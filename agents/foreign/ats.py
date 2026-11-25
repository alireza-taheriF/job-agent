"""
Company career boards (public JSON APIs, no login, no scraping).

Greenhouse, Lever and Ashby expose each company's open roles as JSON. Arbeitnow
is a public EU job board API. These are the sources that carry on-site roles
with relocation / visa sponsorship, which the remote-only boards miss.

Company slugs live in config.yaml under `ats_companies`. A wrong slug just
returns 404 and is logged; it never stops the run.
"""

import re

from agents.common import strip_html

RELOCATION = re.compile(
    r"\b(relocation|relocate|visa sponsorship|sponsor(ship)? (a |your )?(work )?visa|"
    r"we sponsor|work permit support|blue card|highly skilled migrant|kennismigrant|"
    r"immigration support|employment pass)\b", re.I)


def relocation_signal(text: str) -> bool:
    return bool(RELOCATION.search(text or ""))


async def greenhouse(c, slug, make_job):
    r = await c.get(f"https://boards-api.greenhouse.io/v1/boards/{slug}/jobs", params={"content": "true"})
    r.raise_for_status()
    out = []
    for j in r.json().get("jobs", []):
        loc = (j.get("location") or {}).get("name") or ""
        desc = strip_html(_unescape(j.get("content") or ""))
        out.append(make_job(f"greenhouse:{slug}", j["absolute_url"], j["title"], slug, desc,
                            location=loc, is_remote="remote" in loc.lower()))
    return out


async def lever(c, slug, make_job):
    r = await c.get(f"https://api.lever.co/v0/postings/{slug}", params={"mode": "json"})
    r.raise_for_status()
    out = []
    for j in r.json():
        cats = j.get("categories") or {}
        loc = cats.get("location") or ""
        desc = j.get("descriptionPlain") or strip_html(j.get("description"))
        for block in j.get("lists") or []:
            desc += "\n" + strip_html(block.get("content"))
        remote = (j.get("workplaceType") == "remote") or "remote" in loc.lower()
        out.append(make_job(f"lever:{slug}", j["hostedUrl"], j["text"], slug, desc,
                            location=loc, is_remote=remote))
    return out


async def ashby(c, slug, make_job):
    r = await c.get(f"https://api.ashbyhq.com/posting-api/job-board/{slug}")
    r.raise_for_status()
    out = []
    for j in r.json().get("jobs", []):
        loc = j.get("location") or ""
        desc = j.get("descriptionPlain") or strip_html(j.get("descriptionHtml"))
        remote = bool(j.get("isRemote")) or j.get("workplaceType") == "Remote"
        out.append(make_job(f"ashby:{slug}", j["jobUrl"], j["title"], slug, desc,
                            location=loc, is_remote=remote))
    return out


async def arbeitnow(c, make_job, pages: int = 3):
    out = []
    for page in range(1, pages + 1):
        r = await c.get("https://www.arbeitnow.com/api/job-board-api", params={"page": page})
        r.raise_for_status()
        for j in r.json().get("data", []):
            out.append(make_job("arbeitnow", j["url"], j["title"], j.get("company_name"),
                                j.get("description"), j.get("tags"),
                                location=j.get("location"), is_remote=bool(j.get("remote"))))
    return out


def _unescape(s: str) -> str:
    import html
    return html.unescape(s)


BOARDS = {"greenhouse": greenhouse, "lever": lever, "ashby": ashby}
