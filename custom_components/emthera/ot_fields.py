"""boiler.fields.v3: the values of an OpenTherm boiler, read-only (wire specification: OT-FIT-plan.md section 6).

A device whose boiler is OpenTherm publishes its values on ``fw/state/ot_fields/<g>`` (retained, group g = id // 16)
and its link on ``fw/config/boiler_link``. Every row is ``[id, raw16, age_ms, state]``; this module knows what an id
is from ONE generated table (ot_table.py, scripts/generate_ot_fields.py): no code per id. A value that means the same
as an existing boiler field (flow, return, modulation, pressure, hot water, outdoor, the status bits, the counters)
is handed to that field's cache record in the unit of that field, so its entity, history, dashboard tile and advice
stay the same ones; only what has no counterpart gets an entity of its own (v1_ot_fields.py).

Nothing here sends anything or grants anything: like every boiler field these values are read-only evidence.
"""
import json
import math
from collections import namedtuple

from .boiler_fields import INDEX_BY_NAME, spec
from .ot_table import POINTS, ROWS

CAPABILITY = "boiler.fields.v3"
PROFILE = "opentherm_observed"
FIELDS_TOPIC = "fw/state/ot_fields/"
LINK_TOPIC = "fw/config/boiler_link"
GROUPS = 8                    # g = id // 16, ids 0..127
MAX_ROWS = 16                 # one bucket
MAX_BYTES = 1200              # a group document (the firmware's maximumBoilerGroupBytes)
LINK_MAX_BYTES = 600
LINKS = ("ems", "opentherm", "none")
STAGES = ("reading", "testing", "awaiting_confirmation", "active", "stopping")
CONTACTS = ("never", "in_contact", "lost")
LIMIT_SOURCES = ("reported", "assumed", "none")
VALUE, NO_VALUE, STALE = 0, 1, 2

Point = namedtuple("Point", "id part kind bit key unit show concept factor cls device_class en nl")
POINT_LIST = tuple(Point(*row) for row in POINTS)
ROW_BY_ID = {row[0]: row for row in ROWS}
POINTS_BY_ID = {}
for _point in POINT_LIST:
    POINTS_BY_ID.setdefault(_point.id, []).append(_point)
CONCEPT_POINTS = tuple(point for point in POINT_LIST if point.concept)
OWN_POINTS = tuple(point for point in POINT_LIST if point.show and not point.concept)
# A status bit that feeds an existing sensor and has a name of its own on an OpenTherm boiler: {boiler field: key}.
OT_NAMES = {point.concept: "ot_" + point.key for point in POINT_LIST if point.concept and point.en}


def _integer(value, low=0, high=9007199254740991):
    return type(value) is int and low <= value <= high


def _small_number(value):
    """An identity part: a whole number or a version like 2.2, never a bool, NaN or infinity."""
    return type(value) in (int, float) and math.isfinite(value) and 0 <= value <= 65535


def readable(ot_id):
    """True for an id of the table that is verified, may be read and needs no index."""
    row = ROW_BY_ID.get(ot_id)
    return row is not None and row[2]


def validate_group(value, group):
    """The ``values`` of one ``fw/state/ot_fields/<g>`` document, or ValueError (the whole document is refused).

    Exactly four keys; profile opentherm_observed; at most 16 rows, ids strictly ascending, each a known verified
    readable id of this group; raw 0..65535; state 0 (a value: raw and age), 1 (the boiler has no value now: neither)
    or 2 (stale: the age, and the raw it had, may be missing); an age is never more than the snapshot's own clock.
    """
    if (type(value) is not dict or set(value) != {"schema", "sampled_at_ms", "profile", "fields"}
            or not _integer(value["schema"], 1, 1) or not _integer(value["sampled_at_ms"])
            or value["profile"] != PROFILE or not _integer(group, 0, GROUPS - 1)):
        raise ValueError("ot group schema")
    fields = value["fields"]
    if type(fields) is not list or len(fields) > MAX_ROWS:
        raise ValueError("ot group size")
    last = -1
    for field in fields:
        if type(field) is not list or len(field) != 4:
            raise ValueError("ot field shape")
        ot_id, raw, age, state = field
        if not _integer(ot_id, 0, 127) or ot_id <= last:
            raise ValueError("ot field order")
        last = ot_id
        if ot_id not in ROW_BY_ID:
            raise ValueError("ot field unknown id")
        if not readable(ot_id):
            raise ValueError("ot field not allowed")
        if ot_id // 16 != group:
            raise ValueError("ot field in the wrong group")
        if not _integer(state, 0, 2) or (raw is not None and not _integer(raw, 0, 65535)):
            raise ValueError("ot field value")
        if age is not None and not _integer(age, 0, value["sampled_at_ms"]):
            raise ValueError("ot field age")
        if state == VALUE and (raw is None or age is None):
            raise ValueError("ot field without value")
        if state == NO_VALUE and (raw is not None or age is not None):
            raise ValueError("ot field with a value")
        if state == STALE and raw is not None and age is None:
            raise ValueError("ot stale field without age")
    return value


def validate_group_document(raw, group):
    """A whole ``fw/state/ot_fields/<g>`` payload (text): its ``values``, or ValueError."""
    if not isinstance(raw, str) or not raw or len(raw) > MAX_BYTES:
        raise ValueError("ot group bytes")
    document = json.loads(raw)
    if (type(document) is not dict or set(document) != {"schema", "group", "values"}
            or not _integer(document["schema"], 1, 1) or type(document["group"]) is not int
            or document["group"] != group):
        raise ValueError("ot group envelope")
    return validate_group(document["values"], group)


