"""Tests for URL-hash deduplication logic."""

import hashlib

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from db.models import Base, Job


def url_hash(url: str) -> str:
    return hashlib.sha256(url.encode()).hexdigest()


def make_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def test_same_url_not_inserted_twice():
    session = make_session()
    url = "https://karlancer.com/project/42"
    h = url_hash(url)

    session.add(Job(url=url, url_hash=h, source="karlancer", title="First"))
    session.commit()

    # Simulate the agent dedupe check
    exists = session.query(Job).filter_by(url_hash=h).first()
    assert exists is not None

    # Agent would skip — verify count stays at 1
    if session.query(Job).filter_by(url_hash=h).first() is None:
        session.add(Job(url=url, url_hash=h, source="karlancer", title="Duplicate"))
        session.commit()

    assert session.query(Job).count() == 1


def test_different_urls_all_inserted():
    session = make_session()
    urls = [
        "https://karlancer.com/project/1",
        "https://karlancer.com/project/2",
        "https://remoteok.com/jobs/abc",
    ]
    for url in urls:
        h = url_hash(url)
        session.add(Job(url=url, url_hash=h, source="karlancer", title=f"Job {url[-1]}"))
    session.commit()

    assert session.query(Job).count() == 3


def test_hash_is_deterministic():
    url = "https://wellfound.com/jobs/99"
    assert url_hash(url) == url_hash(url)
    assert len(url_hash(url)) == 64


def test_different_urls_produce_different_hashes():
    assert url_hash("https://a.com/1") != url_hash("https://a.com/2")
