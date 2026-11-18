"""Firmware offers from the signed update list of the product's own website (the update route, package P4).

Specification: docs/engineering/UPDATE-ROUTE.md (the list, the signature line, the 512-byte trailer of a firmware
file, "newest" as an algorithm). Its golden files and case files (test/fixtures/update/) decide where this text and
the specification differ. This module is the integration's own implementation of the reader: it does not import from
``tools/`` (the integration ships on its own), and ``tests_native/test_update_catalog.py`` proves it equal to the
reference reader with every case of the three case files.

What it does, in this order, for one device:

1. fetch ``catalog.json`` and ``catalog.sig`` from ``https://updates.emthera.nl/v1/`` (fixed host and path prefix, no
   redirect followed, a size bound, a timeout, a fixed User-Agent without version, name or address);
2. verify the signature line and the ECDSA P-256 / SHA-256 signature over the exact bytes of the list with the public
   keys of ``PRODUCTION_POINTS`` (``cryptography``, a dependency of Home Assistant Core itself); only then parse;
3. apply the rules of the specification: lexical bounds, format, schema, members, the stored generation (it only
   rises), duplicates, the clock and the expiry, the selection for the device (product from the board it reports);
4. later, for the chosen release: the file (its size and SHA-256 from the list, then the file's own trailer and its
   signature, then the binding between list and file) and the notes (their SHA-256 from the list).

The public key table is all zero today: a slot that is all zero is not provisioned, so every list is refused
(``sig_key_not_provisioned``) and nothing is offered, until the owner puts his real public keys here. Slot 2 is the
practice key; a normal installation refuses it, a list with ``"test": true`` and an image with the rehearsal flag.
Only a developer switch (the environment variable ``OPEN_THERMOSTAT_UPDATE_REHEARSAL=1``, which no user interface
offers) accepts them.

No private key, passphrase or secret of any kind is in this module (the practice key's public point is public).
"""
from __future__ import annotations

import asyncio
import base64
import hashlib
import json
import logging
import os
import re
import struct

import aiohttp
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.asymmetric.utils import encode_dss_signature

_LOGGER = logging.getLogger(__name__)

# --- where -------------------------------------------------------------------------------------------------------
HOST = "updates.emthera.nl"
BASE_URL = f"https://{HOST}/v1/"
REHEARSAL_BASE_URL = f"https://{HOST}/v1-test/"      # the practice folder (plan D.5); only a rehearsal client uses it
USER_AGENT = "emthera-ha-updater"                      # fixed: no version, no name, no address
FETCH_TIMEOUT = 30                                     # seconds per request (the plan's C.1)
FILE_TIMEOUT = 300                                     # seconds for a firmware file (3.5 MB over a slow line)
RETRY_AFTER = 10                                       # seconds before the one retry of a torn pair (spec 5.3)
SIG_MAX_BYTES = 96                                     # a signature line is exactly 95
NOTES_MAX_BYTES = 16384                                # spec 3.4
REHEARSAL_SWITCH = "OPEN_THERMOSTAT_UPDATE_REHEARSAL"

# --- the public keys ---------------------------------------------------------------------------------------------
# Slots 0 and 1: the owner's production keys. ALL ZERO today (not provisioned = fail closed). The same two points are
# in the firmware's table (src/update/UpdatePublicKeys.h); `emthera_sign.py pubkeys --check` compares the copies.
PRODUCTION_POINTS = {0: "00" * 65, 1: "00" * 65}
# Slot 2: the practice key (test/fixtures/update/practice-key/). It protects nothing.
PRACTICE_POINT = ("04575aefbfdbab0bcb1e68ff52af34f5f56f48c88bd22ed8126add01a3b12ab9ca59124c1cf785cbb146049abfaf527b8b66"
                  "2b472d1e44e55058778460a5ed5393")
PRODUCTION_SLOTS = (0, 1)
PRACTICE_SLOT = 2


def rehearsal_enabled():
    """The developer switch. No user interface, option or service sets it."""
    return os.environ.get(REHEARSAL_SWITCH) == "1"


def public_keys(rehearsal=False):
    """{slot: 65-byte point}; slot 2 only for a rehearsal reader. A zero point is kept (it is "not provisioned")."""
    keys = {slot: bytes.fromhex(point) for slot, point in PRODUCTION_POINTS.items()}
    if rehearsal:
        keys[PRACTICE_SLOT] = bytes.fromhex(PRACTICE_POINT)
    return keys


# --- the limits of the specification -----------------------------------------------------------------------------
LIST_MAX_BYTES = 32768
NODE_MAX = 4096
DEPTH_MAX = 8
PRODUCTS_MAX = 8
RELEASES_MAX = 8
FORMAT = "emthera-update-catalog"
EXPIRES_MAX_DAYS = 400
VERSION_COMPONENT_MAX = 65535   # the trailer carries u16 numbers
PRERELEASE_NUMBER_MAX = 255     # and a u8 prerelease number
SIZE_BOUNDS = {"e32v2": (1000000, 3670016), "hub": (1000000, 3932160), "hub-radio": (1024, 2547712)}
BOARDS = {"e32v2": "bbqkees_e32v2", "hub": "emthera_hub_v1", "hub-radio": "emthera_hub_v1"}
LAYOUTS = {"e32v2": "e32v2-dual-app-spiffs-v1", "hub": "hub-dual-app-spiffs-c6-v2"}
SETTINGS_SCHEMA = 1             # what a device of today has (the spec: "today 1"); neither device reports it
FIRMWARE_PRODUCTS = ("e32v2", "hub")   # the products this module installs (hub-radio is a later package)
SLOT_BYTES = {"e32v2": 3670016,  # the gateway's smaller OTA slot (0x380000)
              "hub": 3932160}    # the Hub's OTA slots (0x3C0000, layout v2)
