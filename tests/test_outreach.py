"""Cold outreach: CSV import, daily cap, follow-up scheduling, reply marking."""

import importlib
from datetime import datetime, timedelta

import pytest


@pytest.fixture()
def db(tmp_path, monkeypatch):
    monkeypatch.setenv("DB_PATH", str(tmp_path / "t.db"))
    import db.session as s
    importlib.reload(s)
    s.create_tables()
    with s.session_scope() as sess:
        yield sess


@pytest.fixture()
def cfg(monkeypatch):
    from agents.outreach import cold_email
    conf = {"cold_email": {"max_per_day": 2, "follow_up_after_days": 6, "max_follow_ups": 1},
            "application": {"dry_run": False}}
    monkeypatch.setattr(cold_email, "load_config", lambda: conf)
    sent = []
    monkeypatch.setattr(cold_email.mailer, "send",
                        lambda to, subj, body, approved, dry_run, attachments=None:
                        (sent.append(to) or ("sent", "ok")) if approved else (_ for _ in ()).throw(RuntimeError()))
    return sent


def _csv(tmp_path):
    p = tmp_path / "c.csv"
    p.write_text("company,name,role,email,linkedin,note\n"
                 "Adyen,Ann,EM,ann@adyen.com,,met at meetup\n"
                 "Wise,Bob,Lead,bob@wise.com,,\n"
                 "Wolt,Cy,CTO,cy@wolt.com,,\n"
                 "NoMail,Dee,EM,,https://linkedin.com/in/dee,\n"
                 "Adyen,Ann,EM,ANN@adyen.com,,dup\n")
    return p


def test_import_skips_missing_and_duplicate(db, tmp_path):
    from agents.outreach import cold_email
    assert cold_email.import_contacts(db, _csv(tmp_path)) == {"added": 3, "skipped": 2}


def test_daily_cap_and_followup(db, tmp_path, cfg):
    from agents.outreach import cold_email
    from db.models import ColdEmailTarget
    cold_email.import_contacts(db, _csv(tmp_path))
    rows = db.query(ColdEmailTarget).all()
    for t in rows:
        t.subject, t.email_draft, t.status = "Hi", "body", "draft"
    assert cold_email.send(db, rows[0], approved=True)[0] == "sent"
    assert cold_email.send(db, rows[1], approved=True)[0] == "sent"
    assert cold_email.send(db, rows[2], approved=True)[0] == "capped"
    assert cfg == ["ann@adyen.com", "bob@wise.com"]
    assert rows[0].follow_up_at - rows[0].sent_at == timedelta(days=6)


def test_replies_marked(db, tmp_path, cfg):
    from agents.outreach import cold_email
    from db.models import ColdEmailTarget
    cold_email.import_contacts(db, _csv(tmp_path))
    t = db.query(ColdEmailTarget).filter_by(contact_email="ann@adyen.com").one()
    t.status, t.sent_at = "sent", datetime.utcnow()
    assert cold_email.mark_replies(db, {"ann@adyen.com"}) == 1
    assert t.status == "replied"
    assert cold_email.send(db, t, approved=True)[0] == "skipped"
