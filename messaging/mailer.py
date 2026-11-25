"""
Outgoing email (SMTP) and reply detection (IMAP).

Safety rules enforced here, not only in the UI:
1. `send()` refuses unless `approved=True` — the caller must pass the user's
   explicit Telegram approval through.
2. `dry_run` (config.yaml → application.dry_run) builds the message and logs
   it but never connects to the server.
3. Credentials come only from .env; nothing is hard-coded.
"""

import email
import imaplib
import mimetypes
import os
import smtplib
import ssl
from email.message import EmailMessage
from email.utils import make_msgid, parseaddr
from pathlib import Path

import log as _log_mod

log = _log_mod.get_logger("mailer")


class NotApproved(RuntimeError):
    pass


def smtp_configured() -> bool:
    return all(os.getenv(k) for k in ("SMTP_HOST", "SMTP_USER", "SMTP_PASSWORD"))


def build(to: str, subject: str, body: str, attachments: list[Path] | None = None) -> EmailMessage:
    msg = EmailMessage()
    msg["From"] = os.getenv("SMTP_FROM") or os.getenv("SMTP_USER", "")
    msg["To"] = to
    msg["Subject"] = subject
    msg["Message-ID"] = make_msgid()
    msg.set_content(body)
    for path in attachments or []:
        path = Path(path)
        if not path.exists():
            continue
        ctype, _ = mimetypes.guess_type(path.name)
        maintype, subtype = (ctype or "application/octet-stream").split("/", 1)
        msg.add_attachment(path.read_bytes(), maintype=maintype, subtype=subtype, filename=path.name)
    return msg


def send(to: str, subject: str, body: str, *, approved: bool, dry_run: bool,
         attachments: list[Path] | None = None) -> tuple[str, str]:
    """Return (status, note). status ∈ {"sent", "dry_run"}; raises on failure."""
    if not approved:
        raise NotApproved("email not approved by the user")
    if "@" not in parseaddr(to)[1]:
        raise ValueError(f"bad recipient: {to!r}")
    msg = build(to, subject, body, attachments)
    if dry_run:
        log.info("mailer.dry_run", to=to, subject=subject)
        return "dry_run", f"dry run — would send to {to}"
    if not smtp_configured():
        raise RuntimeError("SMTP_HOST / SMTP_USER / SMTP_PASSWORD missing in .env")
    host, port = os.environ["SMTP_HOST"], int(os.getenv("SMTP_PORT", "587"))
    ctx = ssl.create_default_context()
    timeout = int(os.getenv("SMTP_TIMEOUT_S", "20"))
    if port == 465:
        server = smtplib.SMTP_SSL(host, port, context=ctx, timeout=timeout)
    else:
        server = smtplib.SMTP(host, port, timeout=timeout)
        server.starttls(context=ctx)
    with server:
        server.login(os.environ["SMTP_USER"], os.environ["SMTP_PASSWORD"])
        server.send_message(msg)
    log.info("mailer.sent", to=to, subject=subject)
    return "sent", f"sent to {to}"


def senders_since(days: int = 30) -> set[str]:
    """Lower-cased sender addresses in the IMAP inbox over the last `days` days."""
    host = os.getenv("IMAP_HOST")
    if not host or not os.getenv("SMTP_USER"):
        return set()
    from datetime import datetime, timedelta
    since = (datetime.utcnow() - timedelta(days=days)).strftime("%d-%b-%Y")
    out: set[str] = set()
    with imaplib.IMAP4_SSL(host) as box:
        box.login(os.environ["SMTP_USER"], os.environ["SMTP_PASSWORD"])
        box.select("INBOX", readonly=True)
        _, data = box.search(None, f'(SINCE "{since}")')
        for num in (data[0] or b"").split():
            _, msg_data = box.fetch(num, "(BODY.PEEK[HEADER.FIELDS (FROM)])")
            hdr = email.message_from_bytes(msg_data[0][1])
            out.add(parseaddr(hdr.get("From", ""))[1].lower())
    return out
