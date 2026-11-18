"""The radio chip's signed container, checked in Python before anything is sent to the Hub (S-HA-2 package C).

The Hub's radio chip (an ESP32-C6) gets its firmware as ONE signed file, the container (the Hub's docs/engineering/
RADIO-CONTAINER.md; the Hub's own reader is src/radio/RadioContainer.h). Home Assistant checks the same rules first, so
a bad file is refused with a clear reason before an upload, and the Hub checks everything again when it arrives:

1. the 32-byte header (magic ``EMRADIOC``, versions, lengths bounded before they are trusted),
2. the manifest: every text, version, build id, link protocol range, lowest Hub version, part table and the canonical layout,
3. the policy: target ``esp32c6``, this Hub's board, the link protocol range the Hub speaks, the lowest Hub version
   (an unknown Hub version fails closed),
4. the ECDSA P-256 signature over ``"emthera-radio-image-v1" NUL + manifest`` with key slot 0 or 1 (standard
   ``cryptography``; the key table is the update list's, all zero until the owner provisions it: a zero slot fails closed),
5. the bytes after the prefix: zero padding, every part's SHA-256, nothing after the end.

All numbers are little endian. Nothing is allocated from a length the file states before that length is bounded. The
module reads bytes and decides; it sends nothing and keeps nothing.
"""
from __future__ import annotations

import hashlib
import struct

from . import update_catalog as catalog

MAGIC = b"EMRADIOC"
CONTAINER_VERSION = 1
SCHEMA = 1
HEADER_BYTES = 32
MANIFEST_FIXED = 184
PART_ENTRY = 64
MAX_PARTS = 8
PART_NAMES = ("bootloader", "partition_table", "app")
SIGNATURE_BLOCK = 65
MAX_MANIFEST = MANIFEST_FIXED + MAX_PARTS * PART_ENTRY
CAPACITY = 0x2FE000                    # the most bytes the Hub's store keeps (the list's bound for hub-radio is the same)
TARGET = "esp32c6"
BOARD = "emthera_hub_v1"
FLASH_BYTES = 0x800000
BOOT_MAX, TABLE_MAX, APP_SLOT = 0x8000, 0x1000, 0x200000
TABLE_OFFSET, APP_MIN, APP_ALIGN = 0x8000, 0x10000, 0x10000
SIGN_DOMAIN = b"emthera-radio-image-v1\x00"
LINK_PROTOCOL = (1, 1)                 # the link protocol major(s) this Hub speaks until its status says otherwise


class RadioContainerError(Exception):
    """The container was refused; ``reason`` is the stable name (the Hub's own names where it has one)."""

    def __init__(self, reason):
        super().__init__(reason)
        self.reason = reason


def _align16(n):
    return (n + 15) // 16 * 16


def _text(raw):
    """Printable ASCII up to the first NUL, only NULs after it, at least one character, a NUL as the last byte."""
    end = raw.find(b"\x00")
    if end <= 0 or end == len(raw) or any(raw[end:]) or any(c < 0x20 or c > 0x7E for c in raw[:end]):
        raise RadioContainerError("bad_text")
    return raw[:end].decode("ascii")


