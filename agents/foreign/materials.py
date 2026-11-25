"""Foreign job materials generator. Source of truth: profile.md (TODO lines removed)."""

from agents.common import load_profile, load_style_notes, parse_json
from llm import call_llm


async def generate_materials(job: dict, db_session, edit_instruction: str | None = None,
                             previous: str | None = None) -> dict:
    """Return {"cover_letter": str, "cv_highlights": list[str], "form_answers": dict}."""
    edit = ""
    if previous and edit_instruction:
        edit = f"\nPREVIOUS COVER LETTER:\n{previous}\n\nREVISE IT according to this instruction: {edit_instruction}\n"
    prompt = f"""Write application materials in English for the job below.
HARD RULES: use ONLY facts in the profile. Never invent experience, metrics, employers, degrees, papers or patents. The candidate is an MSc STUDENT (not a graduate). English level is B2. If a requirement is not covered by the profile, do not claim it. If the role is on-site/hybrid, say once, briefly, that he is ready to relocate with his spouse and would need visa sponsorship. Tone: professional, friendly, concise.

PROFILE:
{load_profile()}

STYLE NOTES:
{load_style_notes()}

JOB:
Title: {job['title']} at {job.get('company')}
Description: {(job.get('description') or '')[:3500]}
{edit}
Reply with ONLY JSON:
{{"cover_letter": "<150-220 words, plain text>",
  "cv_highlights": ["<3-5 real profile items most relevant to this job>"],
  "form_answers": {{"why_this_role": "...", "availability": "...", "salary_expectation": "UNKNOWN - to be decided by Ali"}}}}"""
    return parse_json(await call_llm(prompt, db_session, skip_cache=bool(edit)))
