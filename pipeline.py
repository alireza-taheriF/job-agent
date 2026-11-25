"""Collect → score → shortlist → draft → store, for both agents."""

import json
import os
from datetime import datetime

import log as _log_mod
from agents.common import load_config
from db.models import Job, Proposal
from db.session import session_scope

log = _log_mod.get_logger("pipeline")

COLS = {c.name for c in Job.__table__.columns}


async def _run(agent: str, collect, score, draft, limit: int, max_scored: int = 40) -> dict:
    cfg = load_config()
    stats = {"collected": 0, "new": 0, "shortlisted": 0}
    with session_scope() as db:
        raw = await collect(limit)
        stats["collected"] = len(raw)
        known = {h for (h,) in db.query(Job.url_hash).all()}
        fresh = [j for j in raw if j["url_hash"] not in known][:max_scored]
        stats["new"] = len(fresh)
        for j in fresh:
            row = Job(**{k: v for k, v in j.items() if k in COLS})
            db.add(row)
            db.flush()
            try:
                row.fit_score, row.score_reason = await score(j, db)
                row.score_cached = True
                row.status = "scored"
            except Exception as exc:
                log.warning("pipeline.score_failed", agent=agent, job=j["url"], error=str(exc)[:200])
            db.commit()

        is_k = Job.source == "karlancer"
        top = (db.query(Job)
               .filter(is_k if agent == "karlancer" else ~is_k,
                       Job.status == "scored", Job.fit_score >= cfg["scoring"]["min_fit_score"])
               .order_by(Job.fit_score.desc()).limit(cfg["collection"]["shortlist_size"]).all())
        for row in top:
            try:
                content = await draft(row, db)
                db.add(Proposal(job_id=row.id, content=content, language="fa" if agent == "karlancer" else "en"))
                row.status = "shortlisted"
                stats["shortlisted"] += 1
            except Exception as exc:
                log.warning("pipeline.draft_failed", agent=agent, job=row.url, error=str(exc)[:200])
            db.commit()
    log.info("pipeline.done", agent=agent, **stats)
    return stats


async def run_karlancer() -> dict:
    from agents.karlancer.collector import collect_projects
    from agents.karlancer.proposer import draft_proposal
    from agents.karlancer.scorer import score_project

    async def draft(row, db):
        return await draft_proposal({"title": row.title, "description": row.description}, db)

    limit = load_config()["collection"]["karlancer_daily_limit"]
    return await _run("karlancer", collect_projects,
                      lambda j, db: score_project(j, db), draft, limit)


async def run_foreign() -> dict:
    from agents.foreign.collector import collect_jobs
    from agents.foreign.materials import generate_materials
    from agents.foreign.scorer import score_job

    async def draft(row, db):
        m = await generate_materials({"title": row.title, "company": row.company,
                                      "description": row.description}, db)
        return json.dumps(m, ensure_ascii=False)

    limit = load_config()["collection"]["foreign_daily_limit"]
    return await _run("foreign", collect_jobs, lambda j, db: score_job(j, db), draft, limit)
