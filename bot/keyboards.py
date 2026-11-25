from telegram import InlineKeyboardButton, InlineKeyboardMarkup


def karlancer_buttons(job_id) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ ارسال", callback_data=f"apply:{job_id}"),
            InlineKeyboardButton("⏭ رد کردن", callback_data=f"skip:{job_id}"),
        ],
        [
            InlineKeyboardButton("✏️ ویرایش پیشنهاد", callback_data=f"edit:{job_id}"),
            InlineKeyboardButton("🔍 جزئیات", callback_data=f"details:{job_id}"),
        ],
    ])


def foreign_buttons(job_id) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ Apply", callback_data=f"apply:{job_id}"),
            InlineKeyboardButton("⏭ Skip", callback_data=f"skip:{job_id}"),
        ],
        [
            InlineKeyboardButton("✏️ Edit materials", callback_data=f"edit:{job_id}"),
            InlineKeyboardButton("🔍 Details", callback_data=f"details:{job_id}"),
        ],
    ])


def edit_confirm_buttons(job_id) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("📤 Send as-is", callback_data=f"send:{job_id}"),
            InlineKeyboardButton("✏️ Edit again", callback_data=f"edit:{job_id}"),
            InlineKeyboardButton("❌ Cancel", callback_data=f"cancel:{job_id}"),
        ],
    ])


def outreach_buttons(target_id) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("📤 Send", callback_data=f"csend:{target_id}"),
        InlineKeyboardButton("⏭ Skip", callback_data=f"cskip:{target_id}"),
    ]])
