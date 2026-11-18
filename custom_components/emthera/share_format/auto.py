"""The rules for a report that came in by itself (via "auto"; TESTER-AUTO-1). The data is auto.json; this is the code.

One function judges: the same rules of the report's link (rules.py, completeness.json) run as always, then `adjust` changes only
what the way in `auto` changes, `levels_of` caps the level, and `summary` says it all in a machine-readable way:

- the three moment buttons are not needed (the table never needed them: no taps = seen, rules.chk_marks_plausible);
- the typed display answer does not block level read for an automatic report; the result then says that the independent display
  check is missing (`independent_display_check: "missing"`). OWNER DECISION 4, NOT ANSWERED: the one switch below;
- a program can never raise an automatic report above level read (CAP);
- the user's own pick of the boiler travels as data (`summary`), it never changes a rule or a level;
- a recording that holds only the boiler's own telegrams (material.filter_recording) cannot show the damaged share of the whole
  cable by itself: the filter's header carries the counts of what it removed and the rule `frames_clean` reads them. Nothing else
  of the rule table changes for a filtered recording (see the report TESTER-AUTO-1 for what was run, rule by rule).

Standard library only; loaded by the tools of the owner's computer by path, like the rest of share_format.
"""
import copy
from pathlib import Path

from . import fmt, material, recording, rules

# ---- the switch of decision 4 (one line changes it) -------------------------------------------------------------------------------
TYPED_DISPLAY_NEEDED_FOR_AUTO = False

VIA = "auto"
_CACHE = {}


def table():
    if "table" not in _CACHE:
        _CACHE["table"] = fmt.load_json_file(Path(__file__).with_name("auto.json"))
    return _CACHE["table"]


def version():
    return table()["version"]


def _display_unasked(doc):
    return (doc.get("human") or {}).get("display_state", "not_asked") == "not_asked"


def _frames_clean(result, rec_bytes, head):
    """frames_clean over the WHOLE recording of a filtered one: the damaged frames that were kept plus those the filter removed (it
    cannot tell whose they were), over every frame. The rule's own limit; the result says what it counted."""
    info, _ = recording.read_recording(rec_bytes)
    if info is None:
        return result
    limit = fmt.completeness()["rules"]["frames_clean"]["params"]["ratio"]
    damaged = info["damaged"] + head["removed_damaged"]
    frames = info["received"] + info["transmitted"] + info["damaged"] + head["removed_frames"] + head["removed_damaged"]
    ratio = damaged / frames if frames else 0.0
    detail = {"damaged_pct": f"{ratio * 100:.2f}", "damaged": damaged, "filtered": True, "frames": frames}
    return dict(result, state="seen" if ratio <= limit else "untrusted", detail=detail)


def adjust(results, doc, via, rec_bytes=None):
    """The rule results for the way in `via`: unchanged for anything but "auto". Never raises a result: a rule only goes from
    missing to not_checked (and says why) or is recomputed over the whole recording of a filtered one."""
    if via != VIA:
        return results
    out = []
    head = material.filter_header(rec_bytes) if rec_bytes is not None else None
    for r in results:
        r = copy.deepcopy(r)
        if r["id"] in table()["display_rules"] and not TYPED_DISPLAY_NEEDED_FOR_AUTO and r["state"] == "missing" and _display_unasked(doc):
            r["state"] = "not_checked"
            r["detail"] = {**r["detail"], "reason": "auto_no_typed_display", "blocks": False, "independent_display_check": "missing"}
        elif r["id"] == "frames_clean" and head is not None and r["state"] in ("seen", "untrusted"):
            r = _frames_clean(r, rec_bytes, head)
        out.append(r)
    return out


def levels_of(results, via):
    """{level: bool}: rules.levels_of, and an automatic report is never above CAP (a program never raises it further)."""
    levels = rules.levels_of(results)
    if via == VIA:
        for level in rules.LEVEL_ORDER[rules.LEVEL_ORDER.index(table()["cap"]) + 1:]:
            levels[level] = False
    return levels


def display_check(results, doc):
    """"missing" (the way in auto skipped it), "needed" (the switch asks for it and it is not there) or "done" (a typed answer was compared)."""
    rows = [r for r in results if r["id"] in table()["display_rules"]]
    if any(r["detail"].get("independent_display_check") == "missing" for r in rows):
        return "missing"
    if TYPED_DISPLAY_NEEDED_FOR_AUTO and _display_unasked(doc):
        return "needed"
    return "done" if not _display_unasked(doc) else "missing"


def attended_test(doc):
    """What the report says of an attended test, machine-readable: "passed" (a saved test of the Hub, passed), "present" (one that did not pass)
    or "none". It changes no level here: the cap holds whatever the test says."""
    test = doc.get("test") or {}
    if test.get("kind", "none") == "none":
        return "none"
    return "passed" if test.get("outcome") == "passed" else "present"


def summary(results, doc, via, rec_bytes=None, pick=None, recognised=None):
    """The machine-readable part of an automatic result (None for any other way in): what was not checked and why, the cap, the
    switches and the user's pick, which is data only."""
    if via != VIA:
        return None
    head = material.filter_header(rec_bytes) if rec_bytes is not None else None
    return {
        "via": VIA, "rules_version": version(), "base_table": table()["base_table"], "cap": table()["cap"],
        "independent_display_check": display_check(results, doc),
        "attended_test": attended_test(doc),
        "recording": {"filtered": head is not None, "removed": head,
                      "whole": rec_bytes is not None and head is None and doc["link"] != "opentherm",
                      "values_only": rec_bytes is not None and doc["link"] == "opentherm"},
        "pick": pick, "recognised": recognised,
        "switches": {"TYPED_DISPLAY_NEEDED_FOR_AUTO": TYPED_DISPLAY_NEEDED_FOR_AUTO,
                     "BOILER_TELEGRAMS_ONLY": material.BOILER_TELEGRAMS_ONLY},
    }


def lines(auto, lang, lacks=()):
    """The sentences an answer adds for an automatic report, in the language asked for (plain words; every one is in auto.json)."""
    ph = table()["phrases"]
    out = [ph["came_in"][lang]]
    if auto["independent_display_check"] == "missing":
        out.append(ph["display_not_checked"][lang])
    elif auto["independent_display_check"] == "needed":
        out.append(ph["display_needed"][lang])
    if auto.get("attended_test") == "passed":
        out.append(ph["test_passed"][lang])
    if auto["recording"]["filtered"]:
        out.append(ph["recording_boiler_only"][lang])
    elif auto["recording"]["whole"]:
        out.append(ph["recording_whole"][lang])
    elif auto["recording"].get("values_only"):
        out.append(ph["recording_opentherm"][lang])
    if auto.get("recognised") is True:
        out.append(ph["recognised"][lang])
    elif auto.get("recognised") is False:
        out.append(ph["not_recognised"][lang])
    pick = auto.get("pick")
    if pick is not None:
        name = pick["list_id"] if pick["source"] == "list" else f"{pick['brand']} {pick['model']}"
        out.append(ph["pick"][lang].format(boiler=name))
    elif auto.get("recognised") is False:
        out.append(ph["no_pick"][lang])
    if lacks:
        out.append(ph["lacks"][lang].format(list=", ".join(ph["words"][lang][k] for k in lacks)))
        out.append(ph["waits"][lang])
    out.append(ph["cap"][lang])
    return out
