from datetime import datetime
from sqlalchemy import (
    Boolean, Column, DateTime, Float, ForeignKey,
    Integer, String, Text, UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, relationship


class Base(DeclarativeBase):
    pass


class Job(Base):
    __tablename__ = "jobs"

    id = Column(Integer, primary_key=True)
    url = Column(String, unique=True, nullable=False)
    url_hash = Column(String(64), unique=True, nullable=False)
    source = Column(String, nullable=False)       # "karlancer", "remoteok", etc.
    title = Column(String, nullable=False)
    company = Column(String)
    description = Column(Text)
    skills_json = Column(Text)                    # JSON list of skill strings
    budget_raw = Column(String)                   # original budget/salary string
    budget_usd_month = Column(Float)              # normalized to USD/month
    currency = Column(String)
    proposals_count = Column(Integer)             # Karlancer: existing proposal count
    client_info_json = Column(Text)               # JSON: rating, history, etc.
    deadline = Column(DateTime)
    posted_at = Column(DateTime)
    collected_at = Column(DateTime, default=datetime.utcnow)

    fit_score = Column(Float)
    score_reason = Column(Text)                   # short why-this-fits note
    score_cached = Column(Boolean, default=False)

    # "new" | "scored" | "shortlisted" | "skipped" | "applied" | "replied" | "interview" | "rejected"
    status = Column(String, default="new")
    is_remote = Column(Boolean, default=True)
    location_note = Column(String)               # any residency/auth restriction text

    proposals = relationship("Proposal", back_populates="job", cascade="all, delete-orphan")
    applications = relationship("Application", back_populates="job", cascade="all, delete-orphan")
    messages = relationship("InboxMessage", back_populates="job", cascade="all, delete-orphan")
    feedback = relationship("FeedbackEvent", back_populates="job", cascade="all, delete-orphan")


class Proposal(Base):
    __tablename__ = "proposals"

    id = Column(Integer, primary_key=True)
    job_id = Column(Integer, ForeignKey("jobs.id"), nullable=False)
    content = Column(Text, nullable=False)
    version = Column(Integer, default=1)
    language = Column(String, default="fa")       # "fa" = Persian, "en" = English
    edit_instruction = Column(Text)               # the instruction that produced this version
    created_at = Column(DateTime, default=datetime.utcnow)

    job = relationship("Job", back_populates="proposals")
    applications = relationship("Application", back_populates="proposal")


class Application(Base):
    __tablename__ = "applications"

    id = Column(Integer, primary_key=True)
    job_id = Column(Integer, ForeignKey("jobs.id"), nullable=False)
    proposal_id = Column(Integer, ForeignKey("proposals.id"))
    submitted_at = Column(DateTime)
    # "pending" | "sent" | "confirmed" | "failed"
    status = Column(String, default="pending")
    submission_method = Column(String)            # "browser" | "email" | "api"
    confirmation_text = Column(Text)
    dry_run = Column(Boolean, default=False)

    job = relationship("Job", back_populates="applications")
    proposal = relationship("Proposal", back_populates="applications")


class InboxMessage(Base):
    __tablename__ = "inbox_messages"

    id = Column(Integer, primary_key=True)
    job_id = Column(Integer, ForeignKey("jobs.id"))
    source = Column(String)                       # "karlancer" | "gmail"
    sender = Column(String)
    subject = Column(String)
    content = Column(Text)
    received_at = Column(DateTime)
    reply_draft = Column(Text)
    # "pending" | "approved" | "sent" | "ignored"
    reply_status = Column(String, default="pending")
    notified_at = Column(DateTime)

    job = relationship("Job", back_populates="messages")


class LLMCache(Base):
    __tablename__ = "llm_cache"

    id = Column(Integer, primary_key=True)
    prompt_hash = Column(String(64), unique=True, nullable=False)
    backend = Column(String)
    response = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)


class FeedbackEvent(Base):
    __tablename__ = "feedback_events"

    id = Column(Integer, primary_key=True)
    job_id = Column(Integer, ForeignKey("jobs.id"))
    action = Column(String)                       # "apply" | "skip" | "edit"
    edit_instruction = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)

    job = relationship("Job", back_populates="feedback")


class ColdEmailTarget(Base):
    __tablename__ = "cold_email_targets"

    id = Column(Integer, primary_key=True)
    company = Column(String)
    contact_email = Column(String)
    contact_name = Column(String)
    contact_role = Column(String)
    source_url = Column(String)                   # LinkedIn profile or company page
    note = Column(Text)                           # personal hook: why this person / company
    subject = Column(String)
    follow_ups = Column(Integer, default=0)
    email_draft = Column(Text)
    sent_at = Column(DateTime)
    follow_up_at = Column(DateTime)
    reply_received = Column(Boolean, default=False)
    opted_out = Column(Boolean, default=False)
    # "new" | "draft" | "sent" | "followup_draft" | "replied" | "skipped" | "opted_out"
    status = Column(String, default="draft")

    __table_args__ = (
        UniqueConstraint("contact_email", name="uq_cold_email_contact"),
    )


class SchedulerState(Base):
    __tablename__ = "scheduler_state"

    id = Column(Integer, primary_key=True)
    key = Column(String, unique=True, nullable=False)
    value = Column(String)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
