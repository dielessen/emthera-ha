"""The report "boiler-share 2" made from a material bundle (TESTER-AUTO-1).

The Hub that shares by itself sends raw material (share_format/material.py: the documents its own page reads, one recorded half
hour, what its scorer says about it). Our own computer turns it into a report. There is no second builder: this runs
tester_run.TesterRun._build, the Python twin of the Hub's page (pinned to the page by test_tester_run_hub_mirror.py), over the very
inputs the page gives its builder, with the run's record made from the bundle instead of from a person: no moment was tapped, no
display was typed, no photo was taken, and the attended test is only what the Hub already saved (the display question is not asked of an automatic report: share_format/auto.py says what that
means for the rules).

Nothing here is called by the integration: it is for the owner's computer (tools/testers/intake loads it through material_loader.py).
Pure: no clock, no network, no files.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from types import SimpleNamespace

from . import tester_ot as ot
from . import tester_run
from .share_format import auto, fmt, material

class MaterialInvalid(Exception):
    """The bundle is not valid: `problems` are the strict reader's (path, code, what)."""

    def __init__(self, problems):
        super().__init__(f"{len(problems)} problem(s)")
        self.problems = problems


def _status(bundle):
    r = bundle["recording"]
    return {"state": r["state"], "seconds": r["seconds"], "frames": r["frames"], "polls": r["polls"], "dropped": r["dropped"]}


def _raw(bundle):
    d = bundle["documents"]
    if bundle["link"] == "opentherm":
        return {"/status/version": d["version"], ot.OT_LINK: d["ot_link"], ot.OT_RUN: d["ot_run"], ot.OT_TEST: d.get("ot_test"),
                "groups": d.get("ot_groups") or []}
    return {"/status/version": d["version"], "/boiler/match": d["match"], "/status/boiler/profile": d["profile"],
            "/status/ems/devices": d["devices"], "/status/boiler": d["boiler"], "/boiler/plus-probe": d.get("plus_probe")}


def report_from_material(bundle):
    """A valid material bundle (the dict) -> the report. Raises MaterialInvalid for a bundle the strict reader refuses.

    Returns {"doc": the report, "report_bytes": the file, "recording": the recording bytes or None, "results", "levels", "problems"
    (the report's own, empty when it is valid), "complete": level read reached, "auto": auto.summary(...)}."""
    problems = material.validate(bundle)
    if problems:
        raise MaterialInvalid(problems)
    link, window, rec = bundle["link"], bundle["window"], bundle["recording"]
    created = date.fromisoformat(bundle["created"])
    clock = datetime(created.year, created.month, created.day, 10, tzinfo=timezone.utc)     # the builder's "now": the Hub's day, 10:00 UTC (the age of a saved test is judged against it)
    data = rec["text"].encode("ascii") if rec["text"] is not None else None
    record = {"state": "summary", "report_id": bundle["report_id"], "started": (clock - timedelta(seconds=window["seconds"])).isoformat(),
              "consent_version": bundle["permission"]["text_version"], "recording_chosen": True,
              "recording_failed": rec["state"] if data is None and rec["state"] in ("unavailable", "not_supported", "failed") else None,
              "marks": [], "phases": material.phases_of(window), "display": {"state": "not_asked", "code": None, "temp": None},
              "country": None, "photo": None, "saved": None, "ended": None, "step": tester_run.FIRST_STEP, "notified": False,
              "link": "opentherm" if link == "opentherm" else "ems"}
    readiness = bundle["documents"].get("readiness") or {}
    run = tester_run.TesterRun(None, SimpleNamespace(entry_id="material", title="material"), lambda: None,
                               lambda: SimpleNamespace(status={"readiness": readiness}), clock=lambda: clock)
    run._today = lambda: created        # the Hub's day, not the local day of the machine that builds
    run.book = SimpleNamespace(data={"tester_code": bundle["tester_code"], "tests": {}, "runs": {}}, write=lambda: None)
    run.record = tester_run._clean_record(record)
    run.via = auto.VIA
    names = tester_run.pick_names(created.isoformat(), set(), opentherm=link == "opentherm")
    raw = _raw(bundle)
    # the test is what the Hub already saved of an attended test (the wizard's own, the EMS+ probe, the OpenTherm test), read as the page reads it;
    # nothing is made for the report. Without such a document the test is "none".
    collected = {"raw": raw, "status": _status(bundle), "data": data, "today": created, "test": run._test(raw, record_seen=False)[0], "photo": None,
                 "names": names}
    doc, results, levels, problems = run._build(collected, names)
    if doc.get("software"):
        doc["software"]["integration"] = None        # the version of the integration is that of the machine that builds it: the Hub's page says null too (D11)
        problems = fmt.validate(doc)
    return {"doc": doc, "report_bytes": fmt.dump(doc), "recording": data, "results": results, "levels": levels, "problems": problems,
            "complete": levels["read"],
            "auto": auto.summary(results, doc, auto.VIA, data, bundle["boiler_pick"], bundle["recognised"])}
