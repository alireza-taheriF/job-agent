"""Foreign job scorer — LLM-based, cached by prompt hash."""

import json

from agents.common import load_profile, load_style_notes, parse_json
from llm import call_llm


async def score_job(job: dict, db_session) -> tuple[float, str]:
    """Return (score 0-100, why-this-fits/risks note)."""
    prompt = f"""You score job postings for fit against one candidate. Use ONLY the profile below; never assume skills not listed.

PROFILE:
{load_profile()}

STYLE NOTES:
{load_style_notes()}

JOB:
Title: {job['title']}
Company: {job.get('company')}
Location / restrictions: {job.get('location_note')}
Salary: {job.get('budget_raw') or 'UNKNOWN'}
Description: {(job.get('description') or '')[:3500]}

Work mode: {job.get('mode') or ('remote' if job.get('is_remote', True) else 'on-site')}.
The candidate is an Iranian citizen living in Iran. He accepts (a) fully remote work from Iran, or (b) relocating with his spouse if the employer sponsors the work visa.
Score 0-100 on skill match, seniority realism for a candidate with ~1 year of professional AI experience, and pay.
Caps:
- Remote role that requires residency or work authorization in a specific country: at most 25.
- On-site/hybrid role with NO mention of relocation or visa sponsorship: at most 25.
- US-based employer for a remote contractor living in Iran: at most 30 (US sanctions usually block this); say so.
If you cannot tell, say UNKNOWN in the reason.
Reply with ONLY JSON: {{"score": <int>, "reason": "<max 2 short sentences, English>"}}"""
    data = parse_json(await call_llm(prompt, db_session))
    return float(max(0, min(100, data["score"]))), str(data["reason"])[:400]
