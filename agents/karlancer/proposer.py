"""Karlancer proposal drafter — Persian, grounded in profile.md only."""

from agents.common import load_profile, load_style_notes
from llm import call_llm


async def draft_proposal(job: dict, db_session, edit_instruction: str | None = None,
                         previous: str | None = None) -> str:
    """Return a Persian proposal string for the given job."""
    edit = ""
    if previous and edit_instruction:
        edit = f"\nپیشنهاد قبلی:\n{previous}\n\nآن را طبق این دستور ویرایش کنید: {edit_instruction}\n"
    prompt = f"""یک پیشنهاد (proposal) فارسی برای پروژه زیر بنویسید.
قوانین سخت: فقط از حقایق پروفایل استفاده کنید. هیچ تجربه، عدد، کارفرما، مدرک، مقاله یا اختراعی نسازید. علی دانشجوی کارشناسی ارشد است (نه فارغ‌التحصیل). لحن: حرفه‌ای، صمیمی، مختصر (۸۰ تا ۱۵۰ کلمه). یک سؤال دقیق درباره پروژه بپرسید. اگر نیازمندی‌ای در پروفایل نیست، ادعایش نکنید.

PROFILE:
{load_profile()}

STYLE NOTES:
{load_style_notes()}

پروژه: {job['title']}
توضیحات: {(job.get('description') or '')[:3500]}
{edit}
فقط متن پیشنهاد را برگردانید، بدون توضیح اضافه."""
    return (await call_llm(prompt, db_session, skip_cache=bool(edit))).strip()
