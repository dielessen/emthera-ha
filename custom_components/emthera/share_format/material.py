"""The material bundle "boiler-material 1": what the Hub sends by itself after ONE permission (TESTER-AUTO-1).

The Hub does not make the report. It sends the documents its own page would read (material.json: the allow-list, a key that
is not listed makes the whole bundle invalid, like the report's), one recorded half hour and what its scorer says about that
window. Our own computer makes the report "boiler-share 2" from it with the builder that already mirrors the Hub's page
(tester_material.report_from_material, which calls tester_run.TesterRun._build): there is no second builder.

This module is the format: the strict reader, the cross checks, the filter that keeps only the boiler's own telegrams in an
EMS recording, and the two decisions of the owner that are NOT answered yet, each behind ONE named switch:

    BOILER_TELEGRAMS_ONLY   (decision 2) True: only telegrams to or from the boiler leave the house; a bundle whose EMS
                            recording holds anything else is refused. False: the recording is sent as it is (room
                            temperatures and the thermostat's clock included), and the permission text must say so
                            (consent_auto.json has both forms of that paragraph).

(The other switch, TYPED_DISPLAY_NEEDED_FOR_AUTO, is a rule and lives in auto.py.)

`sequence` (minor 1, optional, 1 or 2, absent means 1) is the Hub's ONE more half hour with the same report id: the report builder ignores it,
the intake does not (tools/testers/intake). A bundle never says more than the reader's minor.

Standard library only (the tools of the owner's computer load this file by path, like the other files of share_format).
"""
import json
import re
from pathlib import Path

from . import fmt, recording, rules

# ---- the switch of decision 2 (one line changes it) ---------------------------------------------------------------------------
BOILER_TELEGRAMS_ONLY = True

SCHEMA = "boiler-material 1"
DATA = Path(__file__).resolve().parent
BOILER_ADDRESS = 0x08
FILTER_NAME = "boiler_only_1"          # the word the filtered recording carries in its header line: "# filter=boiler_only_1 ..."
FILTER_LINE = re.compile(r"# filter=" + FILTER_NAME + r" kept=([0-9]{1,9}) removed_frames=([0-9]{1,9}) removed_damaged=([0-9]{1,9})"
                         r" removed_polls=([0-9]{1,9}) removed_unreadable=([0-9]{1,9})")
PHRASE_BAD = re.compile(r"[0-9]{1,3}(\.[0-9]{1,3}){3}|([0-9A-Fa-f]{2}[:-]){5}[0-9A-Fa-f]{2}|@|://|  ")
BLOCK_OK = re.compile(r"[\x20-\x7e\n]*")

_CACHE = {}


def spec():
    if "spec" not in _CACHE:
        _CACHE["spec"] = fmt.load_json_file(DATA / "material.json")
    return _CACHE["spec"]


def limits():
    return spec()["limits"]


# ---- reading a bundle strictly --------------------------------------------------------------------------------------------------

def parse(data):
    """(bundle, problems) of the bytes of a bundle file: size, UTF-8, JSON without duplicate keys or NaN."""
    p = fmt.Problems()
    limit = limits()["bundle_bytes"]
    if len(data) > limit:
        p.add("file", "size", f"larger than {limit // 1024} KB")
        return None, p
    try:
        doc = json.loads(data.decode("utf-8"), object_pairs_hook=fmt._no_duplicates, parse_constant=fmt._no_constant)
    except (UnicodeDecodeError, ValueError, RecursionError) as err:
        p.add("file", "json", f"is not valid JSON ({type(err).__name__})")
        return None, p
    if type(doc) is not dict:
        p.add("file", "json", "must be a JSON object")
        return None, p
    return doc, p


def _resolve(node):
    """A node with its reference resolved: {"ref": name} (our defs) or {"report": path} (the report's allow-list)."""
    if "ref" in node:
        base = dict({**fmt.allowlist()["defs"], **spec()["defs"]}[node["ref"]])    # the bundle's own words first, then the report's (a report node may refer to them)
    elif "report" in node:
        base = fmt.allowlist()["root"]
        for part in node["report"].split("."):
            base = fmt.node_of(fmt.allowlist(), base["members"][part])
        base = dict(base)
    else:
        return node
    if node.get("null"):
        base["null"] = True
    return base


