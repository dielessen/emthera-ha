"""The completeness rules of the report format "boiler-share 2": ONE evaluator for everyone.

completeness.json (beside this file) is the rule table per boiler link; this module is the code that applies it to a report.
The integration evaluates a run's report with it before the tester sees the summary, and the owner's computer
(tools/emsplus/check_share2.py) loads this very file: there is no second evaluator. A rule judges only what it is given;
reading a recording and running the host replay are the caller's work (recording.py; tools/emsplus/check_share.py).
Standard library only.
"""
import hashlib
import re

from . import fmt, recording

LEVEL_ORDER = ("send", "read", "tested", "verified")
STATES = ("seen", "missing", "untrusted", "not_checked")


# What the bus must show before a phase counts as seen (seconds in that state, from the replay's time line). A phase
# shorter than this is a glitch or a single frame, not the boiler doing it. One sample counts for at most two time
# line steps, so a silent stretch of the bus is never credited to the state before it.
PHASE_MIN_S = {"rest": 60, "heating": 60, "hot_water": 30}
MARK_WINDOW_BEFORE_S, MARK_WINDOW_AFTER_S, MARK_NEAR_END_S = 60, 600, 60
PHASE_NAMES = ("rest", "heating", "hot_water")


def _sample_phases(s):
    """The phases one time line sample shows: heating and hot water as the firmware's boiler view says, rest when both
    are explicitly off and the burner is not on (a sample without values shows nothing)."""
    out = set()
    if s.get("heating") is True:
        out.add("heating")
    if s.get("hot_water") is True:
        out.add("hot_water")
    if s.get("heating") is False and s.get("hot_water") is False and s.get("flame") is not True:
        out.add("rest")
    return out


