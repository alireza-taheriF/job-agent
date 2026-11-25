"""
Foreign remote job collector.

Only public APIs / feeds are used: remote boards (RemoteOK, Remotive, We Work
Remotely RSS, Himalayas, Hacker News "Who is hiring") plus company career
boards (Greenhouse, Lever, Ashby) and Arbeitnow for relocation roles.
LinkedIn / Wellfound / YC need a login or scraping and are NOT collected.

A job is kept when it is remote with no residency restriction, or when it is
on-site/hybrid but says it offers relocation or visa sponsorship.
"""

import asyncio
import json
import re
from datetime import datetime
from xml.etree import ElementTree

import httpx

import log as _log_mod
from agents.foreign import ats
from agents.common import keyword_hits, load_config, strip_html, url_hash

log = _log_mod.get_logger("foreign.collector")

HEADERS = {"User-Agent": "job-agent/0.1 (personal job search)"}
RESTRICTED = re.compile(
    r"\b(us only|u\.s\. only|usa only|must (be|reside)|work authorization|"
    r"eu only|uk only|canada only|us citizens?|green card|security clearance)\b", re.I)


def _job(source, url, title, company, description, skills=None, salary_raw=None,
         salary_usd_month=None, posted_at=None, location=None, is_remote=True) -> dict:
    return {
        "source": source, "url": url, "url_hash": url_hash(url), "title": title,
        "company": company, "description": strip_html(description)[:6000],
        "skills_json": json.dumps(skills or []), "budget_raw": salary_raw,
        "budget_usd_month": salary_usd_month, "currency": "USD",
        "posted_at": posted_at, "is_remote": is_remote, "location_note": location,
    }


def _month(low, high, period="year"):
    vals = [v for v in (low, high) if v]
    if not vals:
        return None
    v = sum(vals) / len(vals)
    return round(v / 12 if period == "year" else v, 0)


async def _remoteok(c):
    r = await c.get("https://remoteok.com/api")
    out = []
    for j in r.json()[1:]:
        lo, hi = j.get("salary_min") or 0, j.get("salary_max") or 0
        out.append(_job("remoteok", j["url"], j["position"], j.get("company"),
                        j.get("description"), j.get("tags"),
                        f"${lo}-{hi}/yr" if hi else None, _month(lo, hi) if hi else None,
                        location=j.get("location")))
    return out


async def _remotive(c):
    r = await c.get("https://remotive.com/api/remote-jobs?limit=200")
    return [_job("remotive", j["url"], j["title"], j.get("company_name"),
                 j.get("description"), j.get("tags"), j.get("salary") or None,
                 location=j.get("candidate_required_location"))
            for j in r.json().get("jobs", [])]


async def _wwr(c):
    out = []
    for feed in ("remote-programming-jobs", "remote-back-end-programming-jobs"):
        r = await c.get(f"https://weworkremotely.com/categories/{feed}.rss")
        for it in ElementTree.fromstring(r.content).iter("item"):
            t = it.findtext("title") or ""
            company, _, title = t.partition(": ")
            out.append(_job("weworkremotely", it.findtext("link"), title or t, company,
                            it.findtext("description"), location=it.findtext("region")))
    return out


async def _himalayas(c):
    r = await c.get("https://himalayas.app/jobs/api?limit=100")
    out = []
    for j in r.json().get("jobs", []):
        lo, hi = j.get("minSalary"), j.get("maxSalary")
        out.append(_job("himalayas", j.get("applicationLink") or j.get("guid"),
                        j["title"], j.get("companyName"), j.get("description"),
                        j.get("categories"), f"{lo}-{hi} {j.get('currency')}/yr" if hi else None,
                        _month(lo, hi) if j.get("currency") == "USD" else None,
                        location=", ".join(j.get("locationRestrictions") or []) or None))
    return out


async def _hackernews(c):
    r = await c.get("https://hn.algolia.com/api/v1/search_by_date",
                    params={"tags": "story,author_whoishiring", "hitsPerPage": 5})
    thread = next((h for h in r.json()["hits"] if "who is hiring" in h["title"].lower()), None)
    if not thread:
        return []
    r = await c.get("https://hn.algolia.com/api/v1/search", params={
        "tags": f"comment,story_{thread['objectID']}", "query": "remote", "hitsPerPage": 100})
    out = []
    for h in r.json()["hits"]:
        text = strip_html(h.get("comment_text"))
        if not text:
            continue
        out.append(_job("hackernews", f"https://news.ycombinator.com/item?id={h['objectID']}",
                        text.split("|")[0][:100] + " | " + (text.split("|")[1][:60] if "|" in text else ""),
                        text.split("|")[0][:60], text))
    return out


SOURCES = {"remoteok": _remoteok, "remotive": _remotive, "weworkremotely": _wwr,
           "himalayas": _himalayas, "hackernews": _hackernews}


def _source_calls(cfg, c):
    """(label, coroutine) for every enabled source, including one per ATS company."""
    calls = [(s, SOURCES[s](c)) for s, on in cfg["sources"].items() if on and s in SOURCES]
    if cfg["sources"].get("arbeitnow"):
        calls.append(("arbeitnow", ats.arbeitnow(c, _job)))
    for board, fn in ats.BOARDS.items():
        if not cfg["sources"].get(board):
            continue
        for slug in (cfg.get("ats_companies") or {}).get(board) or []:
            calls.append((f"{board}:{slug}", fn(c, slug, _job)))
    return calls


def keep_job(j: dict, cfg: dict) -> bool:
    """Location / mode filter. Pure function so it is unit-tested."""
    mode = cfg.get("work_mode", {})
    text = f"{j.get('location_note') or ''} {(j.get('description') or '')[:3000]}"
    relocation = ats.relocation_signal(text)
    j["relocation"] = relocation
    if j.get("is_remote", True):
        if not mode.get("remote", True):
            return relocation and mode.get("relocation", True)
        if RESTRICTED.search(text[:1600]) and not (relocation and mode.get("relocation", True)):
            return False
        return True
    return relocation and mode.get("relocation", True)


async def collect_jobs(limit: int = 100) -> list[dict]:
    cfg = load_config()
    min_salary = cfg["scoring"]["foreign_min_salary_usd_month"]
    found: list[dict] = []
    async with httpx.AsyncClient(headers=HEADERS, timeout=30, follow_redirects=True) as c:
        calls = _source_calls(cfg, c)
        enabled = [label for label, _ in calls]
        results = await asyncio.gather(*(co for _, co in calls), return_exceptions=True)
    for s, res in zip(enabled, results):
        if isinstance(res, Exception):
            log.warning("foreign.source_failed", source=s, error=str(res)[:200])
        else:
            log.info("foreign.source_ok", source=s, count=len(res))
            found += res

    keep, seen = [], set()
    for j in found:
        if not j["url"] or j["url_hash"] in seen:
            continue
        seen.add(j["url_hash"])
        text = f"{j['title']} {j['description']} {j['skills_json']}"
        if keyword_hits(text, cfg) < 1:
            continue
        if not keep_job(j, cfg):
            continue
        if j["budget_usd_month"] is not None and j["budget_usd_month"] < min_salary:
            continue
        j["_hits"] = keyword_hits(text, cfg)
        keep.append(j)
    keep.sort(key=lambda j: -j["_hits"])
    for j in keep:
        j.pop("_hits", None)
        if j.pop("relocation", False):
            j["location_note"] = f"{j['location_note'] or 'on-site'} · relocation/visa mentioned"
    return keep[:limit]