def _walk(p, path, v, node, depth):
    node = _resolve(node)
    if v is None:
        if not node.get("null"):
            p.add(path, "null", "must not be null")
        return
    if depth > fmt.MAX_DEPTH:
        p.add(path, "depth", "nested too deep")
        return
    kind = node["t"]
    if kind == "const":
        if v != node["v"] or type(v) is not type(node["v"]):
            p.add(path, "word", f'must be {json.dumps(node["v"])}')
    elif kind == "int":
        if type(v) is not int or not node["min"] <= v <= node["max"]:
            p.add(path, "range", f"must be a whole number from {node['min']} to {node['max']}" + (" or null" if node.get("null") else ""))
    elif kind == "num":
        if type(v) not in (int, float) or not node["min"] <= v <= node["max"]:
            p.add(path, "range", f"must be a number from {node['min']} to {node['max']}")
    elif kind == "bool":
        if type(v) is not bool:
            p.add(path, "type", "must be true or false")
    elif kind == "word":
        if type(v) is not str or v not in node["words"]:
            p.add(path, "word", "unexpected value")
    elif kind == "text":
        if type(v) is not str or not re.fullmatch(node["pattern"], v):
            p.add(path, "pattern", "unexpected value")
        elif fmt.NETWORK.search(v):
            p.add(path, "network_like", "a text looks like an address, a name or free text")
    elif kind == "phrase":      # a few plain words (the user's own typed boiler): bounded, plain characters, nothing that looks like an address
        if type(v) is not str or not re.fullmatch(node["pattern"], v):
            p.add(path, "pattern", "unexpected value")
        elif PHRASE_BAD.search(v):
            p.add(path, "network_like", "a text looks like an address or a name")
    elif kind == "block":       # the recording: plain printable ASCII and line ends, bounded
        if type(v) is not str or len(v) > node["max"] or not BLOCK_OK.fullmatch(v):
            p.add(path, "block", f"must be plain text of at most {node['max']} characters")
    elif kind == "object":
        if type(v) is not dict:
            p.add(path, "type", "must be an object")
            return
        optional = set(node.get("optional", ()))
        missing = [k for k in node["members"] if k not in v and k not in optional]
        extra = sorted(set(v) - set(node["members"]))
        if missing:
            p.add(path or "file", "missing", "missing " + ", ".join(missing))
        if extra:   # the names are not echoed: a private string can be a key
            p.add(path or "file", "unknown_key", f"{len(extra)} unexpected key(s) (not in the allow-list)")
        for k, sub in node["members"].items():
            if k in v:
                _walk(p, f"{path}.{k}" if path else k, v[k], sub, depth + 1)
    elif kind == "list":
        if type(v) is not list or len(v) > node["max"]:
            p.add(path, "size", f"must be a list of at most {node['max']}")
            return
        for idx, item in enumerate(v):
            _walk(p, f"{path}[{idx}]", item, node["items"], depth + 1)
    else:  # pragma: no cover (the allow-list is ours)
        raise ValueError(f"unknown node type {kind}")


# ---- the window (what the Hub's scorer says) -----------------------------------------------------------------------------------

def needed_seconds():
    """The length a recording must reach (the rule table's `recording_length`): the window is good only with it."""
    return fmt.completeness()["rules"]["recording_length"]["params"]["min_s"]


def lacks_of(seconds, heating_s, hot_water_s):
    """What a window lacks, in the words of the bundle: heating (the boiler seen heating for 60 s), hot_water (30 s), length."""
    out = []
    if heating_s < rules.PHASE_MIN_S["heating"]:
        out.append("heating")
    if hot_water_s < rules.PHASE_MIN_S["hot_water"]:
        out.append("hot_water")
    if seconds < needed_seconds():
        out.append("length")
    return out


def phases_of(window):
    """The phases the window claims, as the run record names them: what the Hub's own counters saw for long enough (the rule table's
    minimum per phase), in the order the page lists them. Never `restored`: that is a moment a person taps."""
    return [p for p, seconds in (("rest", window["rest_s"]), ("heating", window["heating_s"]), ("hot_water", window["hot_water_s"]))
            if seconds >= rules.PHASE_MIN_S[p]]


# ---- the cross checks ------------------------------------------------------------------------------------------------------------

EMS_ONLY = ("match", "profile", "devices", "boiler")
OT_ONLY = ("ot_link", "ot_run", "ot_groups")
EMS_OPTIONAL = ("readiness", "plus_probe")      # what the Hub already saved of an attended test (the wizard's own test, the EMS+ probe); absent when there is none
OT_OPTIONAL = ("ot_test",)