SLOT_MAX = max(SLOT_BYTES.values())   # the bound before the product is known
RANK = {"alpha": 0, "beta": 1, "rc": 2, None: 3}
CLOCK_FLOOR = "2026-01-01T00:00:00Z"   # the epoch of `generation` (D12): an earlier clock is not trusted

_NUM = r"(0|[1-9][0-9]{0,8})"
VERSION_RE = re.compile(rf"{_NUM}\.{_NUM}\.{_NUM}(?:-(alpha|beta|rc)\.{_NUM})?")
TRIPLE_RE = re.compile(rf"{_NUM}\.{_NUM}\.{_NUM}")
HEX64 = re.compile(r"[0-9a-f]{64}")
UTC_RE = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z")
DATE_RE = re.compile(r"\d{4}-\d{2}-\d{2}")
FILE_RE = re.compile(r"files/[a-z0-9][a-z0-9._-]{0,89}")
NOTES_RE = re.compile(r"notes/[a-z0-9][a-z0-9._-]{0,89}\.md")
NEED_RE = re.compile(r"[a-z0-9._-]{1,32}")
TAG_RE = re.compile(r"v[0-9][A-Za-z0-9.-]{0,45}")
SIG_LINE_RE = re.compile(rb"ES1 ([0-9]) ([A-Za-z0-9+/]{86}==)\n")


class ListError(Exception):
    """A refusal of the whole list; ``reason`` is a stable name of the specification (section 12)."""

    def __init__(self, reason):
        super().__init__(reason)
        self.reason = reason


class CatalogError(Exception):
    """A refusal after the list: ``reason`` is a stable name (a trailer name, ``file_list_mismatch``, ``size_mismatch``,
    ``hash_mismatch``, ``notes_hash_mismatch``) or ``unreachable``."""

    def __init__(self, reason):
        super().__init__(reason)
        self.reason = reason


# ======================================================================================================
# versions, dates, numbers
# ======================================================================================================
def parse_version(text):
    """(major, minor, patch, rank, n) or None. Rank: alpha 0, beta 1, rc 2, stable 3 (n = 0)."""
    m = VERSION_RE.fullmatch(text) if isinstance(text, str) else None
    if not m:
        return None
    major, minor, patch, channel, n = m.groups()
    return int(major), int(minor), int(patch), RANK[channel], int(n or 0)


def version_text(key):
    return "%d.%d.%d" % key[:3] + ("" if key[3] == 3 else "-%s.%d" % (("alpha", "beta", "rc")[key[3]], key[4]))


def tag_for(product, version):
    """The tag a device reports for a release: v<major>.<minor>.<patch>-<product>[-<channel>.<n>]."""
    core, _, pre = version.partition("-")
    return "v%s-%s%s" % (core, product, "-" + pre if pre else "")


def parse_installed(product, text):
    """The installed version as the device reports it: a tag for e32v2 and hub, the plain version for hub-radio."""
    if not isinstance(text, str):
        return None
    if product == "hub-radio":
        return parse_version(text)
    if product not in FIRMWARE_PRODUCTS:
        return None
    n = r"(?:0|[1-9][0-9]{0,8})"
    m = re.fullmatch(rf"v({n}\.{n}\.{n})-{re.escape(product)}(-(?:alpha|beta|rc)\.{n})?", text)
    if not m or len(text) > 47:
        return None
    return parse_version(m.group(1) + (m.group(2) or ""))


def key_fits_trailer(key):
    return max(key[:3]) <= VERSION_COMPONENT_MAX and key[4] <= PRERELEASE_NUMBER_MAX


def valid_date(text, with_time):
    if not isinstance(text, str) or not (UTC_RE if with_time else DATE_RE).fullmatch(text):
        return False
    year, month, day = int(text[0:4]), int(text[5:7]), int(text[8:10])
    if year < 1970 or not 1 <= month <= 12:
        return False
    if with_time and (int(text[11:13]) > 23 or int(text[14:16]) > 59 or int(text[17:19]) > 59):
        return False
    limit = (31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31)[month - 1]
    if month == 2 and year % 4 == 0 and (year % 100 != 0 or year % 400 == 0):
        limit = 29
    return 1 <= day <= limit


def days_between(earlier, later):
    """Days (fractional) between two valid UTC texts, from days since 1970 (no library)."""
    def seconds(t):
        y, mo, d, h, mi, s = (int(t[a:b]) for a, b in ((0, 4), (5, 7), (8, 10), (11, 13), (14, 16), (17, 19)))
        y -= mo <= 2
        era = y // 400
        yoe = y - era * 400
        doy = (153 * (mo + (-3 if mo > 2 else 9)) + 2) // 5 + d - 1
        doe = yoe * 365 + yoe // 4 - yoe // 100 + doy
        return ((era * 146097 + doe - 719468) * 24 + h) * 3600 + mi * 60 + s
    return (seconds(later) - seconds(earlier)) / 86400.0


def is_int(value):
    """A JSON number whose value is an integer (1 and 1.0 are the same; True is not a number: bool is an int)."""
    return (isinstance(value, int) and not isinstance(value, bool)) or (isinstance(value, float) and value.is_integer())


