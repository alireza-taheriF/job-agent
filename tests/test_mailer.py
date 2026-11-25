"""Email safety gates and application-address extraction (no SMTP)."""

import pytest

from agents.foreign.submitter import application_email
from messaging import mailer


def test_send_refuses_without_approval():
    with pytest.raises(mailer.NotApproved):
        mailer.send("a@b.com", "s", "b", approved=False, dry_run=True)


def test_dry_run_never_connects(monkeypatch):
    def boom(*a, **k):
        raise AssertionError("SMTP must not be used in dry run")
    monkeypatch.setattr(mailer.smtplib, "SMTP", boom)
    monkeypatch.setattr(mailer.smtplib, "SMTP_SSL", boom)
    assert mailer.send("a@b.com", "s", "b", approved=True, dry_run=True)[0] == "dry_run"


def test_bad_recipient_rejected():
    with pytest.raises(ValueError):
        mailer.send("not-an-address", "s", "b", approved=True, dry_run=True)


def test_application_email_prefers_apply_context():
    d = "Questions: privacy@acme.com. Contact sales@acme.com. To apply, send your CV to jobs@acme.com."
    assert application_email(d) == "jobs@acme.com"


def test_application_email_skips_noreply_and_none():
    assert application_email("Write to noreply@acme.com") is None
    assert application_email("Apply via our careers page") is None
