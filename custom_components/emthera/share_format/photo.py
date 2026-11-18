"""The type-plate photo: take in a JPEG and write it again WITHOUT its hidden data (where and when it was taken, the
camera, a thumbnail, comments, anything after the picture). Pure Python, no imaging library: the file is read as its
JPEG segments and only the ones that draw the picture are copied, byte for byte; the scan data is never decoded or changed.
What is kept: quantisation tables, frame headers, Huffman tables, restart interval and the scans (header and data), plus a plain JFIF
header without a thumbnail. Everything else (every APPn: Exif, XMP, ICC, IPTC, MakerNote; comments; unknown markers;
bytes after the end of the picture) is dropped. The result is checked by the same rule the checker applies
(rules.chk_photo_clean) in the tests. The original is never kept: the caller passes bytes in and keeps only the result.
"""
import hashlib

MAX_INPUT_BYTES = 2 * 1024 * 1024
MAX_OUTPUT_BYTES = 3 * 1024 * 1024  # = allowlist limits.photo_bytes
KEEP = frozenset([0xDB, 0xC4, 0xCC, 0xDD, 0xDA] + [m for m in range(0xC0, 0xD0) if m not in (0xC4, 0xC8, 0xCC)])
SOF = frozenset(m for m in range(0xC0, 0xD0) if m not in (0xC4, 0xC8, 0xCC))
JFIF_PLAIN = bytes.fromhex("FFE000104A46494600") + b"\x01\x01\x00" + b"\x00\x01\x00\x01\x00\x00"  # version 1.01, no units, 1:1, no thumbnail
WHY = ("not_a_jpeg", "damaged", "too_large")


class PhotoError(ValueError):
    """The reason is one of WHY (a word the screen explains), never the content."""

    def __init__(self, reason):
        super().__init__(reason)
        self.reason = reason


def clean(data):
    """The JPEG bytes of the same picture without metadata, or raises PhotoError."""
    if type(data) is not bytes or data[:3] != b"\xff\xd8\xff":
        raise PhotoError("not_a_jpeg")
    if len(data) > MAX_INPUT_BYTES:
        raise PhotoError("too_large")
    out = bytearray(b"\xff\xd8")
    i, n = 2, len(data)
    frame = scans = False
    while True:
        # the next marker: skip fill bytes
        while i < n and data[i] == 0xFF and i + 1 < n and data[i + 1] == 0xFF:
            i += 1
        if i + 2 > n or data[i] != 0xFF:
            raise PhotoError("damaged")
        marker = data[i + 1]
        if marker == 0xD9:  # end of the picture: whatever follows is dropped
            break
        if marker in (0x01, 0xD8) or 0xD0 <= marker <= 0xD7:
            raise PhotoError("damaged")
        if i + 4 > n:
            raise PhotoError("damaged")
        length = int.from_bytes(data[i + 2:i + 4], "big")
        end = i + 2 + length
        if length < 2 or end > n:
            raise PhotoError("damaged")
        segment = data[i:end]
        if marker == 0xE0 and segment == JFIF_PLAIN:
            out += segment
        elif marker in KEEP:
            out += segment
            frame = frame or marker in SOF
        i = end
        if marker == 0xDA:  # a scan: its entropy-coded data runs to the next real marker
            if not frame:
                raise PhotoError("damaged")
            j = i
            while j < n:
                if data[j] == 0xFF and j + 1 < n and data[j + 1] not in (0x00, 0xFF) and not 0xD0 <= data[j + 1] <= 0xD7:
                    break
                j += 1
            if j >= n:
                raise PhotoError("damaged")
            out += data[i:j]
            i, scans = j, True
    if not scans or not frame:
        raise PhotoError("damaged")
    out += b"\xff\xd9"
    if len(out) > MAX_OUTPUT_BYTES:
        raise PhotoError("too_large")
    return bytes(out)


def describe(clean_bytes):
    """What the report says about the photo: size and SHA-256 (the file name is the caller's)."""
    return {"bytes": len(clean_bytes), "sha256": hashlib.sha256(clean_bytes).hexdigest()}