def _triple(text):
    return tuple(int(p) for p in text.split("."))


# ======================================================================================================
# the signature of the list (steps 1 to 5)
# ======================================================================================================
def parse_sig_line(line):
    """(slot, raw r||s) of a catalog.sig, strict: exactly one line of 95 bytes, canonical base64; else None."""
    m = SIG_LINE_RE.fullmatch(bytes(line))
    if not m:
        return None
    raw = base64.b64decode(m.group(2))
    if base64.b64encode(raw) != m.group(2):
        return None
    return int(m.group(1)), raw


def check_signature(point, message, raw):
    """"ok", "bad_signature" or "bad_key" (not a point of the curve) for the raw r||s over SHA-256(message)."""
    try:
        key = ec.EllipticCurvePublicKey.from_encoded_point(ec.SECP256R1(), bytes(point))
    except ValueError:
        return "bad_key"
    signature = encode_dss_signature(int.from_bytes(raw[:32], "big"), int.from_bytes(raw[32:], "big"))
    try:
        key.verify(signature, bytes(message), ec.ECDSA(hashes.SHA256()))
    except InvalidSignature:
        return "bad_signature"
    return "ok"


def _provisioned(point):
    return bool(point) and len(point) == 65 and point[0] == 4


def verify_list_signature(data, sig_line, keys, rehearsal=False):
    """Steps 1 to 5 of the specification: the stable refusal name, or "none". Looks at nothing of the list's content."""
    if not data or len(data) > LIST_MAX_BYTES:
        return "list_too_large"
    parsed = parse_sig_line(sig_line)
    if parsed is None:
        return "sig_malformed"
    slot, raw = parsed
    if slot not in PRODUCTION_SLOTS and not (rehearsal and slot == PRACTICE_SLOT):
        return "sig_slot_not_allowed"
    point = keys.get(slot)
    if not _provisioned(point):
        return "sig_key_not_provisioned"
    if not any(raw[:32]) or not any(raw[32:]):
        return "sig_invalid"
    result = check_signature(point, b"emthera-catalog-v1\x00" + bytes(data), raw)
    return "none" if result == "ok" else "sig_key_not_provisioned" if result == "bad_key" else "sig_invalid"


# ======================================================================================================
# the list (steps 6 to 13)
# ======================================================================================================
def scan_bounds(text):
    """The lexical bounds of the firmware (ReleasePolicy.h releaseJson): size, control characters in strings, the
    escape \\u0000, nesting depth and the node count (string openings, braces, brackets, commas, colons)."""
    if not text or len(text.encode("utf-8")) > LIST_MAX_BYTES or "\\u0000" in text:
        raise ListError("list_not_json")
    quoted = escaped = False
    depth = nodes = 0
    for c in text:
        if quoted:
            if escaped:
                escaped = False
            elif c == "\\":
                escaped = True
            elif c == '"':
                quoted = False
            elif ord(c) < 32:
                raise ListError("list_not_json")
            continue
        if c == '"':
            quoted = True
            nodes += 1
        elif c in "{[":
            depth += 1
            nodes += 1
            if depth > DEPTH_MAX:
                raise ListError("list_not_json")
        elif c in "}]":
            if not depth:
                raise ListError("list_not_json")
            depth -= 1
        elif c in ",:":
            nodes += 1
        if nodes > NODE_MAX:
            raise ListError("list_not_json")
    if quoted or escaped or depth:
        raise ListError("list_not_json")


def _no_duplicates(pairs):
    out = {}
    for k, v in pairs:
        if k in out:
            raise ListError("list_not_json")
        out[k] = v
    return out


def _no_constant(_name):
    raise ListError("list_not_json")


def _has_lone_surrogate(value):
    if isinstance(value, str):
        return any(0xD800 <= ord(c) <= 0xDFFF for c in value)
    if isinstance(value, dict):
        return any(_has_lone_surrogate(k) or _has_lone_surrogate(v) for k, v in value.items())
    if isinstance(value, list):
        return any(_has_lone_surrogate(v) for v in value)
    return False


def parse_list(data):
    """Bytes (or text) of catalog.json to a Python object, or ListError('list_too_large' | 'list_not_json').
    Call it only on bytes whose signature has been verified."""
    if isinstance(data, str):
        data = data.encode("utf-8")
    if not data or len(data) > LIST_MAX_BYTES:
        raise ListError("list_too_large")
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        raise ListError("list_not_json") from None
    scan_bounds(text)
    try:
        doc = json.loads(text, object_pairs_hook=_no_duplicates, parse_constant=_no_constant)
    except ListError:
        raise
    except (ValueError, RecursionError):
        raise ListError("list_not_json") from None
    if _has_lone_surrogate(doc):
        raise ListError("list_not_json")
    return doc


