"""The bus recording ("emsrec 1", the text the Hub's recorder writes) and the OpenTherm change log ("otrec 1"): the readers
and the identity comparison.

ONE reader for every user of a recording: the integration (its own completeness answer, share_format/rules.py) and
the owner's computer (tools/emsplus/check_share.py and check_share2.py load this file by path). It reads only text it is
given; it never opens a file or a network. Standard library only.
"""
import hashlib
import re

MAX_RECORDING_BYTES = 2 * 1024 * 1024  # a full E32 ring (192 KiB) downloads as about 550 KB of text
MAX_LINE = 160


class Problems(list):
    def add(self, path, what):
        self.append(f"{path}: {what}")


def crc(data):
    """The EMS CRC (https://docs.emsesp.org/EMS-bus/), as src/EMS/EmsTelegram.cpp computes it."""
    c = 0
    for b in data:
        c = ((c << 1) ^ (0x19 if c & 0x80 else 0) ^ b) & 0xFF
    return c


RECORD = re.compile(r"([0-9]{1,20}) ([RTPX]) ([0-9A-Fa-f]{2}(?: [0-9A-Fa-f]{2}){0,31})")


def telegram_type(frame):
    """The type of a frame (EMS 1.0 or EMS+), or None when it is too short to have one."""
    if len(frame) < 5:
        return None
    read = frame[1] != 0 and frame[1] & 0x80
    if frame[2] == 0xFF and (read or len(frame) >= 7):
        start = 5 if read else 4
        if len(frame) < start + 3:
            return None
        return (frame[start] << 8 | frame[start + 1]) + 256
    return frame[2]


def read_recording(data):
    """What a recording holds: (info, problems). It must be an emsrec 1 text; malformed lines are counted."""
    p = Problems()
    if len(data) > MAX_RECORDING_BYTES:
        p.add("recording", f"larger than {MAX_RECORDING_BYTES // 1024} KB")
        return None, p
    try:
        text = data.decode("ascii")
    except UnicodeDecodeError:
        p.add("recording", "not an emsrec recording (not plain text)")
        return None, p
    lines = text.splitlines()
    if not lines or lines[0].strip() != "# emsrec 1":
        p.add("recording", 'not an emsrec recording (the first line is not "# emsrec 1")')
        return None, p
    info = {"header": {}, "records": 0, "received": 0, "transmitted": 0, "polls": 0, "damaged": 0, "malformed": 0,
            "first_ms": None, "last_ms": None, "telegrams": {}, "out_of_order": 0}
    records = False
    for line in lines[1:]:
        if len(line) > MAX_LINE:
            info["malformed"] += 1
            continue
        if line.startswith("#"):
            body = line[1:].strip()
            if not records and "=" in body and not body.startswith("mark "):
                for pair in body.split():
                    k, _, v = pair.partition("=")
                    if k in ("source", "product", "version", "family", "e32") and v:
                        info["header"][k] = v[:32]
            continue
        if not line.strip():
            continue
        m = RECORD.fullmatch(line.rstrip("\r"))
        if not m:
            info["malformed"] += 1
            continue
        records = True
        ms, kind, hexes = int(m.group(1)), m.group(2), m.group(3)
        frame = bytes(int(h, 16) for h in hexes.split())
        info["records"] += 1
        if info["last_ms"] is not None and ms < info["last_ms"]:
            info["out_of_order"] += 1
        info["first_ms"] = ms if info["first_ms"] is None else min(info["first_ms"], ms)
        info["last_ms"] = ms if info["last_ms"] is None else max(info["last_ms"], ms)
        if kind == "P":
            info["polls"] += 1
            continue
        if kind == "X" or len(frame) < 5 or frame[-1] != crc(frame[:-1]):
            info["damaged"] += 1
            continue
        info["transmitted" if kind == "T" else "received"] += 1
        t = telegram_type(frame)
        if t is not None:
            key = f"{frame[0] & 0x7F:02X}:{t:#04x}" if t <= 0xFF else f"{frame[0] & 0x7F:02X}:{t:#05x}"
            info["telegrams"][key] = info["telegrams"].get(key, 0) + 1
    info["seconds"] = 0 if info["first_ms"] is None else (info["last_ms"] - info["first_ms"]) // 1000
    info["sha256"] = hashlib.sha256(data).hexdigest()
    frames = info["received"] + info["transmitted"] + info["damaged"]
    info["damaged_ratio"] = info["damaged"] / frames if frames else 0.0
    return info, p


