"""Write docs/load-testing.md from results/summary.json, with the before/after comparison
read from results/before-fix/ (the run that found the connection-pool deadlock)."""

import csv
import json
from pathlib import Path

from run import OUT, REPORT, render

HERE = Path(__file__).parent


def before_row(users: int) -> dict:
    path = OUT / "before-fix" / f"stage-{users}_stats.csv"
    for row in csv.DictReader(open(path, newline="")):
        if row["Name"] == "Aggregated":
            return row
    raise SystemExit(f"no Aggregated row in {path}")


def main() -> None:
    data = json.loads((OUT / "summary.json").read_text())
    after = {s["users"]: s["endpoints"]["Aggregated"] for s in data["stages"]}
    lines = [
        "## Finding: connection-pool deadlock at 500 users (fixed)",
        "",
        "The first run of this test, against the code before the fix, handled 100 and 250 "
        "users but collapsed at 500, and the API stayed unresponsive after the test ended "
        "(`/health` took 60 s). PostgreSQL showed all 15 pooled connections `idle in "
        "transaction` with the CPU idle. FastAPI runs sync endpoints and the cleanup of sync "
        "generator dependencies in a 40-thread pool; once all threads were blocked waiting "
        "for a connection, the requests holding the connections could not get a thread to "
        "finish and return them.",
        "",
        "Fix (`app/db/session.py`, `ConcurrencyLimitMiddleware` in `app/core/observability.py`):",
        "",
        "- the session dependency is an async generator, so connections are returned on the "
        "event loop and never wait for a thread;",
        "- at most `MAX_CONCURRENT_REQUESTS` (15) requests run at once; the rest wait on the "
        "event loop, holding nothing, and get `503 Retry-After` after 10 s instead of piling "
        "up (health checks and metrics are exempt);",
        "- the pool (15 + 15 overflow) covers two sessions per running request, and its "
        "timeout is 10 s.",
        "",
        "| Users | Before: req/s | Before: errors | Before: p99 | After: req/s | After: errors | After: p99 |",
        "|---|---|---|---|---|---|---|",
    ]
    for users in sorted(after):
        b, a = before_row(users), after[users]
        b_err = int(b["Failure Count"]) / int(b["Request Count"]) * 100
        a_err = a["failures"] / a["requests"] * 100 if a["requests"] else 0
        lines.append(
            f"| {users} | {float(b['Requests/s']):.1f} | {b_err:.1f}% | "
            f"{float(b['99%']):.0f} ms | {a['rps']} | {a_err:.1f}% | {a['p99']:.0f} ms |"
        )
    lines += [
        "",
        "Before-fix CSVs: `loadtest/results/before-fix/`. A regression test covers the 503 "
        "path (`tests/test_health.py::test_load_shedding_returns_503_when_saturated`).",
        "",
        "**Next limit.** At 500 users the single API process runs at about 90% CPU and p95 "
        "latency rises from ~30 ms to ~230 ms: the process, not PostgreSQL (about 20% CPU, "
        "under 20 connections) or Redis, is the bottleneck. `WEB_CONCURRENCY=N` starts N "
        "API processes; each has its own pool of up to 30 connections, so keep N x 30 plus "
        "the worker's connections below PostgreSQL's `max_connections` (100).",
    ]
    REPORT.write_text(
        render(data["env"], data["stages"], "\n".join(lines)), encoding="utf-8"
    )
    print(f"wrote {REPORT}")


if __name__ == "__main__":
    main()