def read_list(doc, stored_generation, rehearsal):
    """Steps 7 to 13 on a parsed list. Returns (doc, generation) or raises ListError."""
    if not isinstance(doc, dict) or doc.get("format") != FORMAT:
        raise ListError("list_format")
    if not is_int(doc.get("schema")) or doc["schema"] != 1:
        raise ListError("list_schema")
    g = doc.get("generation")
    if not (is_int(g) and 1 <= g <= 4294967295 and valid_date(doc.get("generated"), True)
            and valid_date(doc.get("expires"), True) and isinstance(doc.get("products"), list)):
        raise ListError("list_members")
    if not 0 < days_between(doc["generated"], doc["expires"]) <= EXPIRES_MAX_DAYS:
        raise ListError("list_members")
    if "test" in doc and not isinstance(doc["test"], bool):
        raise ListError("list_members")
    if doc.get("test") is True and not rehearsal:
        raise ListError("list_test_only")
    if int(g) < stored_generation:
        raise ListError("list_generation_old")
    products = doc["products"]
    if len(products) > PRODUCTS_MAX:
        raise ListError("list_members")
    seen = set()
    for entry in products:
        if not isinstance(entry, dict) or not isinstance(entry.get("id"), str) or entry["id"] in seen:
            raise ListError("list_members")
        seen.add(entry["id"])
        if entry["id"] in SIZE_BOUNDS:
            rels = entry.get("releases")
            if not isinstance(rels, list) or len(rels) > RELEASES_MAX or any(not isinstance(r, dict) for r in rels):
                raise ListError("list_members")
    for entry in products:
        if entry["id"] in SIZE_BOUNDS:
            versions = [r["version"] for r in entry["releases"] if parse_version(r.get("version")) is not None]
            if len(versions) != len(set(versions)):
                raise ListError("list_duplicate_release")
    return doc, int(g)


# ======================================================================================================
# the selection (steps 16 and 17)
# ======================================================================================================
def _text_ok(value, max_bytes):
    return (isinstance(value, str) and 1 <= len(value.encode("utf-8")) <= max_bytes
            and not any(ord(c) < 32 or ord(c) == 127 for c in value))


def _bilingual(value, max_bytes):
    return isinstance(value, dict) and all(_text_ok(value.get(lang), max_bytes) for lang in ("en", "nl"))


def _hex_pair(value):
    return isinstance(value, dict) and all(isinstance(value.get(lang), str) and HEX64.fullmatch(value[lang])
                                           for lang in ("en", "nl"))


def _paths(value):
    return isinstance(value, dict) and all(isinstance(value.get(lang), str) and NOTES_RE.fullmatch(value[lang])
                                           and ".." not in value[lang] for lang in ("en", "nl"))


def release_usable(product, rel, device):
    """None when an ACTIVE release is complete and for this device, else the internal reason (not a stable name:
    a release that is not usable is skipped silently)."""
    key = parse_version(rel.get("version"))
    if key is None or not key_fits_trailer(key):
        return "version"
    if rel.get("channel") not in ("stable", "beta"):
        return "channel"
    if not valid_date(rel.get("date"), False):
        return "date"
    f = rel.get("file")
    if not (isinstance(f, str) and FILE_RE.fullmatch(f) and ".." not in f):
        return "file"
    lo, hi = SIZE_BOUNDS[product]
    if not is_int(rel.get("size")) or not lo <= rel["size"] <= hi:
        return "size"
    if not (isinstance(rel.get("sha256"), str) and HEX64.fullmatch(rel["sha256"])):
        return "sha256"
    if not _bilingual(rel.get("summary"), 160) or not _paths(rel.get("notes")) or not _hex_pair(rel.get("notes_sha256")):
        return "summary/notes"
    if rel.get("board") != device["board"]:
        return "board"
    if product in ("e32v2", "hub"):
        if rel.get("tag") != tag_for(product, rel["version"]) or not TAG_RE.fullmatch(rel["tag"]):
            return "tag"
        if rel.get("layout") != device["layout"]:
            return "layout"
        if not is_int(rel.get("settings_schema")) or not 1 <= rel["settings_schema"] <= 65535 \
                or rel["settings_schema"] != device["settings_schema"]:
            return "settings_schema"
    else:
        if rel.get("target") != device["target"]:
            return "target"
        lp = rel.get("link_protocol")
        if not (isinstance(lp, dict) and is_int(lp.get("min")) and is_int(lp.get("max"))
                and 1 <= lp["min"] <= lp["max"] <= 65535):
            return "link_protocol"
        dl = device["link_protocol"]
        if lp["max"] < dl["min"] or lp["min"] > dl["max"]:
            return "link_protocol"
        mh = rel.get("min_hub")
        if not (isinstance(mh, str) and TRIPLE_RE.fullmatch(mh)):
            return "min_hub"
        if _triple(mh) > _triple(device["hub_version"]):
            return "min_hub"
        if not (isinstance(rel.get("build_id"), str) and HEX64.fullmatch(rel["build_id"])):
            return "build_id"
    if "requires" in rel:
        req = rel["requires"]
        r = parse_version(req.get("installed_at_least")) if isinstance(req, dict) else None
        if r is None or not r < key:
            return "requires"
    if "needs" in rel:
        needs = rel["needs"]
        if not isinstance(needs, list) or any(not (isinstance(n, str) and NEED_RE.fullmatch(n)) for n in needs) or needs:
            return "needs"
    return None


def device_facts_ok(device):
    if not isinstance(device, dict) or device.get("product") not in SIZE_BOUNDS:
        return False
    p = device["product"]
    if device.get("board") != BOARDS[p]:
        return False
    if p == "hub-radio":
        lp = device.get("link_protocol")
        return (device.get("target") == "esp32c6" and isinstance(device.get("hub_version"), str)
                and TRIPLE_RE.fullmatch(device["hub_version"]) is not None and isinstance(lp, dict)
                and is_int(lp.get("min")) and is_int(lp.get("max")) and 1 <= lp["min"] <= lp["max"] <= 65535)
    return isinstance(device.get("layout"), str) and is_int(device.get("settings_schema"))