def phase_summary(line):
    """What the recording's time line shows: per phase the seconds in that state, the first second it began and the
    seconds (from the first record) at which it was active, plus the length covered. Pure data; the checks read it."""
    samples = [s for s in line["samples"] if isinstance(s, dict) and isinstance(s.get("ms"), int)]
    first, last = line.get("first_ms"), line.get("last_ms")
    if not isinstance(first, int) or not isinstance(last, int) or not samples:
        return {"span_s": 0, "step_s": 60, "phases": {k: {"seconds": 0, "first_s": None, "observed": False} for k in PHASE_NAMES},
                "active": {k: [] for k in PHASE_NAMES}}
    step = int(line.get("step_ms") or 60000)
    seconds = {k: 0.0 for k in PHASE_NAMES}
    firsts = {k: None for k in PHASE_NAMES}
    active = {k: [] for k in PHASE_NAMES}
    for i, s in enumerate(samples):
        end = samples[i + 1]["ms"] if i + 1 < len(samples) else last
        span = min(max(0, end - s["ms"]), 2 * step)
        for k in _sample_phases(s):
            seconds[k] += span / 1000
            if firsts[k] is None:
                firsts[k] = round((s["ms"] - first) / 1000)
            active[k].append(round((s["ms"] - first) / 1000))
    return {"span_s": max(0, (last - first) // 1000), "step_s": step // 1000,
            "phases": {k: {"seconds": round(seconds[k]), "first_s": firsts[k], "observed": seconds[k] >= PHASE_MIN_S[k]}
                       for k in PHASE_NAMES},
            "active": active}


def mark_problems(doc, phases):
    """The marks of the run that the bus does not bear out: a tester who says he turned the thermostat up (or opened a
    tap) must be followed, soon, by the boiler heating (or making hot water). The recording is the newest part of the
    run, so its start is aligned to the run's length. A mark outside the recording, or too near its end, is not judged."""
    run = doc["run"]
    span = phases["span_s"]
    offset = max(0, run["minutes"] * 60 - span)
    out = []
    for kind, phase in (("heat_up", "heating"), ("hot_water", "hot_water")):
        for m in run["marks"]:
            if m["kind"] != kind:
                continue
            at = m["at_s"] - offset
            if at < -MARK_WINDOW_BEFORE_S or at > span - MARK_NEAR_END_S:
                continue
            if not any(at - MARK_WINDOW_BEFORE_S <= t <= at + MARK_WINDOW_AFTER_S for t in phases["active"][phase]):
                out.append(f"mark {kind} without {phase.replace('_', ' ')} on the bus")
                break
    return out


class Context:
    """What the rules read: the report, the files that belong to it and what the replay says.

    The caller reads the recording (recording.read_recording) and, where it has the host replay, runs it: the rules
    only judge. `replay_runner` is called once, and only when the recording was read; `timeline_runner() -> (time line, why)`
    (the host replay's `--timeline`, the tools only) is called once, and only when the replay ran."""

    def __init__(self, doc, rec_bytes, photo_bytes, replay_runner=None, rec=None, timeline_runner=None):
        self.doc = doc
        self.link = doc["link"]
        self.ems = (doc.get("link_data") or {}).get("ems")
        self.ot = (doc.get("link_data") or {}).get("opentherm")
        self.rec_bytes, self.photo_bytes = rec_bytes, photo_bytes
        self.rec, self.rec_problems = (None, [])
        self.otlog = None          # the OpenTherm change log (otrec 1), read when the report's recording is one
        self.replay, self.replay_why = None, None
        self.timeline, self.timeline_why, self.phases = None, None, None
        if doc["recording"]["kind"] == "otrec 1":  # an OpenTherm change log is no bus recording: its own reader
            if rec_bytes is not None:
                self.otlog, self.rec_problems = recording.read_otrec(rec_bytes)
        elif rec is not None:  # a reading made by the caller (a live reading while the recording still runs)
            self.rec = rec
        elif rec_bytes is not None:
            self.rec, self.rec_problems = recording.read_recording(rec_bytes)
        if self.rec is not None and replay_runner is not None:
            self.replay, self.replay_why = replay_runner()
            if self.replay is not None and timeline_runner is not None:
                self.timeline, self.timeline_why = timeline_runner()
                if self.timeline is not None:
                    self.phases = phase_summary(self.timeline)
        self.counts = {}
        if self.rec is not None:
            self.counts = {int(k.split(":")[1], 16): n for k, n in self.rec["telegrams"].items() if k.startswith("08:")}

    @property
    def chosen(self):
        return self.doc["recording"]["chosen"] and self.doc["recording"]["file"] is not None

    def view(self):
        """(decoded values, where they came from): the replay of the recording first, then the report's own view."""
        if self.replay is not None:
            view = (self.replay.get("final") or {}).get("view")
            if isinstance(view, dict):
                return view, "replay"
        if self.ems and self.ems.get("view"):
            return self.ems["view"], "device"
        return None, None


def _norm(code):
    return re.sub(r"\s", "", code or "").upper()


def _types_text(types):
    return ", ".join(f"{t:#04X}".replace("0X", "0x") for t in types)


# ---- the checks: (state, detail) -----------------------------------------------------------------------------------------

def _need_recording(c):
    """None when the recording was read; else the (state, detail) of a rule that needs it."""
    if c.rec is not None:
        return None
    if not c.chosen:
        return "missing", {"reason": "no_recording"}
    return "not_checked", {"reason": "recording_file_not_given"}


def chk_consent_yes(c, p):
    consent = c.doc.get("consent")
    return ("seen", {}) if consent and consent.get("yes") is True else ("missing", {})


def chk_link_known(c, p):
    return ("seen", {"link": c.link}) if c.link != "unknown" else ("missing", {"link": c.link})


def chk_software_versions(c, p):
    s = c.doc["software"]
    ok = s["firmware"] is not None and (not p.get("require_table") or s["table"] is not None)
    return ("seen" if ok else "missing"), {}


def chk_identity_ems(c, p):
    b = c.doc["boiler"]
    known = b["product"] is not None and b["version"] is not None
    detail = {"product": b["product"], "version": b["version"], "source": None}
    if not known:
        return "missing", detail
    if c.rec is None:
        detail["source"] = "device"
        detail["compared_with_recording"] = False
        return "seen", detail
    like = {"boiler": b, "telegrams": (c.ems or {}).get("telegrams") or {"devices": []}}
    like["telegrams"].setdefault("devices", [])
    version = (c.replay or {}).get("boiler_version")
    heard = c.counts.get(0x02, 0) > 0 or version is not None
    if recording.identity_conflict(like, c.rec):
        detail["source"] = "recording" if heard else None
        return "untrusted", detail
    if version is not None and (version.get("product") != b["product"] or version.get("version") != b["version"]):
        detail["source"] = "recording"
        detail["replay_product"], detail["replay_version"] = version.get("product"), version.get("version")
        return "untrusted", detail
    detail["source"] = "recording" if heard else "device"
    return "seen", detail


def chk_identity_ot(c, p):
    o = c.doc["boiler"].get("opentherm") or {}
    ok = bool(o.get("settled"))  # the boiler answered all three questions; a part it does not give is its answer too
    return ("seen" if ok else "missing"), {"member": o.get("member"), "source": "device" if ok else None}


def chk_recording_chosen(c, p):
    r = c.doc["recording"]
    ok = r["chosen"] and r["file"] is not None and r["state"] == "ready"
    return ("seen" if ok else "missing"), {"chosen": r["chosen"], "state": r["state"]}


def chk_recording_length(c, p):
    needed = p["min_s"] // 60
    if c.rec is None:
        state, detail = _need_recording(c)
        detail.update({"minutes": c.doc["recording"]["seconds"] // 60, "needed": needed})
        return state, detail
    seconds = c.rec["seconds"]
    return ("seen" if seconds >= p["min_s"] else "missing"), {"minutes": seconds // 60, "seconds": seconds, "needed": needed}


def _scaled_need(c, p):
    return max(2, -(-p["min_per_window"] * min(c.rec["seconds"], p["window_s"]) // p["window_s"]))


def chk_telegram_counts(c, p):
    missing = _need_recording(c)
    if missing:
        missing[1].update({"have": 0, "need": p["min_per_window"], "list": ""})
        return missing
    need = _scaled_need(c, p)
    have = {t: c.counts.get(t, 0) for t in p["types"]}
    ok = all(n >= need for n in have.values())
    return ("seen" if ok else "missing"), {"need": need, "have": min(have.values()),
                                           "list": ", ".join(f"{t:#04X}".replace("0X", "0x") + f" {n}x" for t, n in have.items()),
                                           "counts": {f"{t:#04x}": n for t, n in have.items()}}


def chk_telegrams_answered(c, p):
    missing = _need_recording(c)
    if missing:
        missing[1]["list"] = _types_text(p["types"])
        return missing
    silent = [t for t in p["types"] if c.counts.get(t, 0) == 0]
    return ("seen" if not silent else "missing"), {"list": _types_text(silent or p["types"]),
                                                   "answered": [f"{t:#04x}" for t in p["types"] if t not in silent]}


def chk_telegram_seen(c, p):
    missing = _need_recording(c)
    if missing:
        return missing
    silent = [t for t in p["types"] if c.counts.get(t, 0) == 0]
    return ("seen" if not silent else "missing"), {"absent": [f"{t:#04x}" for t in silent]}


def chk_damaged_max(c, p):
    missing = _need_recording(c)
    if missing:
        missing[1]["damaged_pct"] = "0.00"
        return missing
    ratio = c.rec["damaged_ratio"]
    if ratio is None:  # a live reading: the device does not count damaged frames before the recording is read
        return "not_checked", {"damaged_pct": "0.00", "reason": "recording_not_read_yet"}
    return ("seen" if ratio <= p["ratio"] else "untrusted"), {"damaged_pct": f"{ratio * 100:.2f}", "damaged": c.rec["damaged"]}


def chk_plausible_ems(c, p):
    view, source = c.view()
    if view is None:
        state, detail = _need_recording(c) or ("missing", {})
        return state, dict(detail, list="", value="", source=None)
    bad = [(k, view[k]) for k, (low, high) in p["ranges"].items() if type(view.get(k)) is int and not low <= view[k] <= high]
    seen = [k for k in p["ranges"] if type(view.get(k)) is int]
    absent = [k for k in p["minimum_seen"] if view.get(k) is None]
    detail = {"source": source, "list": ", ".join(seen), "value": "", "absent": absent,
              "out_of_range": [k for k, _ in bad]}
    if bad:
        k, v = bad[0]
        detail["value"] = f"{k} {v}"
        return "untrusted", detail
    return ("missing" if absent else "seen"), detail


def chk_phase_seen(c, p):
    claimed = p["phase"] in c.doc["run"]["phases_seen"]
    states = (c.ot or {}).get("states")
    if states is not None:  # OpenTherm: the seconds the boiler's own status spent in each state (not a claim)
        seconds = states[p["phase"]]
        return ("seen" if seconds >= PHASE_MIN_S[p["phase"]] else "missing"), {"phase": p["phase"], "source": "boiler", "claimed": claimed,
                                                                              "seconds": seconds}
    if c.phases is None:  # no time line: the device's claim stands, and the result says it is only a claim
        return ("seen" if claimed else "missing"), {"phase": p["phase"], "source": "device_claim"}
    ph = c.phases["phases"][p["phase"]]
    return ("seen" if ph["observed"] else "missing"), {"phase": p["phase"], "source": "recording", "claimed": claimed,
                                                       "seconds": ph["seconds"], "first_s": ph["first_s"]}


def _typed_text(h):
    parts = [x for x in (h.get("display_code_typed"), f"{h['display_temp_typed']} degrees"
                         if h.get("display_temp_typed") is not None else None) if x]
    return " and ".join(parts)


def chk_display_typed(c, p):
    """Every answer is valid (a code, a temperature, both, dark, no display); only no answer is missing."""
    h = c.doc.get("human") or {}
    state = h.get("display_state", "not_asked")
    return ("seen" if state != "not_asked" else "missing"), {"state": state, "typed": _typed_text(h)}


def chk_display_matches_ems(c, p):
    """Compares what can be compared: a typed code with the decoded code; a typed temperature with the Hub's own flow
    temperature within the tolerance. A dark or absent display gives nothing to compare: not_checked, not blocking."""
    h = c.doc.get("human") or {}
    state = h.get("display_state", "not_asked")
    view, source = c.view()
    detail = {"state": state, "source": source, "typed": _typed_text(h), "read": ""}
    if state == "not_asked":
        return "missing", detail
    if state in ("dark", "no_display"):
        detail.update({"reason": "nothing_to_compare", "blocks": False})
        return "not_checked", detail
    view = view or {}
    verdicts, reads = [], []
    if h.get("display_code_typed"):
        read = view.get("display_code")
        if not read:
            return "missing", detail
        reads.append(_norm(read))
        verdicts.append(_norm(h["display_code_typed"]) == _norm(read))
    if h.get("display_temp_typed") is not None:
        flow = view.get("flow_centi_c")
        if type(flow) is not int:
            return "missing", detail
        reads.append(f"{flow / 100:.0f} degrees")
        detail["difference_c"] = round(abs(h["display_temp_typed"] - flow / 100), 2)
        verdicts.append(detail["difference_c"] <= p["temperature_tolerance_c"])
    detail["read"] = " and ".join(reads)
    return ("seen" if all(verdicts) else "untrusted"), detail


def chk_devices_listed(c, p):
    devices = (c.ems or {}).get("telegrams", {}).get("devices", [])
    ok = any(d["bus_address"] == p["boiler_address"] for d in devices)
    return ("seen" if ok else "missing"), {"count": len(devices)}


def chk_fields_read(c, p):
    fields = (c.ems or {}).get("fields", [])
    minutes = c.doc["run"]["minutes"]
    ok = len(fields) >= p["min_fields"] and minutes >= p["min_minutes"]
    return ("seen" if ok else "missing"), {"count": len(fields), "minutes": minutes}


def chk_limit_read_ems(c, p):
    limit = ((c.ems or {}).get("limit") or {}).get("c")
    return ("seen" if limit is not None else "missing"), {"limit": limit if limit is not None else ""}


def chk_photo_declared(c, p):
    return ("seen" if (c.doc.get("human") or {}).get("photo") else "missing"), {}


def _jpeg_metadata(data):
    """The marker names of a JPEG that carry metadata (anything but APP0/JFIF), or None when it is no JPEG."""
    if data[:2] != b"\xff\xd8":
        return None
    found, i = [], 2
    while i + 4 <= len(data):
        if data[i] != 0xFF:
            return found
        marker = data[i + 1]
        if marker == 0xFF:
            i += 1
            continue
        if marker in (0xD8, 0x01) or 0xD0 <= marker <= 0xD7:
            i += 2
            continue
        if marker == 0xDA or marker == 0xD9:
            return found
        length = int.from_bytes(data[i + 2:i + 4], "big")
        if marker == 0xFE or 0xE1 <= marker <= 0xEF:
            found.append(f"FF{marker:02X}")
        i += 2 + max(length, 2)
    return found


def chk_photo_clean(c, p):
    photo = (c.doc.get("human") or {}).get("photo")
    if not photo:
        return "missing", {}
    if c.photo_bytes is None:
        return "not_checked", {"reason": "photo_file_not_given"}
    meta = _jpeg_metadata(c.photo_bytes)
    if meta is None:
        return "untrusted", {"reason": "not_a_jpeg"}
    return ("seen" if not meta else "untrusted"), {"metadata_segments": meta}


def chk_test_passed(c, p):
    t = c.doc["test"]
    ok = t["kind"] in p["kinds"] and t["outcome"] == "passed" and t["source"] in ("wizard", "testerprogram")
    return ("seen" if ok else "missing"), {"kind": t["kind"], "outcome": t["outcome"]}


def chk_test_passed_ot(c, p):
    t = c.doc["test"]
    ok = t["kind"] == "ot_attended" and (t.get("opentherm") or {}).get("state") == "passed" \
        and t["source"] in ("wizard", "testerprogram")
    return ("seen" if ok else "missing"), {"kind": t["kind"], "outcome": t["outcome"]}


def chk_active_days(c, p):
    a = c.doc.get("active_control")
    if not a:
        return "missing", {"days": 0}
    warnings = sum(w["count"] for w in a["warnings"].values())
    ok = a["days_active"] >= p["min_days"] and warnings <= p["max_warnings"]
    return ("seen" if ok else "missing"), {"days": a["days_active"], "warnings": warnings}


def chk_marks_plausible(c, p):
    marks, run = c.doc["run"]["marks"], c.doc["run"]
    ats = [m["at_s"] for m in marks]
    problems = []
    if ats != sorted(ats):
        problems.append("order")
    if ats and ats[-1] > run["minutes"] * 60 + 60:
        problems.append("beyond_the_run")
    restored = [m["at_s"] for m in marks if m["kind"] == "restored"]
    if restored and any(m["at_s"] > min(restored) for m in marks if m["kind"] in ("heat_up", "hot_water")):
        problems.append("action_after_restored")
    return ("seen" if not problems else "untrusted"), {"problems": problems}


def chk_claims_consistent(c, p):
    r, run = c.doc["recording"], c.doc["run"]
    problems = []
    if r["seconds"] > run["minutes"] * 60 + 90:
        problems.append("recording longer than the run")
    if r["file"] is not None and c.rec is None and c.otlog is None:
        return "not_checked", {"list": "", "reason": "recording_file_not_given"}
    if c.otlog is not None:
        if c.otlog["seconds"] > r["seconds"] + 60:
            problems.append("recording length")
        if abs(c.otlog["entries"] - r["frames"]) > max(5, r["frames"] // 20):
            problems.append("frame count")
    states = (c.ot or {}).get("states")
    if states is not None:  # OpenTherm: what the Hub claims against the seconds the boiler's own status spent in each state
        for phase in ("heating", "hot_water", "rest"):
            if phase in run["phases_seen"] and states[phase] < PHASE_MIN_S[phase]:
                problems.append(f"{phase.replace('_', ' ')} claimed but not in the status")
        for kind, phase in (("heat_up", "heating"), ("hot_water", "hot_water")):
            if any(m["kind"] == kind for m in run["marks"]) and states[phase] < PHASE_MIN_S[phase]:
                problems.append(f"mark {kind} without {phase.replace('_', ' ')} in the status")
    if c.rec is not None:
        if abs(c.rec["seconds"] - r["seconds"]) > 60:
            problems.append("recording length")
        if r["frames"] and abs((c.rec["received"] + c.rec["transmitted"] + c.rec["damaged"]) - r["frames"]) > max(5, r["frames"] // 20):
            problems.append("frame count")
    if c.phases is not None:
        run = c.doc["run"]
        for phase in ("heating", "hot_water", "rest"):
            if phase in run["phases_seen"] and not c.phases["phases"][phase]["observed"]:
                problems.append(f"{phase.replace('_', ' ')} claimed but not on the bus")
        problems.extend(mark_problems(c.doc, c.phases))
    if c.replay is not None:
        for m in c.replay.get("marks", []):
            view = m.get("view") or {}
            if m.get("name") == "heating" and view.get("heating") is False:
                problems.append("mark heating without heating")
            if m.get("name") == "hot_water" and view.get("hot_water") is False:
                problems.append("mark hot_water without hot water")
        mine, theirs = (c.ems or {}).get("view"), (c.replay.get("final") or {}).get("view") or {}
        if mine and mine.get("display_code") is not None and theirs.get("display_code") is not None \
                and _norm(mine["display_code"]) != _norm(theirs["display_code"]):
            problems.append("display code of the Hub and of the replay differ")
    return ("seen" if not problems else "untrusted"), {"list": "; ".join(problems), "problems": problems}


def chk_files_match(c, p):
    problems, unchecked = [], []
    r = c.doc["recording"]
    if r["file"] is not None:
        if c.rec_bytes is None:
            unchecked.append("recording")
        elif len(c.rec_bytes) != r["bytes"] or hashlib.sha256(c.rec_bytes).hexdigest() != r["sha256"]:
            problems.append("recording")
    photo = (c.doc.get("human") or {}).get("photo")
    if photo:
        if c.photo_bytes is None:
            unchecked.append("photo")
        elif len(c.photo_bytes) != photo["bytes"] or hashlib.sha256(c.photo_bytes).hexdigest() != photo["sha256"]:
            problems.append("photo")
    detail = {"list": ", ".join(problems), "problems": problems, "unchecked": unchecked}
    if problems:
        return "untrusted", detail
    return ("not_checked" if unchecked else "seen"), detail


def chk_ot_config(c, p):
    cfg = (c.ot or {}).get("config") or {}
    return ("seen" if cfg.get("hot_water") is not None and cfg.get("modulating") is not None else "missing"), {}


def _ot_support_of(c):
    """{data id: state} of the report's support table."""
    return {s["id"]: s["state"] for s in (c.ot or {}).get("support") or []}


def chk_ot_support(c, p):
    """Every value the Hub asks for on its own has been asked at least once (the write-only and the unverified rows of
    the Hub's table are never asked, so they stay untried and are not judged)."""
    support = (c.ot or {}).get("support") or []
    untried = sum(1 for s in support if s["state"] == "untried" and s["id"] in p["polled_ids"])
    return ("seen" if support and not untried else "missing"), {"untried": untried if support else "all"}


def _f88(raw):
    raw = raw - 65536 if raw >= 0x8000 else raw
    return raw / 256


def chk_ot_values(c, p):
    """The values over the whole run: plausible; the flow temperature is always needed, the others only when the boiler says
    it has them (a boiler without a pressure sensor or without modulation is not incomplete)."""
    ot = c.ot or {}
    summary = ot.get("summary") or []
    by_id = {s["id"]: s for s in summary}
    detail = {"list": ", ".join(str(s["id"]) for s in summary), "value": "", "absent": []}
    for s in summary:
        if s["count"] > 0 and None not in (s["last"], s["min"], s["max"]) and not s["min"] <= s["last"] <= s["max"]:
            detail.update({"value": f"id {s['id']} last outside min and max", "value_id": s["id"], "value_what": "order", "value_num": ""})
            return "untrusted", detail
        rng = p["ranges"].get(str(s["id"]))
        if rng:
            for k in ("last", "min", "max"):
                if s[k] is not None and not rng[0] <= _f88(s[k]) <= rng[1]:
                    detail.update({"value": f"id {s['id']} {k} {_f88(s[k]):.1f}", "value_id": s["id"], "value_what": k,
                                   "value_num": f"{_f88(s[k]):.1f}"})
                    return "untrusted", detail
    support = _ot_support_of(c)
    required = list(p["minimum_ids"])
    if (ot.get("config") or {}).get("modulating") is True:
        required.append(p["modulation_id"])
    required += [i for i in p["when_supported"] if support.get(i) == "supported"]
    detail["absent"] = [i for k, i in enumerate(required) if i not in required[:k] and (i not in by_id or by_id[i]["count"] == 0)]
    return ("seen" if not detail["absent"] else "missing"), detail


def _stat_of(c, ident, state):
    for row in (c.ot or {}).get("by_state") or []:
        if row["id"] == ident:
            return row.get(state)
    return None


def chk_ot_state_values(c, p):
    """The values while the boiler was in ONE state (rest, heating, hot water), from the Hub's numbers per state: the flow
    temperature was read there, the other values the boiler has were too, and a boiler that says it heats is not cold."""
    ot = c.ot or {}
    state = p["state"]
    detail = {"state": state, "reads": 0, "need": p["min_reads"], "absent": [], "value": ""}
    if ot.get("states") is None or ot.get("by_state") is None:
        detail["reason"] = "no_state_numbers"
        if c.doc["schema_minor"] < 1:  # a report of the first minor never had them: nothing to judge, nothing missing
            detail["blocks"] = False
            return "not_checked", detail
        return "missing", detail
    if ot["states"][state] < PHASE_MIN_S[state]:  # the boiler was not seen in this state: the phase rule says so, not this one
        detail.update({"reason": "state_not_seen", "blocks": False})
        return "not_checked", detail
    flow = _stat_of(c, 25, state)
    detail["reads"] = flow["count"] if flow else 0
    absent = [] if detail["reads"] >= p["min_reads"] else [25]
    support = _ot_support_of(c)
    for ident in p["extra_ids"]:
        stat = _stat_of(c, ident, state)
        if support.get(ident) == "supported" and (not stat or stat["count"] < 1):
            absent.append(ident)
    detail["absent"] = absent
    if absent:
        return "missing", detail
    if p["flow_min_c"] is not None and flow["max"] is not None and _f88(flow["max"]) < p["flow_min_c"]:
        detail.update({"value": f"id 25 max {_f88(flow['max']):.1f}", "value_id": 25, "value_what": "max", "value_num": f"{_f88(flow['max']):.1f}"})
        return "untrusted", detail
    return "seen", detail


def chk_ot_fault(c, p):
    f = (c.ot or {}).get("fault") or {}
    ok = f.get("none_seen") or any(f.get(k) is not None for k in ("flags", "oem_code", "diagnostic"))
    return ("seen" if ok else "missing"), {}


def chk_display_matches_ot(c, p):
    """The typed display against what the boiler itself told: a code against its fault codes, a temperature against its flow,
    hot water or return temperature (the tolerance is wide: the display and the reading are not the same moment). Nothing to
    compare (a dark display, or a boiler that reported no fault) is not a failure."""
    h = c.doc.get("human") or {}
    state = h.get("display_state", "not_asked")
    detail = {"state": state, "source": "device", "typed": _typed_text(h), "read": ""}
    if state == "not_asked":
        return "missing", detail
    if state in ("dark", "no_display"):
        detail.update({"reason": "nothing_to_compare", "blocks": False})
        return "not_checked", detail
    ot = c.ot or {}
    fault = ot.get("fault") or {}
    codes = list(dict.fromkeys(v for v in (fault.get("oem_code"), fault.get("diagnostic")) if v))   # the same code twice is told once
    temps = [_f88(s["last"]) for i in (25, 26, 28) for s in (ot.get("summary") or []) if s["id"] == i and s["last"] is not None]
    typed_code, typed_temp = h.get("display_code_typed"), h.get("display_temp_typed")
    verdicts, reads = [], []
    if typed_code and codes:
        numbers = [int(n) for n in re.findall(r"[0-9]+", typed_code)]
        reads.append(", ".join(str(v) for v in codes))
        verdicts.append(any(n in codes for n in numbers))
    if typed_temp is not None and temps:
        nearest = min(temps, key=lambda t: abs(typed_temp - t))
        diff = abs(typed_temp - nearest)
        detail["difference_c"] = f"{diff:.1f}"
        reads.append(f"{nearest:.0f} degrees")
        verdicts.append(diff <= p["temperature_tolerance_c"])
    if not verdicts:
        if typed_temp is not None and not temps and not typed_code:
            return "missing", detail
        detail.update({"reason": "nothing_to_compare", "blocks": False})
        return "not_checked", detail
    detail["read"] = " and ".join(reads)
    return ("seen" if all(verdicts) else "untrusted"), detail


def chk_ot_limit(c, p):
    """The boiler's upper water limit. A limit the boiler reported counts (it must be believable); a boiler that has none to
    give (it answers that it does not know the value) is an answer too; a limit the Hub only assumed is never shown as read."""
    limit = (c.ot or {}).get("limit") or {}
    value, source = limit.get("c"), limit.get("source")
    detail = {"limit": value if value is not None else "", "source": source, "told": ""}
    if value is not None and source == "reported":
        detail["told"] = "reported"
        return ("seen" if p["min_c"] <= value <= p["max_c"] else "untrusted"), detail
    if _ot_support_of(c).get(p["limit_id"]) in ("unsupported", "noValue"):
        detail["told"] = "none"
        return "seen", detail
    return "missing", detail


def chk_ot_line(c, p):
    """The Hub's counts of the line to the boiler: present, and not mostly mistakes (too many say the cable, not the boiler)."""
    line = (c.ot or {}).get("line")
    if not line or not line["conversations"]:
        return "missing", {}
    bad = line["no_answer"] + line["parity_errors"] + line["timing_errors"]
    hundredths = bad * 10000 // line["conversations"]
    detail = {"bad": bad, "conversations": line["conversations"], "releases": line["watchdog_releases"],
              "share_pct": f"{hundredths // 100}.{hundredths % 100:02d}"}
    return ("seen" if bad * 100 <= line["conversations"] * p["max_pct"] else "untrusted"), detail


def chk_ot_log(c, p):
    """The change log (otrec 1): named by the report, and, when the file is given, readable and whole."""
    r = c.doc["recording"]
    if not (r["kind"] == "otrec 1" and r["file"] is not None):
        return "missing", {"reason": "no_log"}
    if c.otlog is None:
        return "not_checked", {"reason": "recording_file_not_given"}
    log = c.otlog
    problems = []
    if log["entries"] == 0:
        problems.append("empty")
    if log["malformed"] or log["bad_id"]:
        problems.append("lines")
    if log["out_of_order"]:
        problems.append("order")
    if log["dropped"] is not None and log["dropped"] != r["dropped"]:
        problems.append("dropped")
    return ("seen" if not problems else "untrusted"), {"entries": log["entries"], "dropped": r["dropped"], "problems": problems}


CHECKS = {name[4:]: fn for name, fn in globals().items() if name.startswith("chk_")}


# ---- the result ---------------------------------------------------------------------------------------------------------

# Words the sentences take from the details: every one in both languages (nothing English in a Dutch sentence).
LINK_NAMES = {"ems_classic": {"en": "EMS", "nl": "EMS"}, "ems_plus": {"en": "EMS+", "nl": "EMS+"},
              "opentherm": {"en": "OpenTherm", "nl": "OpenTherm"}, "unknown": {"en": "unknown", "nl": "onbekend"}}
FILE_NAMES = {"recording": {"en": "the recording", "nl": "de opname"}, "photo": {"en": "the photo", "nl": "de foto"}}
PROBLEM_NAMES = {
    "recording longer than the run": {"en": "the recording is longer than the run", "nl": "de opname is langer dan de run"},
    "recording length": {"en": "the length of the recording", "nl": "de lengte van de opname"},
    "frame count": {"en": "the number of messages", "nl": "het aantal berichten"},
    "mark heating without heating": {"en": "you tapped heating, but the recording shows no heating",
                                     "nl": "je tikte verwarmen, maar in de opname verwarmt de ketel niet"},
    "mark hot_water without hot water": {"en": "you tapped hot water, but the recording shows none",
                                         "nl": "je tikte warm water, maar in de opname is er geen"},
    "heating claimed but not on the bus": {"en": "the Hub says the boiler heated, but the recording does not show it",
                                           "nl": "de Hub zegt dat de ketel verwarmde, maar de opname laat het niet zien"},
    "hot water claimed but not on the bus": {"en": "the Hub says the boiler made hot water, but the recording does not show it",
                                             "nl": "de Hub zegt dat de ketel warm water maakte, maar de opname laat het niet zien"},
    "rest claimed but not on the bus": {"en": "the Hub says the boiler was at rest, but the recording does not show it",
                                        "nl": "de Hub zegt dat de ketel in rust was, maar de opname laat het niet zien"},
    "mark heat_up without heating on the bus": {"en": "you turned the thermostat up, but the boiler does not heat soon after in the recording",
                                                "nl": "je zette de thermostaat hoger, maar de ketel gaat daarna in de opname niet verwarmen"},
    "mark hot_water without hot water on the bus": {"en": "you opened a tap, but the boiler does not make hot water soon after in the recording",
                                                    "nl": "je draaide een kraan open, maar de ketel maakt daarna in de opname geen warm water"},
    "display code of the Hub and of the replay differ": {"en": "the display code of the Hub differs from the one in the recording",
                                                         "nl": "de displaycode van de Hub verschilt van die in de opname"},
    "heating claimed but not in the status": {"en": "the Hub says the boiler heated, but the boiler's own report shows it for less than a minute",
                                              "nl": "de Hub zegt dat de ketel verwarmde, maar het eigen bericht van de ketel laat het korter dan een minuut zien"},
    "hot water claimed but not in the status": {"en": "the Hub says the boiler made hot water, but the boiler's own report shows it for less than half a minute",
                                                "nl": "de Hub zegt dat de ketel warm water maakte, maar het eigen bericht van de ketel laat het korter dan een halve minuut zien"},
    "rest claimed but not in the status": {"en": "the Hub says the boiler was at rest, but the boiler's own report shows it for less than a minute",
                                           "nl": "de Hub zegt dat de ketel in rust was, maar het eigen bericht van de ketel laat het korter dan een minuut zien"},
    "mark heat_up without heating in the status": {"en": "you turned the thermostat up, but the boiler did not report heating",
                                                   "nl": "je zette de thermostaat hoger, maar de ketel meldde geen verwarmen"},
    "mark hot_water without hot water in the status": {"en": "you opened a tap, but the boiler did not report making hot water",
                                                       "nl": "je draaide een kraan open, maar de ketel meldde geen warm water maken"},
}
WORDS = {"nl": (("degrees", "graden"), (" and ", " en ")), "en": ()}

# Rules that only the bus recording can prove. In a report WITHOUT the recording they are not findings of their own: the
# summary and the live list leave them out and say once, under the recording's own item, what cannot be checked.
RECORDING_ONLY = ("recording_length", "telegrams_classic", "telegrams_plus_reports", "settings_answered", "frames_clean",
                  "extra_telegrams", "claims_consistent", "ot_log")
WITHOUT_RECORDING = {
    "en": "That is also why we cannot check the boiler's messages, the heating and hot water as recorded, or the cable.",
    "nl": "Daarom kunnen we ook de berichten van de ketel, het verwarmen en het warm water zoals opgenomen en de kabel niet controleren."}
_ADDRESSES = re.compile(r"\s*\((?:\s*0x[0-9A-Fa-f]+(?:\s+\d+x)?\s*,?)+\)")


def without_recording(doc):
    """True when the report has no recording file: then the recording-only rules prove nothing either way."""
    return doc["recording"]["file"] is None


def screen_results(results, doc):
    """The results a tester's screen lists: the recording-only rules are left out of a report without the recording, and
    a recording length that is long enough is never listed as open. One place for the summary and the Hub's page."""
    gone = without_recording(doc)
    out = []
    for r in results:
        if gone and r["id"] in RECORDING_ONLY:
            continue
        if r["id"] == "recording_length" and r["state"] != "seen" and r["detail"].get("minutes", 0) >= r["detail"].get("needed", 1):
            continue
        if r["state"] == "not_checked" and r["detail"].get("reason") in ("state_not_seen", "no_state_numbers"):
            continue  # the values of a state the boiler was not seen in: the phase's own rule says so
        out.append(r)
    return out


def with_recording_note(text, rule_id, doc, lang):
    """The recording's own item says, once, what cannot be checked without it."""
    return f"{text} {WITHOUT_RECORDING[lang]}" if rule_id == "recording_chosen" and without_recording(doc) else text


_PLURAL = re.compile(r"\{(\w+):([^{}|:]*)\|([^{}|:]*)\}")


def plural(text, values):
    """The one way a sentence says a count: `{minutes} {minutes:minute|minutes}` reads "1 minute" and "5 minutes" (the first word when the
    count is exactly 1, the second otherwise; a count that is not a whole number takes the second). The Hub's page script does the same."""
    return _PLURAL.sub(lambda m: m.group(2) if type(values.get(m.group(1))) is int and values[m.group(1)] == 1 else m.group(3), text)


def _fmt(text, rule, detail):
    values = {k: "?" for k in rule["placeholders"]}
    for k, v in detail.items():
        if k in rule["placeholders"]:
            values[k] = "?" if v is None or v == "" else v
    if "list" in rule["placeholders"] and not detail.get("list"):
        values["list"] = ""  # no detail: the brackets around it go too
    out = plural(text, values).format_map(values)
    out = re.sub(r"\s*\(\s*\)", "", out)
    out = re.sub(r"[ ]{2,}", " ", out)
    return re.sub(r"\s+([.;,:])", r"\1", out).strip()


def _plain_value(text, lang):
    """"flow_centi_c 21300" as a tester reads it: "flow temperature 213 °C" (the names are data: completeness.json)."""
    names = fmt.completeness()["value_names"]
    key, _, number = str(text).partition(" ")
    entry = names.get(key)
    if entry is None:
        m = re.match(r"id (\d+) ", str(text))
        if m:  # an OpenTherm value by its number
            return f"{'waarde' if lang == 'nl' else 'value'} {m.group(1)}"
        return str(text)
    if number.lstrip("-").isdigit() and entry["div"] != 1:
        shown = f"{int(number) / entry['div']:.1f}".rstrip("0").rstrip(".")
    else:
        shown = number
    if lang == "nl":
        shown = shown.replace(".", ",")
    return " ".join(x for x in (entry[lang], shown, entry["unit"]) if x)


def _words(text, lang):
    for english, dutch in WORDS[lang]:
        text = text.replace(english, dutch)
    return text


def _named(keys, table, lang):
    return ", ".join(table[k][lang] for k in keys if k in table)


# ---- the names of an OpenTherm value in a tester's own words (data: completeness.json "ot_words") ------------------------------

def _ot_value_name(ident, lang, screen):
    """"flow temperature" (the screen), "flow temperature (data id 25)" (the file's own text); None for a value without a name."""
    words = fmt.completeness()["ot_words"]
    entry = words["values"].get(str(ident))
    if entry is None:
        return None
    return entry[lang] if screen else f"{entry[lang]} ({words['id'][lang]} {ident})"


def _ot_names(idents, lang, screen):
    return ", ".join(n for n in (_ot_value_name(i, lang, screen) for i in idents) if n is not None)


def _ot_value_text(detail, lang, screen):
    """What an implausible value reads as: "flow temperature 213 °C", or that its last value lies outside its range."""
    words = fmt.completeness()["ot_words"]
    entry = words["values"].get(str(detail["value_id"]))
    name = _ot_value_name(detail["value_id"], lang, screen) or words["unnamed"][lang]
    if detail.get("value_what") == "order":
        return words["order"][lang].format(name=name)
    number = detail["value_num"].replace(".", ",") if lang == "nl" else detail["value_num"]
    return " ".join(x for x in (name, number, entry["unit"] if entry else "") if x)


def rule_text(rule, which, lang, detail, screen=False):
    """One sentence of a rule. Every detail that reaches it is in the language asked for; an empty detail leaves its
    brackets out. screen=True (a tester's screen) also leaves out bus addresses, which stay in the report file."""
    detail = dict(detail)
    check = rule.get("check")
    if check == "plausible_ems":
        if detail.get("value"):
            detail["value"] = _plain_value(detail["value"], lang)
        if detail.get("list"):
            detail["list"] = ", ".join(fmt.completeness()["value_names"].get(k, {}).get(lang, k) for k in detail["list"].split(", "))
    if check in ("ot_values", "ot_state_values"):
        if detail.get("value_id") is not None:
            detail["value"] = _ot_value_text(detail, lang, screen)
        detail["list"] = _ot_names(detail.get("absent") or [int(i) for i in str(detail.get("list", "")).split(", ") if re.fullmatch(r"[0-9]+", i)], lang, screen)
    if check == "ot_log":
        problems = fmt.completeness()["ot_words"]["log_problems"]
        detail["list"] = ", ".join(problems[k][lang] for k in detail.get("problems") or [] if k in problems)
    if check == "ot_line" and lang == "nl" and detail.get("share_pct"):
        detail["share_pct"] = detail["share_pct"].replace(".", ",")
    if check == "identity_ot":
        member = detail.get("member")
        detail["told"] = f" ({fmt.completeness()['ot_words']['maker'][lang]} {member})" if member is not None else ""
    if check == "ot_limit":
        words = fmt.completeness()["ot_words"]
        detail["limit_text"] = f"{detail['limit']} °C" if detail.get("told") == "reported" else words["limit_none"][lang]
    if check == "claims_consistent":
        detail["list"] = _named(detail.get("problems") or [], PROBLEM_NAMES, lang)
    if check == "files_match":
        detail["list"] = _named(detail.get("problems") or [], FILE_NAMES, lang)
    if check == "link_known" and "link" in detail:
        detail["link"] = LINK_NAMES.get(detail["link"], LINK_NAMES["unknown"])[lang]
    for key in ("typed", "read"):
        if detail.get(key):
            detail[key] = _words(detail[key], lang)
    if "shown" in rule["placeholders"]:
        states = fmt.completeness()["display_states"]
        typed = detail.get("typed", "")
        detail = dict(detail, shown=states[detail["state"]][lang] if detail.get("state") in states else "?")
        if typed:
            detail["shown"] += f" ({typed})"
    sentence = rule["action_screen"] if which == "action" and screen and "action_screen" in rule else rule[which]   # a tester's own action, where the file's is for the checker
    out = _fmt(sentence[lang], rule, detail)
    return _ADDRESSES.sub("", out).replace(" .", ".") if screen else out


def identity_of(doc):
    b = doc["boiler"]
    o = b.get("opentherm")
    key = None
    if doc["link"] in ("ems_classic", "ems_plus") and b["product"] is not None and b["version"] is not None:
        key = f"ems:{'plus' if doc['link'] == 'ems_plus' else 'classic'}:{b['product']}:{b['version']}"
    elif doc["link"] == "opentherm" and o and o["member"] is not None and o["product_type"] is not None:
        key = f"ot:{o['member']}:{o['product_type']}:{o['product_version']}" + \
              (f":{o['ot_version_hundredths']}" if o["ot_version_hundredths"] is not None else "")
    return {"key": key, "link": doc["link"], "family": b["family"], "product": b["product"], "version": b["version"],
            "brand": b["brand"], "row": b["row"], "opentherm": o}


def evaluate(doc, rec_bytes=None, photo_bytes=None, replay_runner=None, rec=None, timeline_runner=None):
    """The rules of the report's link applied: (context, [rule results]). One evaluator for the integration and the
    tools; replay_runner() -> (replay, why) is the tools' host replay (the integration has none)."""
    table = fmt.completeness()
    c = Context(doc, rec_bytes, photo_bytes, replay_runner, rec, timeline_runner)
    out = []
    for rid in table["links"][doc["link"]]["rules"]:
        rule = table["rules"][rid]
        state, detail = CHECKS[rule["check"]](c, rule["params"])
        out.append({"id": rid, "items": rule["items"], "kind": rule["kind"], "counts_for": rule["counts_for"],
                    "state": state, "detail": detail})
    return c, out


def _skippable(r):
    """A check that found nothing to compare (a dark display) is not checked, and does not block."""
    return r["state"] == "not_checked" and r["detail"].get("blocks") is False


def levels_of(results):
    """{level: bool}: a level is reached when every rule at that level and below is seen."""
    out, ok = {}, True
    for level in LEVEL_ORDER:
        for r in results:
            if r["counts_for"] == level and r["state"] != "seen" and not _skippable(r):
                ok = False
        out[level] = ok
    return out
