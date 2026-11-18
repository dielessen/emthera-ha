"""The tester's one run on an OpenTherm boiler, in Home Assistant (OT-RUN-2A): what the Hub's documents say, as parts of the report.

The Hub's recorder for an OpenTherm boiler (`POST /opentherm/run/start|stop`, `GET /status/opentherm/run`, the same with
`?group=0..7` for the summary per state, `GET /opentherm/run/log`) keeps the numbers; the link document (`GET /status/boiler/link`)
says who the boiler is; the attended boiler test (`GET /config/boiler-link/test`) is the test the Hub keeps. This module only turns
those documents into the members of the report format (`link_data.opentherm`, `boiler.opentherm`, `test`, the recording's status)
and the readiness items; tester_run.py does the run itself. Pure functions: no request, no clock, nothing is stored here. Whatever
the Hub says that the format does not hold is dropped by the allow-list (fmt.project) like everything else.
"""
from __future__ import annotations

OT_LINK = "/status/boiler/link"
OT_RUN = "/status/opentherm/run"
OT_TEST = "/config/boiler-link/test"
GROUPS = 8                      # the summary per state comes in 8 documents of 16 data ids each
RUN_SECONDS = 1800              # a run ends by itself after 30 minutes
NEEDED_S = 1500                 # the clock line asks for 25 minutes, as it does for a bus recording
MAX_STATE_S = 7200
STATES = ("rest", "heating", "hot_water")
# What the Hub's own run document says, in the words of the recording's status (the one status shape the run already knows).
RUN_STATE = {"running": "recording", "stopped": "ready", "idle": "idle"}
IDENTITY_IDS = (3, 125, 127)
# After a stop the Hub's run document says `"settling": true` for a fraction of a second: the numbers and the log are final once it is gone.
SETTLE_EVERY_S = 0.4            # so the run is read again every 0.4 seconds ...
SETTLE_READS = 25               # ... at most 25 more times (10 seconds), while the run still counts or settles
TEST_STATE = {"passed": "passed", "failed": "failed", "aborted": "stopped"}

# The sentences of the run on an OpenTherm boiler, English and Dutch (the owner's words: ketel, thermostaat, warmwaterkraan, de Hub). Kept here
# beside tester_run.TEXT, which the Hub's own page copies and pins; the page for OpenTherm takes these from here.
TEXT = {
    "en": {
        "family.opentherm": "OpenTherm",
        "ready.ot_thermostat": "The Hub only reads your boiler and changes nothing. You do not have to remove anything.",
        "ready.ot_run_busy": "The Hub is already recording a run. Finish or delete it first, or wait until it ends by itself (at most 30 minutes).",
        "line.ot_boiler_maker": "maker code {member}", "line.ot_boiler_type": "type {type}",
        "line.ot_values": "What the boiler reported, at rest, while heating and while making hot water: {names}.",
        "line.ot_states": "The Hub saw the boiler at rest for {rest} {rest:minute|minutes}, heating for {heating} {heating:minute|minutes} and making hot water for {hot_water} {hot_water:minute|minutes}.",
        "line.ot_log": "The log of the values as they changed: {entries} changes in {minutes} {minutes:minute|minutes}. It holds no room temperatures.",
        "line.ot_no_log": "No log of the changing values. Your report can still be complete; we just cannot read it again later with newer software.",
        "lost.ot_run": "The Hub restarted during your run, so the recording was lost and cannot be made again for this run. The report is marked incomplete.",
        "lost.ot_run.action": "Start a new run and keep the Hub powered until the run is finished.",
        "msg.ready.ot": "The Hub has watched your boiler for long enough. Open Settings, Installation, Tester program and finish your report. Nothing is sent.",
    },
    "nl": {
        "family.opentherm": "OpenTherm",
        "ready.ot_thermostat": "De Hub leest alleen je ketel en verandert niets. Je hoeft niets los te halen.",
        "ready.ot_run_busy": "De Hub neemt al een run op. Rond die eerst af of verwijder hem, of wacht tot hij vanzelf stopt (hooguit 30 minuten).",
        "line.ot_boiler_maker": "merkcode {member}", "line.ot_boiler_type": "type {type}",
        "line.ot_values": "Wat de ketel meldde, in rust, tijdens het verwarmen en tijdens het maken van warm water: {names}.",
        "line.ot_states": "De Hub zag de ketel {rest} {rest:minuut|minuten} in rust, {heating} {heating:minuut|minuten} verwarmen en {hot_water} {hot_water:minuut|minuten} warm water maken.",
        "line.ot_log": "Het logboek van de waarden zoals ze veranderden: {entries} wijzigingen in {minutes} {minutes:minuut|minuten}. Er staan geen kamertemperaturen in.",
        "line.ot_no_log": "Geen logboek van de veranderende waarden. Je melding kan toch compleet zijn; we kunnen hem later alleen niet met nieuwere software opnieuw lezen.",
        "lost.ot_run": "De Hub is tijdens je run opnieuw gestart, daarom is de opname verloren gegaan en kan ze voor deze run niet opnieuw worden gemaakt. De melding wordt als onvolledig gemarkeerd.",
        "lost.ot_run.action": "Start een nieuwe run en laat de Hub aan staan tot de run klaar is.",
        "msg.ready.ot": "De Hub heeft je ketel lang genoeg bekeken. Open Instellen, Installatie, Testerprogramma en rond je melding af. Er wordt niets verstuurd.",
    },
}