def validate_link(raw):
    """``fw/config/boiler_link`` (retained): the document, or ValueError."""
    if not isinstance(raw, str) or not raw or len(raw) > LINK_MAX_BYTES:
        raise ValueError("boiler link bytes")
    value = json.loads(raw)
    keys = {"schema", "link", "stage", "contact", "identity", "config", "limit", "test"}
    if (type(value) is not dict or set(value) != keys or not _integer(value["schema"], 1, 1)
            or value["link"] not in LINKS or value["stage"] not in STAGES or value["contact"] not in CONTACTS):
        raise ValueError("boiler link schema")
    identity, config, limit, test = value["identity"], value["config"], value["limit"], value["test"]
    if (type(identity) is not dict or set(identity) != {"member", "type", "version", "ot", "digest"}
            or any(item is not None and not _small_number(item) for item in identity.values())
            or type(config) is not dict or set(config) != {"dhw", "modulating", "cooling", "ch2"}
            or any(type(item) is not bool for item in config.values())
            or type(limit) is not dict or set(limit) != {"c", "source"} or limit["source"] not in LIMIT_SOURCES
            or (limit["c"] is not None and (type(limit["c"]) not in (int, float) or not 0 <= limit["c"] <= 150))
            or type(test) is not dict or set(test) != {"passed", "at_age_s"} or type(test["passed"]) is not bool
            or (test["at_age_s"] is not None and not _integer(test["at_age_s"]))):
        raise ValueError("boiler link document")
    return value


def signed(raw, bits):
    return raw - (1 << bits) if raw >= 1 << (bits - 1) else raw


def part_of(point, raw):
    """The bits of ``raw`` this point is made of: the whole 16 bits, or one byte."""
    return raw if point.part == "w" else raw >> 8 & 255 if point.part == "hi" else raw & 255


def decode(point, raw):
    """The value of a point from the raw 16 bits of its id: a number, or for a bit 0 or 1."""
    part = part_of(point, raw)
    if point.kind == "bit":
        return part >> point.bit & 1
    if point.kind == "f88":
        return round(signed(raw, 16) / 256, 2)
    if point.kind == "s16":
        return signed(raw, 16)
    if point.kind == "s8":
        return signed(part, 8)
    return part


def concept_raw(point, raw):
    """The raw value of the boiler field this point feeds, in that field's own unit (boiler_fields.FIELDS)."""
    value = decode(point, raw)
    if point.kind == "bit":
        return value
    return round(value * spec(INDEX_BY_NAME[point.concept])[2] * point.factor)


class OtFieldCache:
    """What the boiler link reported: the last row of every id and the link document (retained configuration)."""

    def __init__(self):
        self.link = None   # the last valid fw/config/boiler_link document
        self.clear()

    def clear(self):
        self.records = {}   # id: (raw or None, observed_ms or None, state)
        self.sampled = {}   # group: sampled_at_ms of the newest document

    def __eq__(self, other):
        return (isinstance(other, OtFieldCache)
                and (self.link, self.records, self.sampled) == (other.link, other.records, other.sampled))

    __hash__ = None

    def value(self, point):
        """The decoded value of a point, only for a row that holds one now (state 0)."""
        record = self.records.get(point.id)
        if record is None or record[2] != VALUE or record[0] is None:
            return None
        return decode(point, record[0])

    def has_value(self, point):
        record = self.records.get(point.id)
        return record is not None and record[2] == VALUE and record[0] is not None


def apply_group(cache, value, group, now):
    """A validated group (``validate_group``) into a BoilerFieldCache: the id rows, and their share of the existing
    boiler fields. Returns False for a document older than one already seen (retained redelivery)."""
    sampled = value["sampled_at_ms"]
    ot = cache.ot
    if sampled < ot.sampled.get(group, -1):
        return False
    if not cache.state_mode:
        cache.reset()
        cache.state_mode = True
    ot.sampled[group] = sampled
    listed = {field[0] for field in value["fields"]}
    for gone in [ot_id for ot_id in ot.records if ot_id // 16 == group and ot_id not in listed]:
        # No longer supported by the boiler (a group document lists every supported id of its bucket).
        del ot.records[gone]
        for point in POINTS_BY_ID.get(gone, ()):
            if point.concept:
                _store(cache, point, (INDEX_BY_NAME[point.concept], None, None, 0, 0), None, sampled, now)
    for ot_id, raw, age, state in value["fields"]:
        observed = sampled - age if age is not None else None
        ot.records[ot_id] = (raw, observed, state)
        for point in POINTS_BY_ID.get(ot_id, ()):
            if not point.concept:
                continue
            index = INDEX_BY_NAME[point.concept]
            if state == VALUE:
                field = (index, concept_raw(point, raw), observed, 0, ot_id)
            else:  # the boiler has no value now, or it is stale: seen, without a value (an entity shows unknown)
                field = (index, None, observed if observed is not None else sampled, 0, ot_id)
            _store(cache, point, field, math.inf, sampled, now)
    cache.profile = PROFILE
    cache.sampled = max(cache.sampled, sampled)
    cache.received = now
    cache.invalid = False
    cache.sequence += 1
    if cache.first_state_at is None:
        cache.first_state_at = now
    return True


def _store(cache, point, field, deadline, sampled, now):
    index = field[0]
    if sampled < cache.sampled_by_index.get(index, -1):
        return
    cache.records[index] = (tuple(field), deadline)
    cache.sampled_by_index[index] = sampled
    cache.read_at[index] = (sampled, now)
