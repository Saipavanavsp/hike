"""Run the load test stages against the local Docker stack and write docs/load-testing.md.

    pip install -r loadtest/requirements.txt          (plus backend/requirements.txt for redis/psycopg)
    docker compose up -d --build
    python loadtest/run.py                            # 100, 250, 500 users; ~10 minutes
    python loadtest/run.py --users 100 --seconds 60   # quick run

Per stage: Locust runs headless (stats reset once all users are spawned, so the ramp-up is
excluded), while this script samples PostgreSQL connections every second and container CPU
and memory once mid-stage. Afterwards it reads the search-cache hit/miss counters from the
API's /metrics, Redis INFO, and resume-parsing times from the background_tasks table.
"""

import argparse
import csv
import json
import platform
import re
import statistics
import subprocess
import sys
import threading
import time
from datetime import UTC, datetime
from pathlib import Path

import psycopg
import redis
import requests

HERE = Path(__file__).parent
ROOT = HERE.parent
OUT = HERE / "results"
REPORT = ROOT / "docs" / "load-testing.md"
APP = "http://localhost:8080"
API = "http://localhost:8000"
DSN = "postgresql://hike:hike@localhost:5432/hike"
GROUPS = [
    "search /api/jobs",
    "job detail /api/jobs/{id}",
    "autocomplete",
    "my applications",
    "notifications",
    "recruiter pipeline",
    "resume upload",
    "Aggregated",
]


def cache_counters() -> dict[tuple[str, str], float]:
    # After a heavy stage the API may still be draining its backlog: wait and retry.
    for attempt in range(6):
        try:
            text = requests.get(f"{API}/metrics", timeout=60).text
            break
        except requests.RequestException:
            if attempt == 5:
                raise
            time.sleep(10)
    out = {}
    for m in re.finditer(
        r'hike_cache_requests_total\{cache="([^"]+)",result="([^"]+)"\} ([\d.e+]+)',
        text,
    ):
        out[(m.group(1), m.group(2))] = float(m.group(3))
    return out


def redis_stats() -> dict[str, int]:
    info = redis.Redis.from_url("redis://localhost:6379/0").info("stats")
    return {"hits": info["keyspace_hits"], "misses": info["keyspace_misses"]}


class DbSampler(threading.Thread):
    def __init__(self):
        super().__init__(daemon=True)
        self.samples: list[int] = []
        self.stop = threading.Event()

    def run(self):
        with psycopg.connect(DSN, autocommit=True) as conn:
            while not self.stop.is_set():
                n = conn.execute(
                    "SELECT count(*) FROM pg_stat_activity WHERE datname = 'hike' AND pid <> pg_backend_pid()"
                ).fetchone()[0]
                self.samples.append(n)
                time.sleep(1)


def docker_stats() -> dict[str, str]:
    out = subprocess.run(
        ["docker", "stats", "--no-stream", "--format", "{{.Name}}|{{.CPUPerc}}|{{.MemUsage}}"],
        capture_output=True, text=True, check=False,
    ).stdout  # fmt: skip
    rows = {}
    for line in out.splitlines():
        name, cpu, mem = line.split("|")
        if name.startswith("hike-"):
            rows[name.removeprefix("hike-").removesuffix("-1")] = (
                f"{cpu} CPU, {mem.split(' / ')[0]}"
            )
    return rows


def upload_stats(since: datetime) -> dict:
    with psycopg.connect(DSN) as conn:
        rows = conn.execute(
            "SELECT status, extract(epoch FROM finished_at - created_at) FROM background_tasks "
            "WHERE kind = 'process_resume' AND created_at >= %s",
            (since,),
        ).fetchall()
    done = [float(d) for s, d in rows if s == "succeeded" and d is not None]
    return {
        "queued": len(rows),
        "succeeded": len(done),
        "failed": sum(1 for s, _ in rows if s == "failed"),
        "p50_s": round(statistics.median(done), 2) if done else None,
        "p95_s": round(sorted(done)[int(0.95 * (len(done) - 1))], 2) if done else None,
    }