def validate(doc):
    """The problems of a material bundle (an empty list: well formed and consistent). Strict: a key that is not in the
    allow-list makes the whole bundle invalid."""
    p = fmt.Problems()
    if type(doc) is not dict:
        p.add("file", "type", "must be a JSON object")
        return p
    if doc.get("schema") != SCHEMA:
        p.add("schema", "word", f'must be "{SCHEMA}"')
        return p
    _walk(p, "", doc, spec()["root"], 0)
    if p:
        return p
    _cross(p, doc)
    return p


def _cross(p, doc):
    if doc["schema_minor"] > spec()["minor"]:
        p.add("schema_minor", "newer_minor", f"newer than this reader knows (it reads up to {spec()['minor']}); update the reader")
    if doc["permission"]["yes"] is not True:
        p.add("permission.yes", "consent", "a bundle is only valid with the permission")
    docs, link = doc["documents"], doc["link"]
    need, forbid = (EMS_ONLY, OT_ONLY) if link == "ems" else (OT_ONLY, EMS_ONLY)
    for k in need:
        if k not in docs:
            p.add(f"documents.{k}", "link", f"required for link {link}")
    for k in (*forbid, *(OT_OPTIONAL if link == "ems" else EMS_OPTIONAL)):
        if k in docs:
            p.add(f"documents.{k}", "link", f"not allowed for link {link}")
    if link == "opentherm":
        groups = docs.get("ot_groups")
        if groups is not None and len(groups) not in (0, 8):
            p.add("documents.ot_groups", "size", "the numbers per state come in eight documents, or none")
    if doc["software"]["firmware"] != docs["version"]["version"]:
        p.add("software.firmware", "cross", "the firmware version is not the one the Hub's own version document says")
    pick = doc["boiler_pick"]
    if pick is not None:
        if pick["source"] == "list" and (pick["list_id"] is None or pick["brand"] is not None or pick["model"] is not None):
            p.add("boiler_pick", "cross", "a boiler picked from the list is named by its list id only")
        if pick["source"] == "typed" and (pick["list_id"] is not None or pick["brand"] is None or pick["model"] is None):
            p.add("boiler_pick", "cross", "a boiler typed by the user has a brand and a model and no list id")
    w = doc["window"]
    lacks = lacks_of(w["seconds"], w["heating_s"], w["hot_water_s"])
    if list(w["lacks"]) != lacks or w["good"] is not (not lacks):
        p.add("window", "cross", "what the window lacks is not what its own numbers say")
    r = doc["recording"]
    kind, text = r["kind"], r["text"]
    if (kind is None) != (text is None):
        p.add("recording", "cross", "a recording text needs its kind, and only a text has one")
    want = "emsrec 1" if link == "ems" else "otrec 1"
    if kind is not None and kind != want:
        p.add("recording.kind", "link", f"link {link} carries a {want} recording")
    if text is not None:
        if len(text.encode("ascii")) > limits()["recording_bytes"]:
            p.add("recording.text", "size", "larger than the recording limit")
        if not text.startswith("# " + want + "\n"):
            p.add("recording.text", "format", f'the first line must be "# {want}"')
    if link == "opentherm" and r["filtered"]:
        p.add("recording.filtered", "link", "the OpenTherm log holds boiler values only: there is nothing to filter")
    if link == "ems" and text is not None:
        if BOILER_TELEGRAMS_ONLY:
            if not r["filtered"]:
                p.add("recording.filtered", "boiler_only", "only telegrams to or from the boiler may leave the house: the recording must be filtered")
            elif not is_boiler_only(text.encode("ascii")):
                p.add("recording.text", "not_boiler_only", "the recording holds a telegram that is neither to nor from the boiler")
        elif r["filtered"] and not is_boiler_only(text.encode("ascii")):
            p.add("recording.text", "not_boiler_only", "the recording says it is filtered but holds a telegram that is neither to nor from the boiler")
    elif r["filtered"] and text is None:
        p.add("recording.filtered", "cross", "there is no recording to be filtered")


# ---- the filter: only the boiler's own telegrams (decision 2) ---------------------------------------------------------------------