def device_for(product):
    """The facts of a device of today for the selection (what the specification's table says a device has)."""
    if product not in FIRMWARE_PRODUCTS:
        return None
    return {"product": product, "board": BOARDS[product], "layout": LAYOUTS[product], "settings_schema": SETTINGS_SCHEMA}


def select_release(doc, installed, device):
    """Steps 16 and 17 on a verified, unexpired list: (reason, release or None, installed_withdrawn)."""
    if not device_facts_ok(device):
        return "device_facts", None, False
    product = device["product"]
    entry = next((e for e in doc["products"] if e["id"] == product), None)
    if entry is None:
        return "product_missing", None, False
    key = parse_installed(product, installed)
    if key is None:
        return "installed_unparsed", None, False
    releases = entry.get("releases") or []
    withdrawn = any(parse_version(r.get("version")) == key and r.get("status") == "withdrawn" for r in releases)
    usable = [(parse_version(r["version"]), r) for r in releases
              if r.get("status") == "active" and release_usable(product, r, device) is None]
    if not usable:
        return "no_release", None, withdrawn
    mature = [(k, r) for k, r in usable if k[3] >= key[3]]
    reachable = [(k, r) for k, r in mature
                 if "requires" not in r or key >= parse_version(r["requires"]["installed_at_least"])]
    best = max(reachable, key=lambda kr: kr[0], default=None)
    if best is not None and best[0] > key:
        return "offer", best[1], withdrawn
    if any(k > key for k, _ in mature):
        return "requires_not_met", None, withdrawn
    return "up_to_date", None, withdrawn


def evaluate(data, *, installed, device, now, stored_generation, rehearsal=False):
    """Steps 6 to 17 on the BYTES of a list whose signature is verified, the way the case files state them (section 8
    of the specification): {"reason", "offer", "installed_withdrawn", "stored_generation"}."""
    out = {"reason": None, "offer": None, "installed_withdrawn": False, "stored_generation": stored_generation}
    try:
        doc, generation = read_list(parse_list(data), stored_generation, rehearsal)
    except ListError as err:
        out["reason"] = err.reason
        return out
    out["stored_generation"] = max(stored_generation, generation)          # step 14: commit
    if not valid_date(now, True):
        out["reason"] = "no_clock"
        return out
    if now >= doc["expires"]:          # fixed-format UTC texts order like the instants they name
        out["reason"] = "list_expired"
        return out
    reason, release, withdrawn = select_release(doc, installed, device)
    out["reason"], out["installed_withdrawn"] = reason, withdrawn
    out["offer"] = release["version"] if release else None
    return out


# ======================================================================================================
# the firmware file: image + 512-byte trailer (section 6)
# ======================================================================================================
TRAILER_BYTES = 512
TRAILER_MAGIC = b"EMTHFW01"
OFF = dict(version=8, size=10, image_len=12, product=16, board=32, layout=64, tag=96, vkey=144, floor=152,
           requires=160, schema=168, flags=170, created=172, sha=176, build=208, reserved=240, sig=256, pad=321)
FLAG_REHEARSAL = 1
IMAGE_MIN = 24
KEY_NONE = bytes(8)
MARKER_RE = re.compile(rb"OT_E32V2_OTA_V1:(v[0-9][A-Za-z0-9.-]{0,45}):[0-9a-f]{40}:[0-9a-f]{64}:END")


def _key_from_bytes(raw):
    major, minor, patch, rank, n = struct.unpack("<HHHBB", raw)
    if rank > 3 or (rank == 3 and n):
        return None
    return major, minor, patch, rank, n


def _clean_text(raw):
    """A NUL-padded printable-ASCII field, or None."""
    end = raw.find(b"\x00")
    if end <= 0 or any(raw[end:]) or any(c < 0x20 or c > 0x7E for c in raw[:end]):
        return None
    return raw[:end].decode("ascii")


def find_marker_tag(image):
    """The tag of the first build marker of the image, as the firmware's upload gate finds it, or None."""
    m = MARKER_RE.search(bytes(image))
    return m.group(1).decode("ascii") if m else None


def parse_trailer(data, slot_bytes=None):
    """(info, reason): the structure checks 1 to 7 of the order in section 6.3."""
    n = len(data)
    if n < TRAILER_BYTES + IMAGE_MIN:
        return None, "trailer_truncated"
    if n > (slot_bytes or SLOT_MAX):
        return None, "size_out_of_range"
    t = bytes(data[-TRAILER_BYTES:])
    if t[:8] != TRAILER_MAGIC:
        return None, "no_trailer"
    version, size, image_len = struct.unpack_from("<HHI", t, OFF["version"])
    if version != 1:
        return None, "bad_trailer_version"
    if size != TRAILER_BYTES:
        return None, "bad_trailer_size"
    if image_len != n - TRAILER_BYTES:
        return None, "image_len_mismatch"
    schema, flags, created = struct.unpack_from("<HHI", t, OFF["schema"])
    if flags & ~FLAG_REHEARSAL:
        return None, "bad_flags"
    if any(t[OFF["reserved"]:OFF["reserved"] + 16]):
        return None, "reserved_not_zero"
    if any(t[OFF["pad"]:]):
        return None, "bad_padding"
    text = {name: _clean_text(t[OFF[name]:OFF[name] + length]) for name, length in
            (("product", 16), ("board", 32), ("layout", 32), ("tag", 48))}
    if any(v is None for v in text.values()):
        return None, "bad_text"
    if text["product"] not in FIRMWARE_PRODUCTS:
        return None, "bad_product"
    vkey = _key_from_bytes(t[OFF["vkey"]:OFF["vkey"] + 8])
    if vkey is None or not any(vkey):
        return None, "bad_version"
    floor = None if t[OFF["floor"]:OFF["floor"] + 8] == KEY_NONE else _key_from_bytes(t[OFF["floor"]:OFF["floor"] + 8])
    if t[OFF["floor"]:OFF["floor"] + 8] != KEY_NONE and (floor is None or not floor <= vkey):
        return None, "bad_floor"
    requires = (None if t[OFF["requires"]:OFF["requires"] + 8] == KEY_NONE
                else _key_from_bytes(t[OFF["requires"]:OFF["requires"] + 8]))
    if t[OFF["requires"]:OFF["requires"] + 8] != KEY_NONE and (requires is None or not requires < vkey):
        return None, "bad_requires"
    if text["tag"] != tag_for(text["product"], version_text(vkey)):
        return None, "tag_version_mismatch"
    if schema < 1:
        return None, "bad_settings_schema"
    info = dict(text, version=vkey, version_text=version_text(vkey), floor=floor, requires=requires,
                settings_schema=schema, flags=flags, created=created, image_len=image_len,
                image_sha256=t[OFF["sha"]:OFF["sha"] + 32], key_slot=t[OFF["sig"]], trailer=t)
    return info, "none"