def _dict(v):
    return v if type(v) is dict else {}


def _list(v):
    return v if type(v) is list else []


def _int(v, low=0, high=2 ** 53):
    return v if type(v) is int and low <= v <= high else None


def group_path(n):
    return f"{OT_RUN}?group={n}"


def is_link(doc):
    """True when the link document is the one of an OpenTherm Hub."""
    return type(doc) is dict and doc.get("link") == "opentherm"


def run_state(doc):
    """The Hub's run state in the words of this module: running, stopped, idle, or none (no OpenTherm link, or unreadable)."""
    state = _dict(doc).get("state")
    return state if state in ("running", "stopped", "idle") else "none"


def recording_status(doc):
    """The Hub's run as the status of a recording (state, seconds, frames = entries of the change log, dropped)."""
    doc = _dict(doc)
    state = RUN_STATE.get(doc.get("state"), "not_supported")
    log = _dict(doc.get("log"))
    return {"state": state, "seconds": min(_int(doc.get("seconds")) or 0, RUN_SECONDS), "frames": _int(log.get("entries")) or 0,
            "polls": 0, "dropped": _int(log.get("dropped")) or 0, "bytes": _int(log.get("bytes")) or 0}


def unsettled(doc):
    """True while the Hub's run document still counts (`running`) or says `settling`: its numbers and its log are not final yet."""
    doc = _dict(doc)
    return doc.get("state") == "running" or doc.get("settling") is True


def states_seconds(doc):
    """{rest, heating, hot_water}: whole seconds the boiler's own status spent in each state, or None before the first answer."""
    states = _dict(_dict(doc).get("states"))
    out = {k: _int(states.get(k), 0, MAX_STATE_S) for k in STATES}
    return out if all(v is not None for v in out.values()) else None


def settled(doc):
    """The boiler answered all three questions about itself (a value, no value, or unknown): none is still untried."""
    support = {r.get("id"): r.get("state") for r in _list(_dict(doc).get("support")) if type(r) is dict}
    return all(support.get(i) not in (None, "untried") for i in IDENTITY_IDS)


def identity(link_doc, run_doc):
    """`boiler.opentherm`: who the boiler says it is. What it did not say is null, never a guess."""
    ident = _dict(_dict(link_doc).get("identity"))
    ot = ident.get("ot")
    hundredths = round(ot * 100) if type(ot) in (int, float) and not isinstance(ot, bool) and 0 <= ot <= 99.99 else None
    digest = _int(ident.get("digest"), 1, 255)
    return {"member": _int(ident.get("member"), 0, 255), "product_type": _int(ident.get("type"), 0, 255),
            "product_version": _int(ident.get("version"), 0, 255), "ot_version_hundredths": hundredths,
            "settled": settled(run_doc) if run_doc is not None else digest is not None,
            "digest": f"{digest:02x}" if digest is not None else None}


