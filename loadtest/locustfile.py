"""Locust scenario for Hike. Run through loadtest/run.py, which drives the stages and writes
docs/load-testing.md; or interactively:

    locust -f loadtest/locustfile.py --host http://localhost:8080

User mix (per stage, scaled by the number of users):
- Browser (most users): job search with a random query (some misspelt, some with filters,
  some page 2), job detail, autocomplete. Half are signed-in seekers (personalised match
  scores), half anonymous.
- Applicant (seeker, signed in): their applications and notifications.
- Recruiter (fixed 5): candidate pipeline for their busiest job, which computes match scores.
- Uploader (fixed 5): uploads a resume with consent and polls until the worker has parsed it.
"""

import random
import time
from pathlib import Path

from locust import HttpUser, between, events, task

CSRF = {"X-CSRF-Protection": "1"}
SEEKERS = [
    "rahul", "sneha", "imran", "deepika", "aditya", "nandini", "farhan", "pooja", "karthik",
    "simran", "vikram", "ayesha", "siddharth", "lakshmi", "manish", "revathi", "aman", "divya",
    "harish", "tanvi",
]  # fmt: skip
RECRUITERS = ["meera", "rohan", "ananya"]
QUERIES = [
    "python", "react", "backend engineer", "data scientist", "kubernetes", "java spring",
    "frontend", "devops", "machine learning", "android", "full stack", "golang", "sre",
    "pyhton developer", "javscript", "k8s", "ml engineer", "node", "qa automation", "flutter",
    "", "", "",
]  # fmt: skip
LOCATIONS = ["Bengaluru", "Hyderabad", "Pune", "Chennai", "Remote"]
ROLES = ["backend", "frontend", "fullstack", "data_ml", "devops", "mobile", "qa"]
RESUME = (
    Path(__file__).parents[1]
    / "backend"
    / "tests"
    / "fixtures"
    / "priya_sharma_backend.pdf"
).read_bytes()

tokens: dict[str, str] = {}
job_ids: list[int] = []
flows: list[dict] = []


@events.test_stop.add_listener
def _write_flows(environment, **_kw):
    import json
    import os

    path = os.environ.get("LOAD_FLOW_FILE")
    if path:
        Path(path).write_text(json.dumps(flows))


@events.test_start.add_listener
def _prepare(environment, **_kw):
    """Log the demo users in once (bcrypt is deliberately slow) and collect job ids.
    Access tokens last 15 minutes, longer than one stage."""
    import requests

    host = environment.host
    s = requests.Session()
    accounts = [(n, "Seeker@123") for n in SEEKERS] + [
        (n, "Recruiter@123") for n in RECRUITERS
    ]
    for name, password in accounts:
        r = s.post(
            f"{host}/api/auth/login",
            json={"email": f"{name}@example.com", "password": password},
            headers=CSRF,
        )
        r.raise_for_status()
        tokens[name] = r.json()["access_token"]
    page = s.get(f"{host}/api/jobs", params={"page_size": 50}).json()
    job_ids.extend(j["id"] for j in page["items"])


def _auth(name: str) -> dict:
    return {"Authorization": f"Bearer {tokens[name]}"}


class Browser(HttpUser):
    weight = 8
    wait_time = between(1, 3)

    def on_start(self):
        self.who = random.choice(SEEKERS) if random.random() < 0.5 else None

    def _h(self):
        return _auth(self.who) if self.who else {}

    @task(5)
    def search(self):
        params = {"q": random.choice(QUERIES)}
        if random.random() < 0.3:
            params["location"] = random.choice(LOCATIONS)
        if random.random() < 0.2:
            params["role"] = random.choice(ROLES)
        if random.random() < 0.15:
            params["page"] = 2
        self.client.get(
            "/api/jobs", params=params, headers=self._h(), name="search /api/jobs"
        )

    @task(3)
    def job_detail(self):
        if job_ids:
            jid = random.choice(job_ids)
            self.client.get(
                f"/api/jobs/{jid}", headers=self._h(), name="job detail /api/jobs/{id}"
            )

    @task(2)
    def autocomplete(self):
        prefix = random.choice(["py", "rea", "back", "dat", "kub", "fro", "dev", "and"])
        self.client.get(
            "/api/jobs/autocomplete", params={"q": prefix}, name="autocomplete"
        )


class Applicant(HttpUser):
    weight = 2
    wait_time = between(2, 5)

    def on_start(self):
        self.who = random.choice(SEEKERS)

    @task(2)
    def applications(self):
        self.client.get(
            "/api/applications", headers=_auth(self.who), name="my applications"
        )

    @task(1)
    def notifications(self):
        self.client.get(
            "/api/notifications", headers=_auth(self.who), name="notifications"
        )


class Recruiter(HttpUser):
    fixed_count = 5
    wait_time = between(2, 5)

    def on_start(self):
        self.who = random.choice(RECRUITERS)
        jobs = self.client.get(
            "/api/recruiter/jobs", headers=_auth(self.who), name="recruiter jobs"
        ).json()
        self.job = (
            max(jobs, key=lambda j: j["applications_count"])["id"] if jobs else None
        )

    @task
    def pipeline(self):
        if self.job:
            self.client.get(
                f"/api/recruiter/jobs/{self.job}/applications",
                headers=_auth(self.who),
                name="recruiter pipeline",
            )


class Uploader(HttpUser):
    fixed_count = 5
    wait_time = between(4, 8)

    def on_start(self):
        email = f"load-{random.getrandbits(48):x}@example.com"
        r = self.client.post(
            "/api/auth/register",
            json={
                "email": email,
                "password": "LoadTest123",
                "full_name": "Load Test",
                "role": "seeker",
            },
            headers=CSRF,
            name="register",
        )
        self.h = {"Authorization": f"Bearer {r.json()['access_token']}"}

    @task
    def upload(self):
        t0 = time.perf_counter()
        r = self.client.post(
            "/api/resumes",
            files={"file": ("cv.pdf", RESUME, "application/pdf")},
            data={"consent": "true"},
            headers=self.h,
            name="resume upload",
        )
        if r.status_code != 202:
            return
        rid = r.json()["id"]
        for _ in range(60):
            status = self.client.get(
                f"/api/resumes/{rid}", headers=self.h, name="resume status poll"
            ).json()["status"]
            if status != "processing":
                break
            time.sleep(0.5)
        # Time from upload to parsed, as the seeker experiences it (kept out of the HTTP
        # request statistics; written to a file at the end of the run).
        flows.append({"ms": (time.perf_counter() - t0) * 1000, "status": status})