def verify_firmware(data, keys, device=None, rehearsal=False):
    """The complete order of section 6.3: the stable refusal name, or "none". Returns (name, info).

    keys: {slot: 65-byte point}. device: None, or {"product", "board", "layout", "settings_schema", "installed": a
    version key or None, "stored_floor": a version key or None}; checks 9 and 11 run only with it. rehearsal: True for
    a rehearsal reader (it accepts slot 2 and the rehearsal flag).
    """
    info, reason = parse_trailer(data, SLOT_BYTES.get(device.get("product")) if device else None)
    if info is None:
        return reason, None
    image = bytes(data[:-TRAILER_BYTES])
    if info["flags"] & FLAG_REHEARSAL and not rehearsal:
        return "rehearsal_not_allowed", info
    if device is not None:
        for field, name in (("product", "product_mismatch"), ("board", "board_mismatch"), ("layout", "layout_mismatch")):
            if info[field] != device[field]:
                return name, info
        if info["settings_schema"] != device["settings_schema"]:
            return "settings_schema_mismatch", info
    marker = find_marker_tag(image)
    if marker is None:
        return "marker_missing", info
    if marker != info["tag"]:
        return "tag_marker_mismatch", info
    if device is not None:
        if device.get("stored_floor") and info["version"] < tuple(device["stored_floor"]):
            return "below_floor", info
        if info["requires"] and (device.get("installed") is None or tuple(device["installed"]) < info["requires"]):
            return "requires_not_met", info
    if hashlib.sha256(image).digest() != info["image_sha256"]:
        return "image_hash_mismatch", info
    t = info["trailer"]
    if not any(t[OFF["sig"]:OFF["sig"] + 65]):
        return "unsigned", info
    slot = info["key_slot"]
    if slot not in PRODUCTION_SLOTS and not (rehearsal and slot == PRACTICE_SLOT):
        return "key_slot", info
    point = keys.get(slot)
    if not _provisioned(point):
        return "key_not_provisioned", info
    raw = bytes(t[OFF["sig"] + 1:OFF["sig"] + 65])
    if not any(raw[:32]) or not any(raw[32:]):
        return "signature_invalid", info
    result = check_signature(point, b"emthera-firmware-v1\x00" + bytes(t[:256]), raw)
    return ("none" if result == "ok" else "key_not_provisioned" if result == "bad_key" else "signature_invalid"), info


def check_against_release(info, release):
    """The binding between a downloaded file and the list entry it came from (section 6.5): "none" or
    "file_list_mismatch"."""
    wanted = ((release.get("requires") or {}).get("installed_at_least") if "requires" in release else None)
    ok = (info["product"] in FIRMWARE_PRODUCTS and release.get("tag") == info["tag"]
          and release.get("version") == info["version_text"] and release.get("board") == info["board"]
          and release.get("layout") == info["layout"] and release.get("settings_schema") == info["settings_schema"]
          and release.get("size") == info["image_len"] + TRAILER_BYTES
          and wanted == (None if info["requires"] is None else version_text(info["requires"])))
    return "none" if ok else "file_list_mismatch"


# ======================================================================================================
# the client
# ======================================================================================================
def utc_now_text():
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# catalog_status: what a person is told (attribute of the update entity). The stable reason stays in catalog_reason.
STATUS_OK, STATUS_STALE, STATUS_UNREACHABLE = "ok", "stale", "unreachable"
STATUS_SIGNATURE, STATUS_INVALID = "signature_invalid", "invalid"
_STATUS_OF = {
    "sig_malformed": STATUS_SIGNATURE, "sig_slot_not_allowed": STATUS_SIGNATURE,
    "sig_key_not_provisioned": STATUS_SIGNATURE, "sig_invalid": STATUS_SIGNATURE,
    "list_expired": STATUS_STALE, "list_generation_old": STATUS_STALE,
    "unreachable": STATUS_UNREACHABLE,
    "list_too_large": STATUS_INVALID, "list_not_json": STATUS_INVALID, "list_format": STATUS_INVALID,
    "list_schema": STATUS_INVALID, "list_members": STATUS_INVALID, "list_test_only": STATUS_INVALID,
    "list_duplicate_release": STATUS_INVALID, "no_clock": STATUS_INVALID,
}


