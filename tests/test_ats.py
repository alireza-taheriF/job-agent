"""ATS board parsers against canned API payloads (no network)."""

import asyncio

from agents.foreign import ats
from agents.foreign.collector import _job


class FakeResp:
    def __init__(self, payload):
        self._p = payload

    def raise_for_status(self):
        pass

    def json(self):
        return self._p


class FakeClient:
    def __init__(self, payload):
        self.payload = payload
        self.urls = []

    async def get(self, url, params=None):
        self.urls.append(url)
        return FakeResp(self.payload)


def run(co):
    return asyncio.run(co)


def test_greenhouse_parses_and_unescapes():
    c = FakeClient({"jobs": [{"absolute_url": "https://x/1", "title": "ML Engineer",
                              "location": {"name": "Amsterdam"},
                              "content": "&lt;p&gt;We offer relocation&lt;/p&gt;"}]})
    out = run(ats.greenhouse(c, "adyen", _job))
    assert out[0]["source"] == "greenhouse:adyen"
    assert out[0]["is_remote"] is False
    assert "relocation" in out[0]["description"] and "<p>" not in out[0]["description"]
    assert c.urls[0].endswith("/boards/adyen/jobs")


def test_lever_remote_flag():
    c = FakeClient([{"hostedUrl": "https://x/2", "text": "AI Engineer", "workplaceType": "remote",
                     "categories": {"location": "Europe"}, "descriptionPlain": "LLM agents",
                     "lists": [{"content": "<li>Python</li>"}]}])
    out = run(ats.lever(c, "binance", _job))
    assert out[0]["is_remote"] is True and "Python" in out[0]["description"]


def test_ashby_parses():
    c = FakeClient({"jobs": [{"jobUrl": "https://x/3", "title": "Applied AI", "location": "London",
                              "isRemote": False, "descriptionPlain": "Visa sponsorship"}]})
    out = run(ats.ashby(c, "synthesia", _job))
    assert out[0]["url"] == "https://x/3" and out[0]["is_remote"] is False
