"""Work-mode filter: remote vs relocation (pure function, no network)."""

from agents.foreign.ats import relocation_signal
from agents.foreign.collector import keep_job

CFG = {"work_mode": {"remote": True, "relocation": True}}


def job(remote, desc="", loc=""):
    return {"is_remote": remote, "description": desc, "location_note": loc}


def test_relocation_signals():
    assert relocation_signal("We offer relocation support to Amsterdam")
    assert relocation_signal("Visa sponsorship available")
    assert relocation_signal("EU Blue Card supported")
    assert not relocation_signal("Fully remote, async team")


def test_remote_unrestricted_kept():
    assert keep_job(job(True, "Work from anywhere"), CFG)


def test_remote_restricted_dropped():
    assert not keep_job(job(True, "Applicants must reside in the US. US only."), CFG)


def test_remote_restricted_but_sponsoring_kept():
    assert keep_job(job(True, "EU only, but we provide visa sponsorship and relocation"), CFG)


def test_onsite_without_relocation_dropped():
    assert not keep_job(job(False, "Office in Berlin, 4 days a week", "Berlin"), CFG)


def test_onsite_with_relocation_kept():
    assert keep_job(job(False, "Relocation package and visa sponsorship provided", "Amsterdam"), CFG)


def test_relocation_disabled():
    cfg = {"work_mode": {"remote": True, "relocation": False}}
    assert not keep_job(job(False, "Relocation package provided", "Tallinn"), cfg)


def test_remote_disabled_keeps_only_relocation():
    cfg = {"work_mode": {"remote": False, "relocation": True}}
    assert not keep_job(job(True, "Work from anywhere"), cfg)
    assert keep_job(job(True, "Remote first; we sponsor visas for hubs"), cfg)