def by_state(groups):
    """The numbers per state of every data id that was read in any state, in id order (the eight group documents)."""
    rows = {}
    for doc in _list(groups):
        for row in _list(_dict(doc).get("by_state")):
            row = _dict(row)
            if type(row.get("id")) is int and 0 <= row["id"] <= 127 and any(row.get(s) is not None for s in STATES):
                rows[row["id"]] = {"id": row["id"], **{s: row.get(s) for s in STATES}}
    return [rows[i] for i in sorted(rows)]


def link_data(run_doc, groups):
    """`link_data.opentherm`: the Hub's run document, and the numbers per state when the eight group documents were read."""
    doc = _dict(run_doc)
    out = {"support": _list(doc.get("support")), "summary": _list(doc.get("summary")), "limit": _dict(doc.get("limit")),
           "config": _dict(doc.get("config")), "fault": _dict(doc.get("fault")), "line": doc.get("line") if type(doc.get("line")) is dict else None}
    seconds = states_seconds(doc)
    if seconds is not None and _list(groups):
        out["states"] = seconds
        out["by_state"] = by_state(groups)
    return out


def test_part(test_doc, link_doc, today, wall, seen_test, identity_key, firmware, max_age_s):
    """(the report's `test`, the day of the test or None): the attended boiler test the Hub keeps. Usable only for the same boiler and
    firmware (`seen_test`: when the test was first seen with them) and not older than max_age_s; else no test."""
    none = {"kind": "none", "source": "none", "at_day": None, "outcome": "none", "detail": "", "steps": [], "readback": None,
            "reverted": None, "probe": None, "opentherm": None}
    doc = _dict(test_doc)
    state = TEST_STATE.get(doc.get("state"))
    at = doc.get("at")
    if state is None or type(at) not in (int, float) or isinstance(at, bool) or at <= 0 or wall < at or wall - at > max_age_s:
        return none, None
    known = _dict(seen_test)
    if known.get("at") == int(at) and (known.get("boiler") != identity_key or known.get("firmware") != firmware):
        return none, None  # another boiler or other firmware since the test was first seen
    from datetime import datetime, timezone
    day = datetime.fromtimestamp(at, timezone.utc).date().isoformat()
    rise = doc.get("rise_c")
    reason = doc.get("reason")
    return {"kind": "ot_attended", "source": "testerprogram", "at_day": day, "outcome": state,
            "detail": reason if state != "passed" and type(reason) is str else "", "steps": [], "readback": None,
            "reverted": doc.get("off_confirmed") if type(doc.get("off_confirmed")) is bool else None, "probe": None,
            "opentherm": {"state": state, "asked_c": _int(doc.get("asked_c"), 0, 127),
                          "flame_seen": doc.get("flame_seen") if type(doc.get("flame_seen")) is bool else None,
                          "rise_c": max(0, min(127, round(rise))) if type(rise) in (int, float) and not isinstance(rise, bool) else None,
                          "off_confirmed": doc.get("off_confirmed") if type(doc.get("off_confirmed")) is bool else None,
                          "off_problem": bool(doc.get("off_problem")) if "off_problem" in doc else None}}, day


def test_seen_key(test_doc):
    """The moment (whole seconds) the Hub's test finished: what a stored 'first seen with this boiler' note is keyed on."""
    at = _dict(test_doc).get("at")
    return int(at) if type(at) in (int, float) and not isinstance(at, bool) and at > 0 else None


def readiness(link_doc, run_doc):
    """(items, blocking) of the readiness check for an OpenTherm Hub: the boiler answers, and the Hub's recorder is free.
    An item is {id, ok, text}; text is a key of tester_run.TEXT."""
    link, run = _dict(link_doc), _dict(run_doc)
    items, blocking = [], False
    contact = link.get("contact")
    if contact == "in_contact":
        items.append({"id": "boiler", "ok": True, "text": "ready.boiler", "family": "opentherm"})
    else:
        items.append({"id": "boiler", "ok": False, "text": "ready.boiler_silent"})
        blocking = True
    if run.get("state") == "running":
        items.append({"id": "memory", "ok": False, "text": "ready.ot_run_busy", "state": "running"})
        blocking = True
    else:
        items.append({"id": "memory", "ok": True, "text": "ready.memory", "state": "idle"})
    return items, blocking