def _keeps(kind, hexes, boiler=BOILER_ADDRESS):
    """One record of an emsrec text: kept only when the boiler is its sender or its receiver.

    R and T (a telegram heard, a telegram the Hub sent) and X (a damaged one): the first byte is the sender, the second the
    receiver, each without the read bit (0x80). So a telegram of the boiler to everyone (a broadcast of the boiler) stays, a
    broadcast of anyone else goes, a request of the Hub to the boiler stays, a request of the Hub to the thermostat goes, and the
    answer of the thermostat goes. P (a poll of one address: the master asks who has something to say) stays only for the boiler."""
    frame = [int(h, 16) for h in hexes.split()]
    if kind == "P":
        return len(frame) == 1 and frame[0] & 0x7F == boiler
    return len(frame) >= 2 and (frame[0] & 0x7F == boiler or frame[1] & 0x7F == boiler)


def _records(data):
    """[(line, kind or None, hexes or None)] of the lines of an emsrec text: a comment or blank line has no kind, a line that is no record has kind '?'."""
    out = []
    for line in data.decode("ascii").split("\n"):
        if line.endswith("\r"):
            line = line[:-1]
        if not line.strip() or line.startswith("#"):
            out.append((line, None, None))
            continue
        m = recording.RECORD.fullmatch(line)
        out.append((line, m.group(2), m.group(3)) if m else (line, "?", None))
    return out


def is_boiler_only(data):
    """True when every record of an emsrec text is to or from the boiler (and no line is a record that cannot be read)."""
    return all(kind is None or (kind != "?" and _keeps(kind, hexes)) for _, kind, hexes in _records(data))


def _damaged(kind, hexes):
    """Whether read_recording counts the record as damaged: an X record, a frame shorter than five bytes or one whose check byte is wrong."""
    frame = bytes(int(h, 16) for h in hexes.split())
    return kind == "X" or len(frame) < 5 or frame[-1] != recording.crc(frame[:-1])


def filter_recording(data):
    """(the filtered emsrec text as bytes, what it says about itself): only the telegrams to or from the boiler remain. One header
    line says that the filter ran and what it removed, by kind (frames, damaged frames, polls, lines that were no readable record), so
    the checker can still read the damaged share of the WHOLE recording (auto.py). A line that is no readable record is removed as
    well: nothing unread leaves the house. Idempotent: an earlier filter line is replaced by the new one."""
    out, stats = [], {"kept": 0, "removed_frames": 0, "removed_damaged": 0, "removed_polls": 0, "removed_unreadable": 0}
    before = filter_header(data) or {}          # a recording that was filtered before keeps the counts of what that run removed
    mark = None
    for line, kind, hexes in _records(data):
        if kind is None:
            if not line.startswith("# filter="):
                out.append(line)
            continue
        if mark is None:
            mark = len(out)
        if kind != "?" and _keeps(kind, hexes):
            out.append(line)
            stats["kept"] += 1
        elif kind == "?":
            stats["removed_unreadable"] += 1
        elif kind == "P":
            stats["removed_polls"] += 1
        elif _damaged(kind, hexes):
            stats["removed_damaged"] += 1
        else:
            stats["removed_frames"] += 1
    for key in stats:
        if key != "kept":
            stats[key] += before.get(key, 0)
    note = (f"# filter={FILTER_NAME} kept={stats['kept']} removed_frames={stats['removed_frames']} removed_damaged={stats['removed_damaged']}"
            f" removed_polls={stats['removed_polls']} removed_unreadable={stats['removed_unreadable']}")
    at = len(out) if mark is None else mark
    text = "\n".join(out[:at] + [note] + out[at:])
    return (text if text.endswith("\n") else text + "\n").encode("ascii"), stats


def filter_header(data):
    """What a filtered recording's header line says it removed (the keys of filter_recording's second result), or None when it was not filtered."""
    for line in data.decode("ascii", "replace").split("\n"):
        m = FILTER_LINE.fullmatch(line.rstrip("\r"))
        if m:
            return dict(zip(("kept", "removed_frames", "removed_damaged", "removed_polls", "removed_unreadable"), map(int, m.groups())))
        if line and not line.startswith("#"):
            return None
    return None


def status_of(data):
    """The recording status the Hub states for what it sends: length, frames (received + transmitted + damaged), polls. Counted over
    the text that LEAVES the house, so the report's claims agree with the file (the Hub's own ring counts more, a filter removes some)."""
    info, problems = recording.read_recording(data)
    if info is None:
        return None
    return {"seconds": min(info["seconds"], 1800), "frames": info["received"] + info["transmitted"] + info["damaged"],
            "polls": info["polls"], "dropped": 0}