def parse_prefix(c):
    """Steps 1 and 2: the header and the manifest of ``c`` (bytes). Returns the facts; raises RadioContainerError."""
    if len(c) < HEADER_BYTES:
        raise RadioContainerError("truncated")
    if c[:8] != MAGIC:
        raise RadioContainerError("bad_magic")
    version, header, total, mlen, slen, r0, r1 = struct.unpack_from("<HHIIIII", c, 8)
    if version != CONTAINER_VERSION:
        raise RadioContainerError("bad_container_version")
    if header != HEADER_BYTES:
        raise RadioContainerError("bad_header")
    if r0 or r1:
        raise RadioContainerError("reserved_not_zero")
    if not MANIFEST_FIXED <= mlen <= MAX_MANIFEST:
        raise RadioContainerError("manifest_length")
    if slen != SIGNATURE_BLOCK:
        raise RadioContainerError("signature_length")
    prefix = HEADER_BYTES + mlen + slen
    if total < prefix + len(PART_NAMES) or total > CAPACITY:
        raise RadioContainerError("size_out_of_range")
    if len(c) < prefix:
        raise RadioContainerError("truncated")
    m = c[HEADER_BYTES:HEADER_BYTES + mlen]
    schema, flags = struct.unpack_from("<HH", m, 0)
    if schema != SCHEMA:
        raise RadioContainerError("bad_schema")
    if flags:
        raise RadioContainerError("bad_flags")
    count = struct.unpack_from("<H", m, 176)[0]
    if count != len(PART_NAMES):
        raise RadioContainerError("part_count")
    if mlen != MANIFEST_FIXED + count * PART_ENTRY:
        raise RadioContainerError("manifest_length_mismatch")
    if struct.unpack_from("<H", m, 178)[0] or struct.unpack_from("<I", m, 180)[0]:
        raise RadioContainerError("reserved_not_zero")
    out = {"target": _text(m[4:20]), "board": _text(m[20:52])}
    v = struct.unpack_from("<4H", m, 52)
    if v[3] or not any(v[:3]):
        raise RadioContainerError("bad_version")
    out["version"] = v[:3]
    out["version_text"] = _text(m[60:92])
    out["build_id"] = m[92:124].hex()
    if not any(m[92:124]):
        raise RadioContainerError("zero_build_id")
    low, high = struct.unpack_from("<2H", m, 124)
    if not low or high < low:
        raise RadioContainerError("bad_protocol_range")
    out["protocol"] = (low, high)
    h = struct.unpack_from("<4H", m, 128)
    if h[3]:
        raise RadioContainerError("reserved_not_zero")
    out["hub_min"] = h[:3]
    again, app_size = struct.unpack_from("<II", m, 136)
    if again != total:
        raise RadioContainerError("total_mismatch")
    app_sha = m[144:176]
    cursor, parts = prefix, []
    limits = (BOOT_MAX, TABLE_MAX, APP_SLOT)
    for i, name in enumerate(PART_NAMES):
        entry = m[MANIFEST_FIXED + i * PART_ENTRY:MANIFEST_FIXED + (i + 1) * PART_ENTRY]
        try:
            named = _text(entry[:16])
        except RadioContainerError:
            raise RadioContainerError("part_name") from None
        if named != name:
            raise RadioContainerError("part_name")
        flash, size, offset, reserved = struct.unpack_from("<IIII", entry, 16)
        if reserved:
            raise RadioContainerError("reserved_not_zero")
        if not size or size > limits[i]:
            raise RadioContainerError("part_size")
        if (i == 0 and flash != 0) or (i == 1 and flash != TABLE_OFFSET):
            raise RadioContainerError("part_flash")
        if i == 2 and (flash < APP_MIN or flash % APP_ALIGN or flash + size > FLASH_BYTES):
            raise RadioContainerError("part_flash")
        if offset < cursor:
            raise RadioContainerError("part_container_overlap")
        if offset != _align16(cursor):
            raise RadioContainerError("part_container_gap")
        cursor = offset + size
        if cursor > total:
            raise RadioContainerError("part_container_range")
        parts.append({"name": name, "flash_offset": flash, "size": size, "container_offset": offset, "sha256": entry[32:64].hex()})
    if cursor != total:
        raise RadioContainerError("total_mismatch")
    if app_size != parts[2]["size"] or app_sha.hex() != parts[2]["sha256"]:
        raise RadioContainerError("app_mismatch")
    out.update(parts=parts, total_size=total, app_size=app_size, prefix=prefix, manifest=bytes(m),
               key_slot=c[prefix - SIGNATURE_BLOCK], signature=bytes(c[prefix - 64:prefix]))
    return out


def check_policy(info, *, board=BOARD, link_protocol=LINK_PROTOCOL, hub_version=None):
    """Step 3, the Hub's rules: target, board, the link protocol range that meets the Hub's, and the lowest Hub version.
    ``hub_version``: (major, minor, patch) of this Hub, or None when it is not known (that fails closed)."""
    if info["target"] != TARGET:
        raise RadioContainerError("target_mismatch")
    if info["board"] != board:
        raise RadioContainerError("board_mismatch")
    low, high = info["protocol"]
    if high < link_protocol[0] or low > link_protocol[1]:
        raise RadioContainerError("protocol_unsupported")
    if hub_version is None:
        raise RadioContainerError("hub_version_unknown")
    if tuple(hub_version) < tuple(info["hub_min"]):
        raise RadioContainerError("hub_too_old")


def check_signature(info, keys):
    """Step 4: one ECDSA verification over the domain bytes and the manifest, with the key of slot 0 or 1."""
    slot = info["key_slot"]
    if slot not in (0, 1):
        raise RadioContainerError("key_slot")
    point = (keys or {}).get(slot)
    if not catalog._provisioned(point):
        raise RadioContainerError("key_not_provisioned")
    raw = info["signature"]
    if not any(raw[:32]) or not any(raw[32:]):
        raise RadioContainerError("signature_invalid")
    result = catalog.check_signature(point, SIGN_DOMAIN + info["manifest"], raw)
    if result == "bad_key":
        raise RadioContainerError("key_not_provisioned")
    if result != "ok":
        raise RadioContainerError("signature_invalid")


def check_parts(c, info):
    """Step 5: the bytes after the prefix: zero padding, every part's SHA-256, nothing before the end or after it."""
    if len(c) < info["total_size"]:
        raise RadioContainerError("incomplete")
    if len(c) > info["total_size"]:
        raise RadioContainerError("trailing_data")
    position = info["prefix"]
    for part in info["parts"]:
        if any(c[position:part["container_offset"]]):
            raise RadioContainerError("bad_padding")
        data = c[part["container_offset"]:part["container_offset"] + part["size"]]
        if hashlib.sha256(data).hexdigest() != part["sha256"]:
            raise RadioContainerError("hash_mismatch")
        position = part["container_offset"] + part["size"]


def verify_container(data, keys, *, board=BOARD, link_protocol=LINK_PROTOCOL, hub_version=None):
    """All five steps in the Hub's order; returns the facts of the container, raises RadioContainerError with the first
    reason. Nothing is accepted that the Hub would refuse for the same reason."""
    c = bytes(data)
    info = parse_prefix(c)
    check_policy(info, board=board, link_protocol=link_protocol, hub_version=hub_version)
    check_signature(info, keys)
    check_parts(c, info)
    return info


def link_build_id(build_id_hex):
    """The 32-bit build id the radio chip's hello carries: the FIRST FOUR BYTES of the manifest's build id, little endian,
    written as the Hub's status does (``0x%08X``)."""
    return "0x%08X" % struct.unpack_from("<I", bytes.fromhex(build_id_hex), 0)[0]