def identity_conflict(share, info):
    """True when the recording's header or the share's devices name another product or version than the share's
    boiler part (then the E32's read cannot stand in for a version telegram missing from the recording)."""
    b = share["boiler"]
    header = info.get("header") or {}
    if header.get("product") not in (None, str(b["product"])) or header.get("version") not in (None, b["version"]):
        return True
    for d in share["telegrams"]["devices"]:
        if d["bus_address"] == 0x08 and ((d["product"] is not None and d["product"] != b["product"])
                                         or (d["version"] is not None and d["version"] != b["version"])):
            return True
    return False


# ---- the OpenTherm change log "otrec 1" (the Hub's /opentherm/run/log) ------------------------------------------------------
# A first line "# otrec 1", header lines "# source=tester" and "# dropped=<n>", then one line per change of a value:
# "<seconds>.<milliseconds> <data id> <four hex digits>" (time since the start of the run, only when the answer changed).
# At most OTREC_MAX_ENTRIES lines: the Hub keeps that many and counts the later ones as dropped.

OTREC_MAX_ENTRIES = 4096
OTREC_LINE = re.compile(r"([0-9]{1,5})\.([0-9]{3}) ([0-9]{1,3}) ([0-9A-Fa-f]{4})")


def read_otrec(data):
    """What an otrec change log holds: (info, problems). Not an otrec text: no info. Malformed lines are counted."""
    p = Problems()
    if len(data) > MAX_RECORDING_BYTES:
        p.add("recording", f"larger than {MAX_RECORDING_BYTES // 1024} KB")
        return None, p
    try:
        text = data.decode("ascii")
    except UnicodeDecodeError:
        p.add("recording", "not an otrec change log (not plain text)")
        return None, p
    lines = text.splitlines()
    if not lines or lines[0].strip() != "# otrec 1":
        p.add("recording", 'not an otrec change log (the first line is not "# otrec 1")')
        return None, p
    info = {"header": {}, "entries": 0, "malformed": 0, "out_of_order": 0, "bad_id": 0, "first_ms": None,
            "last_ms": None, "dropped": None}
    entries = False
    for line in lines[1:]:
        if len(line) > MAX_LINE:
            info["malformed"] += 1
            continue
        if line.startswith("#"):
            body = line[1:].strip()
            if not entries and "=" in body:
                for pair in body.split():
                    k, _, v = pair.partition("=")
                    if k == "source" and v:
                        info["header"]["source"] = v[:32]
                    elif k == "dropped" and v.isdigit() and len(v) <= 9:
                        info["dropped"] = int(v)
            continue
        if not line.strip():
            continue
        m = OTREC_LINE.fullmatch(line.rstrip("\r"))
        if not m:
            info["malformed"] += 1
            continue
        entries = True
        ms = int(m.group(1)) * 1000 + int(m.group(2))
        ident = int(m.group(3))
        info["entries"] += 1
        if ident > 127:
            info["bad_id"] += 1
        if info["last_ms"] is not None and ms < info["last_ms"]:
            info["out_of_order"] += 1
        info["first_ms"] = ms if info["first_ms"] is None else min(info["first_ms"], ms)
        info["last_ms"] = ms if info["last_ms"] is None else max(info["last_ms"], ms)
    info["seconds"] = 0 if info["last_ms"] is None else info["last_ms"] // 1000
    info["sha256"] = hashlib.sha256(data).hexdigest()
    return info, p