def flow_stats(path: Path) -> dict:
    """Upload-to-parsed time as the uploading client saw it (upload + polling)."""
    if not path.exists():
        return {"client_p50_ms": None, "client_p95_ms": None}
    flows = json.loads(path.read_text())
    ms = sorted(f["ms"] for f in flows if f["status"] == "ready")
    return {
        "client_flows": len(flows),
        "client_p50_ms": round(statistics.median(ms)) if ms else None,
        "client_p95_ms": round(ms[int(0.95 * (len(ms) - 1))]) if ms else None,
    }


def read_stats(prefix: Path) -> dict[str, dict]:
    out = {}
    with open(f"{prefix}_stats.csv", newline="") as f:
        for row in csv.DictReader(f):
            name = row["Name"]
            if name not in GROUPS:
                continue
            out[name] = {
                "requests": int(row["Request Count"]),
                "failures": int(row["Failure Count"]),
                "rps": round(float(row["Requests/s"]), 1),
                "p50": float(row["50%"]),
                "p95": float(row["95%"]),
                "p99": float(row["99%"]),
            }
    return out


def run_stage(users: int, seconds: int) -> dict:
    prefix = OUT / f"stage-{users}"
    before_cache, before_redis = cache_counters(), redis_stats()
    since = datetime.now(UTC)
    sampler = DbSampler()
    sampler.start()
    spawn_rate = max(10, users // 20)
    cmd = [
        sys.executable, "-m", "locust", "-f", str(HERE / "locustfile.py"), "--headless",
        "-u", str(users), "-r", str(spawn_rate), "--run-time", f"{seconds}s", "--host", APP,
        "--csv", str(prefix), "--reset-stats", "--only-summary", "--loglevel", "WARNING",
    ]  # fmt: skip
    flow_file = OUT / f"stage-{users}-uploads.json"
    flow_file.unlink(missing_ok=True)
    env = {**__import__("os").environ, "LOAD_FLOW_FILE": str(flow_file)}
    proc = subprocess.Popen(
        cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True, env=env
    )
    time.sleep(min(seconds - 5, users / spawn_rate + 30))
    resources = docker_stats()
    _, err = proc.communicate()
    sampler.stop.set()
    after_cache, after_redis = cache_counters(), redis_stats()

    def delta(cache: str, result: str) -> float:
        return after_cache.get((cache, result), 0) - before_cache.get(
            (cache, result), 0
        )

    hits, misses = delta("search", "hit"), delta("search", "miss")
    r_hits = after_redis["hits"] - before_redis["hits"]
    r_misses = after_redis["misses"] - before_redis["misses"]
    with psycopg.connect(DSN) as conn:
        max_conn = int(conn.execute("SHOW max_connections").fetchone()[0])
    return {
        "users": users,
        "seconds": seconds,
        "endpoints": read_stats(prefix),
        "search_cache_hit_rate": (
            round(hits / (hits + misses), 3) if hits + misses else None
        ),
        "redis_hit_rate": (
            round(r_hits / (r_hits + r_misses), 3) if r_hits + r_misses else None
        ),
        "db_connections_max": max(sampler.samples) if sampler.samples else None,
        "db_connections_mean": (
            round(statistics.mean(sampler.samples), 1) if sampler.samples else None
        ),
        "postgres_max_connections": max_conn,
        "uploads": {**upload_stats(since), **flow_stats(flow_file)},
        "resources_mid_stage": resources,
        "locust_errors": (
            err.strip().splitlines()[-5:] if proc.returncode not in (0, 1) else []
        ),
    }


def environment() -> dict:
    cfg = requests.get(f"{API}/health", timeout=10).json()
    return {
        "date": datetime.now(UTC).strftime("%Y-%m-%d"),
        "machine": f"{platform.system()} {platform.release()}, {platform.processor() or platform.machine()}",
        "cpus": __import__("os").cpu_count(),
        "worker": cfg.get("worker"),
    }


def render(env: dict, stages: list[dict], note: str) -> str:
    L = [
        "# Load testing",
        "",
        "_Generated by `python loadtest/run.py`. Raw Locust CSVs are in `loadtest/results/`._",
        "",
        f"**Setup.** {env['machine']}, {env['cpus']} logical CPUs, Docker Desktop. Locust and the "
        "whole stack (nginx, one FastAPI process, Celery worker with concurrency 2, PostgreSQL, "
        "Redis) run on the **same laptop**, so Locust competes with the app for CPU. These "
        "numbers describe this machine, not a production deployment; they are useful for "
        "finding bottlenecks and comparing changes, not as capacity guarantees. "
        f"Run on {env['date']}.",
        "",
        "**Traffic.** Each stage ramps to the given number of concurrent users, then measures "
        "for the stated time (ramp-up excluded). Users mostly browse: search (30% with location "
        "filters, some misspelt queries, some page 2), job pages and autocomplete, half of them "
        "signed in so match scores are computed; others check their applications and "
        "notifications. Five recruiters load ranked candidate pipelines and five uploaders send "
        "real PDF resumes and wait for the background worker to parse them. Every user waits "
        "1-5 s between actions.",
        "",
    ]
    if note:
        L += [note, ""]
    for s in stages:
        e = s["endpoints"]
        agg = e.get("Aggregated", {})
        fail_rate = (
            agg["failures"] / agg["requests"] * 100 if agg.get("requests") else 0
        )
        L += [
            f"## {s['users']} concurrent users ({s['seconds']} s measured)",
            "",
            f"Throughput **{agg.get('rps', 0)} requests/s**, error rate **{fail_rate:.2f}%** "
            f"({agg.get('failures', 0)} of {agg.get('requests', 0)}).",
            "",
            "| Endpoint | Requests | Req/s | Errors | p50 ms | p95 ms | p99 ms |",
            "|---|---|---|---|---|---|---|",
        ]
        for name in GROUPS:
            if name in e:
                r = e[name]
                L.append(
                    f"| {name} | {r['requests']} | {r['rps']} | {r['failures']} | "
                    f"{r['p50']:.0f} | {r['p95']:.0f} | {r['p99']:.0f} |"
                )
        u = s["uploads"]
        hit = s["search_cache_hit_rate"]
        L += [
            "",
            (
                f"- Search cache (Redis) hit rate: **{hit * 100:.1f}%**"
                + (
                    f" (all Redis reads: {s['redis_hit_rate'] * 100:.1f}%)"
                    if s["redis_hit_rate"] is not None
                    else ""
                )
                if hit is not None
                else "- Search cache hit rate: n/a"
            ),
            f"- PostgreSQL connections: max {s['db_connections_max']}, mean "
            f"{s['db_connections_mean']} (server limit {s['postgres_max_connections']})",
            f"- Resume parsing: {u['succeeded']} of {u['queued']} uploads parsed during the stage "
            f"({u['failed']} failed); time from upload to parsed, seen by the uploader: "
            f"p50 {u['client_p50_ms']} ms, p95 {u['client_p95_ms']} ms (queue + sandboxed "
            f"parse in the worker: p50 {u['p50_s']} s, p95 {u['p95_s']} s)",
            "- Containers mid-stage: "
            + "; ".join(
                f"{k} {v}" for k, v in sorted(s["resources_mid_stage"].items())
            ),
            "",
        ]
    return "\n".join(L)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--users", type=int, nargs="*", default=[100, 250, 500])
    ap.add_argument("--seconds", type=int, default=120)
    ap.add_argument("--note", default="", help="extra paragraph for the report")
    ap.add_argument("--no-report", action="store_true")
    args = ap.parse_args()
    OUT.mkdir(exist_ok=True)
    env = environment()
    stages = []
    for users in args.users:
        print(f"stage: {users} users ...", flush=True)
        stage = run_stage(users, args.seconds)
        agg = stage["endpoints"].get("Aggregated", {})
        print(
            f"  {agg.get('rps')} req/s, p50 {agg.get('p50')} p95 {agg.get('p95')} "
            f"p99 {agg.get('p99')} ms, failures {agg.get('failures')}/{agg.get('requests')}",
            flush=True,
        )
        (OUT / "summary.partial.json").write_text(
            json.dumps(stages + [stage], indent=1)
        )
        stages.append(stage)
        time.sleep(10)
    (OUT / "summary.json").write_text(
        json.dumps({"env": env, "stages": stages}, indent=1)
    )
    if not args.no_report:
        REPORT.write_text(render(env, stages, args.note), encoding="utf-8")
        print(f"wrote {REPORT}")


if __name__ == "__main__":
    main()
