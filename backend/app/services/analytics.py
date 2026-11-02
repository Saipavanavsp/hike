"""Recruiter analytics from the application status history.

- Funnel: how many applications ever reached each stage, and the conversion from the
  previous stage. "Reached" uses the history, so a candidate who was interviewed and then
  rejected still counts at Interview.
- Time to first response: applied -> first status change by the recruiter.
- Time to offer: applied -> first move to Offer. Hike has no "hired" stage, so this is the
  closest measure of time-to-hire, and is labelled as such.
- Time in stage: average days between entering a stage and leaving it (finished stays only).
"""

from collections import defaultdict
from statistics import median

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Application, ApplicationStatusHistory, Job, User
from app.models.enums import ApplicationStatus, UserRole

S = ApplicationStatus
FUNNEL = [S.applied, S.shortlisted, S.interview, S.offer]


def _days(a, b) -> float:
    return (b - a).total_seconds() / 86400


def _median(values: list[float]) -> float | None:
    return round(median(values), 1) if values else None


def recruiter_analytics(db: Session, user: User, job_id: int | None = None) -> dict:
    stmt = select(Application, Job.title).join(Job, Job.id == Application.job_id)
    if user.role != UserRole.admin:
        stmt = stmt.where(Job.recruiter_id == user.id)
    if job_id is not None:
        stmt = stmt.where(Application.job_id == job_id)
    rows = db.execute(stmt).unique().all()
    apps = {a.id: a for a, _ in rows}
    titles = {a.job_id: t for a, t in rows}

    history: dict[int, list[ApplicationStatusHistory]] = defaultdict(list)
    if apps:
        for h in db.scalars(
            select(ApplicationStatusHistory)
            .where(ApplicationStatusHistory.application_id.in_(apps))
            .order_by(ApplicationStatusHistory.changed_at, ApplicationStatusHistory.id)
        ):
            history[h.application_id].append(h)

    reached = {s: set() for s in FUNNEL}
    first_response, to_offer = [], []
    stage_days: dict[ApplicationStatus, list[float]] = defaultdict(list)
    per_job: dict[int, dict] = defaultdict(
        lambda: {"applications": 0, "interviews": 0, "offers": 0, "to_offer": []}
    )
    for app_id, app in apps.items():
        hs = history[app_id]
        reached[S.applied].add(app_id)
        statuses = {h.to_status for h in hs} | {app.status}
        for s in FUNNEL[1:]:
            if s in statuses:
                reached[s].add(app_id)
        changes = [h for h in hs if h.from_status is not None]
        if changes:
            first_response.append(_days(app.applied_at, changes[0].changed_at))
        offer = next((h for h in hs if h.to_status == S.offer), None)
        if offer:
            to_offer.append(_days(app.applied_at, offer.changed_at))
        for prev, nxt in zip(hs, hs[1:], strict=False):
            stage_days[prev.to_status].append(_days(prev.changed_at, nxt.changed_at))
        j = per_job[app.job_id]
        j["applications"] += 1
        j["interviews"] += S.interview in statuses
        j["offers"] += S.offer in statuses
        if offer:
            j["to_offer"].append(_days(app.applied_at, offer.changed_at))

    funnel = []
    prev_count = None
    for s in FUNNEL:
        n = len(reached[s])
        funnel.append(
            {
                "stage": s.value,
                "count": n,
                "conversion_from_previous": (round(n / prev_count, 3) if prev_count else None),
            }
        )
        prev_count = n
    total = len(apps)
    return {
        "total_applications": total,
        "funnel": funnel,
        "rejected": sum(1 for a in apps.values() if a.status == S.rejected),
        "offer_rate": round(len(reached[S.offer]) / total, 3) if total else None,
        "median_days_to_first_response": _median(first_response),
        "median_days_to_offer": _median(to_offer),
        "offers_measured": len(to_offer),
        "avg_days_in_stage": {
            s.value: round(sum(v) / len(v), 1) for s, v in stage_days.items() if v
        },
        "by_job": sorted(
            (
                {
                    "job_id": jid,
                    "title": titles[jid],
                    "applications": v["applications"],
                    "interviews": v["interviews"],
                    "offers": v["offers"],
                    "median_days_to_offer": _median(v["to_offer"]),
                }
                for jid, v in per_job.items()
            ),
            key=lambda r: -r["applications"],
        ),
    }