class CatalogCheck:
    """The outcome of one check for one device. ``release`` is the offered release (a dict of the verified list) or
    None; ``status`` and ``reason`` as above; ``generation`` the stored generation; ``checked`` the UTC time of the
    last list that passed the signature and the rules (also an earlier one)."""

    def __init__(self, reason, release=None, installed_withdrawn=False, generation=0, checked=None, rehearsal=False,
                 hub_first=None):
        self.reason, self.release, self.installed_withdrawn = reason, release, installed_withdrawn
        self.hub_first = hub_first   # hub-radio: a newer radio release exists that needs a newer Hub (its release), or None
        self.generation, self.checked, self.rehearsal = generation, checked, rehearsal
        self.status = STATUS_OK if reason in ("offer", "up_to_date", "requires_not_met", "no_release", "product_missing",
                                              "installed_unparsed", "device_facts") else _STATUS_OF.get(reason, STATUS_INVALID)


class CatalogClient:
    """Fetches, verifies and selects. ``store``: an object with ``async_load()`` -> dict or None and
    ``async_save(dict)`` (Home Assistant's Store, in firmware_update.py); it keeps the generation that only rises and
    the time of the last good list. ``keys`` and ``rehearsal`` default to the production table and the developer
    switch. One client serves every entry of the installation (one list for all)."""

    def __init__(self, store, *, clock=None, keys=None, rehearsal=None, sleep=None):
        self._store = store
        self._clock_override = clock
        self._rehearsal = rehearsal_enabled() if rehearsal is None else bool(rehearsal)
        self._keys = keys
        self._sleep = sleep or asyncio.sleep
        self._state = None          # {"generation": int, "checked": text or None}, loaded once
        self._lock = asyncio.Lock()

    # -- the stored generation and the time of the last good list ---------------------------------------------------
    async def _load(self):
        if self._state is None:
            loaded = None
            try:
                loaded = await self._store.async_load()
            except Exception:  # noqa: BLE001 - an unreadable store starts again from zero (the floor is only a floor)
                _LOGGER.debug("Emthera: the update list's stored generation could not be read", exc_info=True)
            generation = loaded.get("generation") if isinstance(loaded, dict) else None
            checked = loaded.get("checked") if isinstance(loaded, dict) else None
            self._state = {"generation": generation if type(generation) is int and 0 <= generation <= 4294967295 else 0,
                           "checked": checked if valid_date(checked, True) else None}
        return self._state

    async def _save(self):
        try:
            await self._store.async_save(dict(self._state))
        except Exception:  # noqa: BLE001 - the value is kept in memory; the next success saves it again
            _LOGGER.debug("Emthera: the update list's stored generation could not be saved", exc_info=True)

    def _clock(self):
        return (self._clock_override or utc_now_text)()

    @property
    def rehearsal(self):
        return self._rehearsal

    def _base(self):
        return REHEARSAL_BASE_URL if self._rehearsal else BASE_URL

    def _key_table(self):
        return self._keys if self._keys is not None else public_keys(self._rehearsal)

    # -- the transport ----------------------------------------------------------------------------------------------
    async def _get(self, session, path, limit, timeout=FETCH_TIMEOUT):
        """The body of GET base + path (200 only, no redirect, at most ``limit`` bytes), or CatalogError."""
        try:
            async with asyncio.timeout(timeout):
                async with session.get(self._base() + path, headers={"User-Agent": USER_AGENT, "Cache-Control": "no-cache"},
                                       allow_redirects=False, timeout=aiohttp.ClientTimeout(total=timeout)) as response:
                    if response.status != 200:
                        raise CatalogError("unreachable")
                    chunks, total = [], 0
                    async for chunk in response.content.iter_chunked(65536):
                        total += len(chunk)
                        if total > limit:
                            raise CatalogError("too_large")
                        chunks.append(chunk)
                    return b"".join(chunks)
        except (aiohttp.ClientError, TimeoutError, ValueError):
            raise CatalogError("unreachable") from None

    async def _fetch_pair(self, session):
        data = await self._get(session, "catalog.json", LIST_MAX_BYTES)
        try:
            sig = await self._get(session, "catalog.sig", SIG_MAX_BYTES)
        except CatalogError as err:
            if err.reason != "too_large":
                raise
            sig = b"too large"            # a signature line is 95 bytes: this is a malformed one (sig_malformed)
        return data, sig

    # -- the list ---------------------------------------------------------------------------------------------------
    async def async_check(self, session, product, installed, device=None):
        """One check: fetch the pair (one retry of a torn pair), verify, apply the rules, select for ``product`` and the
        ``installed`` tag. Returns a CatalogCheck; never raises for a website, signature or list problem.

        ``device``: the facts of the device when they are not the constants of today (device_for): for ``hub-radio`` the
        Hub's board, the radio target, the link protocol range and the Hub's version (S-HA-2 package C)."""
        async with self._lock:
            state = await self._load()
            now = self._clock()
            try:
                data, doc = await self._verified_list(session, state)
            except CatalogError as err:
                reason = "list_too_large" if err.reason == "too_large" else err.reason
                return CatalogCheck(reason, generation=state["generation"], checked=state["checked"],
                                    rehearsal=self._rehearsal)
            except ListError as err:
                return CatalogCheck(err.reason, generation=state["generation"], checked=state["checked"],
                                    rehearsal=self._rehearsal)
            if not valid_date(now, True) or now < CLOCK_FLOOR:       # the host clock is not trusted
                return CatalogCheck("no_clock", generation=state["generation"], checked=state["checked"],
                                    rehearsal=self._rehearsal)
            if now >= doc["expires"]:
                return CatalogCheck("list_expired", generation=state["generation"], checked=state["checked"],
                                    rehearsal=self._rehearsal)
            facts = device or device_for(product) or {}
            reason, release, withdrawn = select_release(doc, installed, facts)
            hub_first = None
            if product == "hub-radio" and release is None and device_facts_ok(facts):
                # A newer radio file that only a newer Hub can take: say so ("the Hub must be updated first").
                again, newer, _w = select_release(doc, installed, {**facts, "hub_version": "65535.65535.65535"})
                hub_first = newer if again == "offer" else None
            return CatalogCheck(reason, release, withdrawn, state["generation"], state["checked"], self._rehearsal, hub_first)

    async def _verified_list(self, session, state):
        """Steps 1 to 14 (with the one retry): the parsed list, after the generation was committed."""
        for attempt in (0, 1):
            data, sig = await self._fetch_pair(session)
            reason = verify_list_signature(data, sig, self._key_table(), self._rehearsal)
            if reason in ("sig_invalid", "sig_malformed") and attempt == 0:
                await self._sleep(RETRY_AFTER)           # a torn pair (a new list with an old signature): once more
                continue
            break
        if reason != "none":
            raise ListError(reason)
        doc, generation = read_list(parse_list(data), state["generation"], self._rehearsal)
        # Step 14, the commit: the stored generation rises (also for a list that is expired or has no offer for us).
        stamp = self._clock()
        state["checked"] = stamp if valid_date(stamp, True) else state["checked"]
        if generation > state["generation"]:
            state["generation"] = generation
        await self._save()
        return data, doc

    # -- the file and the notes -------------------------------------------------------------------------------------
    async def async_fetch_file(self, session, release, product, installed):
        """The firmware file of ``release`` (a release of a CatalogCheck), verified in full: its size and SHA-256 from
        the list, then the trailer (the order of section 6.3, with the device's facts), then the binding to the list
        entry. Returns (bytes, info). Raises CatalogError with the stable name of the first failed check."""
        device = dict(device_for(product) or {})
        installed_key = parse_installed(product, installed)
        device["installed"] = installed_key
        device["stored_floor"] = None                       # the device keeps its own floor; the device checks it
        size = release["size"]
        lo, hi = SIZE_BOUNDS[product]
        if not is_int(size) or not lo <= size <= min(hi, SLOT_BYTES[product]):
            raise CatalogError("size_out_of_range")
        data = await self._get(session, release["file"], size, FILE_TIMEOUT)
        if len(data) != size:
            raise CatalogError("size_mismatch")
        if hashlib.sha256(data).hexdigest() != release["sha256"]:
            raise CatalogError("hash_mismatch")
        reason, info = verify_firmware(data, self._key_table(), device, self._rehearsal)
        if reason != "none":
            raise CatalogError(reason)
        if check_against_release(info, release) != "none":
            raise CatalogError("file_list_mismatch")
        return data, info

    async def async_fetch_container(self, session, release, *, hub_version, link_protocol, board=None):
        """The radio container of ``release`` (a hub-radio release of a CatalogCheck), verified in full before anything is
        sent to the Hub: its size and SHA-256 from the list, then the container's own checks in the Hub's order
        (radio_container.verify_container: structure, the Hub's policy, the signature, the parts), then the binding to the
        list entry (build id, version, target, link protocol range, lowest Hub version). Returns (bytes, info). Raises
        CatalogError with the stable name of the first failed check."""
        from . import radio_container as rc
        size = release["size"]
        lo, hi = SIZE_BOUNDS["hub-radio"]
        if not is_int(size) or not lo <= size <= hi:
            raise CatalogError("size_out_of_range")
        data = await self._get(session, release["file"], size, FILE_TIMEOUT)
        if len(data) != size:
            raise CatalogError("size_mismatch")
        if hashlib.sha256(data).hexdigest() != release["sha256"]:
            raise CatalogError("hash_mismatch")
        try:
            info = rc.verify_container(data, self._key_table(), board=board or BOARDS["hub-radio"],
                                       link_protocol=link_protocol, hub_version=hub_version)
        except rc.RadioContainerError as err:
            raise CatalogError(err.reason) from None
        lp = release.get("link_protocol") or {}
        bound = (release.get("build_id") == info["build_id"] and release.get("target") == info["target"]
                 and release.get("board") == info["board"] and (lp.get("min"), lp.get("max")) == info["protocol"]
                 and release.get("min_hub") == "%d.%d.%d" % info["hub_min"]
                 and parse_version(release.get("version")) is not None
                 and parse_version(release["version"])[:3] == tuple(info["version"]))
        if not bound:
            raise CatalogError("file_list_mismatch")
        return data, info

    async def async_fetch_notes(self, session, release, language):
        """The notes text of ``release`` in ``language`` ("nl" or else English), or None when it is not available or
        its SHA-256 differs from the list's (a notes file that does not match MUST NOT be shown)."""
        lang = "nl" if str(language or "en").split("-")[0].lower() == "nl" else "en"
        try:
            data = await self._get(session, release["notes"][lang], NOTES_MAX_BYTES)
            if hashlib.sha256(data).hexdigest() != release["notes_sha256"][lang]:
                return None
            return data.decode("utf-8")
        except (CatalogError, UnicodeDecodeError):
            return None
