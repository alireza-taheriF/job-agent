"""Karlancer project scorer — LLM-based, cached by prompt hash."""

from agents.common import load_profile, load_style_notes, parse_json
from llm import call_llm


async def score_project(job: dict, db_session) -> tuple[float, str]:
    """Return (score 0-100, short Persian reason)."""
    prompt = f"""شما تناسب یک پروژه فریلنسری را با یک متخصص می‌سنجید. فقط از پروفایل زیر استفاده کنید و هیچ مهارتی را فرض نکنید.

PROFILE:
{load_profile()}

STYLE NOTES:
{load_style_notes()}

پروژه:
عنوان: {job['title']}
بودجه: {job.get('budget_raw') or 'UNKNOWN'}
توضیحات: {(job.get('description') or '')[:3500]}

امتیاز ۰ تا ۱۰۰ بدهید (تطابق مهارت، شفافیت پروژه، بودجه، رقابت). اگر اطلاعاتی نامشخص است بنویسید UNKNOWN.
فقط JSON برگردانید: {{"score": <عدد صحیح>, "reason": "<حداکثر دو جمله کوتاه فارسی>"}}"""
    data = parse_json(await call_llm(prompt, db_session))
    return float(max(0, min(100, data["score"]))), str(data["reason"])[:400]
