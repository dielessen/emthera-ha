"""The report format "boiler-share 2", ONE implementation for everyone who handles it: the strict reader, the writer's
allow-list filter, the id makers, the reader of old "boiler-share 1" reports and the JSON schema generator.

This module ships with the integration (the Home Assistant side builds and checks its own report with it, before the
tester sees it) and the tools of the owner's computer (tools/emsplus/share2.py, check_share2.py) load the very same file:
there is no copy. The data lives beside it: allowlist.json (every member: type, range or words), schema.json (generated
from it) and completeness.json (the rule table per boiler link, evaluated by rules.py). Standard library only; nothing
here reads a network or a device. Reading the data files is blocking: call allowlist() / completeness() once from an
executor before using this inside Home Assistant's event loop (tester_run.async_prepare does).
"""
import hashlib
import json
import re
import secrets
from pathlib import Path

DATA = Path(__file__).resolve().parent
SCHEMA = "boiler-share 2"
SCHEMA_V1 = "boiler-share 1"
MAX_DEPTH = 24
# Belt and braces, as in format 1: no string of a report may look like network data or a free text.
NETWORK = re.compile(r"[0-9]{1,3}(\.[0-9]{1,3}){3}|([0-9A-Fa-f]{2}[:-]){5}[0-9A-Fa-f]{2}|@|://|\s")
BASE32 = "abcdefghijklmnopqrstuvwxyz234567"
MISSING = object()


def load_json_file(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


_CACHE = {}


def allowlist():
    if "allow" not in _CACHE:
        _CACHE["allow"] = load_json_file(DATA / "allowlist.json")
    return _CACHE["allow"]


def completeness():
    if "rules" not in _CACHE:
        _CACHE["rules"] = load_json_file(DATA / "completeness.json")
    return _CACHE["rules"]


class Problems(list):
    """Problems as dicts {path, code, what}; codes are stable words a program can switch on."""

    def add(self, path, code, what):
        self.append({"path": path, "code": code, "what": what})

    def lines(self):
        return [f"{p['path']}: {p['what']}" for p in self]


# ---- reading a file strictly ------------------------------------------------------------------------------------------

def _no_duplicates(pairs):
    out = {}
    for k, v in pairs:
        if k in out:
            raise ValueError(f"duplicate key {k}")
        out[k] = v
    return out


def _no_constant(name):
    raise ValueError(f"{name} is not allowed")


def parse(data):
    """(document, problems) of the bytes of a report file: size, UTF-8, JSON without duplicate keys or NaN."""
    p = Problems()
    limit = allowlist()["limits"]["report_bytes"]
    if len(data) > limit:
        p.add("file", "size", f"larger than {limit // 1024} KB")
        return None, p
    try:
        doc = json.loads(data.decode("utf-8"), object_pairs_hook=_no_duplicates, parse_constant=_no_constant)
    except (UnicodeDecodeError, ValueError, RecursionError) as err:
        p.add("file", "json", f"is not valid JSON ({type(err).__name__})")
        return None, p
    if type(doc) is not dict:
        p.add("file", "json", "must be a JSON object")
        return None, p
    return doc, p


def node_of(allow, node):
    """A node with its reference resolved (a reference may add "null")."""
    if "ref" in node:
        base = dict(allow["defs"][node["ref"]])
        if node.get("null"):
            base["null"] = True
        return base
    return node


def _walk(p, path, v, node, allow, depth, nullable_here=False):
    node = node_of(allow, node)
    if v is None:
        if node.get("null") or nullable_here:
            return
        p.add(path, "null", "must not be null")
        return
    if depth > MAX_DEPTH:
        p.add(path, "depth", "nested too deep")
        return
    kind = node["t"]
    if kind == "const":
        if v != node["v"]:
            p.add(path, "word", f'must be "{node["v"]}"')
    elif kind == "int":
        if type(v) is not int or not node["min"] <= v <= node["max"]:
            p.add(path, "range", f"must be a whole number from {node['min']} to {node['max']}" + (" or null" if node.get("null") else ""))
    elif kind == "bool":
        if type(v) is not bool:
            p.add(path, "type", "must be true or false")
    elif kind == "word":
        if type(v) is not str or v not in node["words"]:
            p.add(path, "word", "unexpected value")
    elif kind == "text":
        if type(v) is not str or not re.fullmatch(node["pattern"], v):
            p.add(path, "pattern", "unexpected value")
        elif NETWORK.search(v):
            p.add(path, "network_like", "a text looks like an address, a name or free text")
    elif kind == "object":
        if type(v) is not dict:
            p.add(path, "type", "must be an object")
            return
        optional = set(node.get("optional", ()))
        missing = [k for k in node["members"] if k not in v and k not in optional]
        extra = sorted(set(v) - set(node["members"]))
        if missing:
            p.add(path, "missing", "missing " + ", ".join(missing))
        if extra:  # the names are not echoed: a private string can be a key
            p.add(path or "file", "unknown_key", f"{len(extra)} unexpected key(s) (not in the allow-list)")
        for k, sub in node["members"].items():
            if k in v:
                _walk(p, f"{path}.{k}" if path else k, v[k], sub, allow, depth + 1,
                      nullable_here=(depth == 0 and k in NULLABLE_NOW))
    elif kind == "list":
        if type(v) is not list or len(v) > node["max"]:
            p.add(path, "size", f"must be a list of at most {node['max']}")
            return
        for idx, item in enumerate(v):
            _walk(p, f"{path}[{idx}]", item, node["items"], allow, depth + 1)
    elif kind == "ext":
        if type(v) is not dict or len(v) > node["max"]:
            p.add(path, "size", f"must be an object of at most {node['max']} members")
            return
        for k, item in v.items():
            if not re.fullmatch(node["key"], k):
                p.add(path, "unknown_key", "an ext key must be x_<name>")
            elif type(item) is bool or (type(item) is int and abs(item) <= 2 ** 53):
                pass
            else:
                p.add(path, "pattern", "an ext value is a number or true/false (a word could carry private text)")
    else:  # pragma: no cover (the allow-list is ours)
        raise ValueError(f"unknown node type {kind}")


# The members that may be null in a converted (legacy) report; set per call of validate (single-threaded tool).
NULLABLE_NOW = frozenset()


def _get(doc, dotted):
    node = doc
    for part in dotted.split("."):
        if type(node) is not dict or part not in node:
            return MISSING
        node = node[part]
    return node


def validate(doc, allow=None):
    """The problems of a boiler-share 2 document (an empty list: well formed and consistent). Strict: a key that is
    not in the allow-list, in any object but `ext`, makes the whole file invalid."""
    global NULLABLE_NOW
    allow = allow or allowlist()
    p = Problems()
    if type(doc) is not dict:
        p.add("file", "type", "must be a JSON object")
        return p
    legacy = (doc.get("run") or {}).get("state") == allow["legacy"]["state"] if type(doc.get("run")) is dict else False
    NULLABLE_NOW = frozenset(allow["legacy"]["nullable_only_when_legacy"]) if legacy else frozenset()
    try:
        if doc.get("schema") != SCHEMA:
            p.add("schema", "word", f'must be "{SCHEMA}"')
            return p
        _walk(p, "", doc, allow["root"], allow, 0)
    finally:
        NULLABLE_NOW = frozenset()
    if p:
        return p
    _cross(p, doc, allow, legacy)
    return p


def _cross(p, doc, allow, legacy):
    if doc["schema_minor"] > allow["minor"]:
        p.add("schema_minor", "newer_minor", f"newer than this reader knows (it reads up to {allow['minor']}); update the reader")
    rules = allow["link_rules"][doc["link"]]
    for path in rules["require"]:
        if _get(doc, path) is MISSING:
            p.add(path, "link", f"required for link {doc['link']}")
    for path in rules["forbid"]:
        if _get(doc, path) is not MISSING:
            p.add(path, "link", f"not allowed for link {doc['link']}")
    if doc["board"] not in rules["boards"] and not legacy:
        p.add("board", "link", f"link {doc['link']} does not exist on board {doc['board']}")
    if doc["boiler"]["family"] not in rules["families"]:
        p.add("boiler.family", "link", f"family {doc['boiler']['family']} does not fit link {doc['link']}")
    rec = doc["recording"]
    if rec["kind"] is not None and rec["kind"] not in rules["recording_kinds"]:
        p.add("recording.kind", "link", f"recording kind {rec['kind']} does not fit link {doc['link']}")
    if (rec["file"] is None) != (rec["sha256"] is None) or (rec["file"] is None) != (rec["bytes"] is None) \
            or (rec["file"] is None) != (rec["kind"] is None):
        p.add("recording", "cross", "a file needs its kind, size and sha256, and only a file has them")
    if not rec["chosen"] and rec["file"] is not None:
        p.add("recording", "cross", "a recording that was not chosen cannot have a file")
    nullable = allow["legacy"]["nullable_only_when_legacy"]
    if legacy:
        for k in allow["legacy"]["required_when_legacy"]:
            if k not in doc:
                p.add(k, "legacy", "a converted report names its source")
    else:
        for k in allow["legacy"]["forbidden_unless_legacy"]:
            if k in doc:
                p.add(k, "legacy", "only a converted report has this")
        for k in nullable:
            if doc.get(k) is None:
                p.add(k, "null", "must not be null")
        if doc["consent"] is not None and doc["consent"]["yes"] is not True:
            p.add("consent.yes", "consent", "a report is only valid with consent")
        run = doc["run"]
        if run["state"] == "complete" and run["missing"]:
            p.add("run.missing", "cross", "a complete run lists nothing missing")
        human = doc["human"]
        if human is not None:
            state = human["display_state"]
            if (state in ("code", "code_and_temperature")) != (human["display_code_typed"] is not None):
                p.add("human.display_code_typed", "cross", "a typed code goes with the display states code and code_and_temperature, and only those")
            if (state in ("temperature", "code_and_temperature")) != (human["display_temp_typed"] is not None):
                p.add("human.display_temp_typed", "cross", "a typed temperature goes with the display states temperature and code_and_temperature, and only those")
    if doc["link"] == "opentherm" and doc["recording"]["kind"] not in (None, "otrec 1"):
        p.add("recording.kind", "link", "an OpenTherm report carries an otrec recording")


# ---- writing a file: the allow-list as a filter -------------------------------------------------------------------------

def _project(v, node, allow, depth=0):
    """The value fitted to a node, or MISSING when it does not fit and may not be null. Never raises. Whatever is not
    in the allow-list is left out; whatever does not fit is dropped or replaced by "other"/null."""
    node = node_of(allow, node)
    kind = node["t"]
    nullable = bool(node.get("null"))
    if depth > MAX_DEPTH:
        return None if nullable else MISSING
    if v is None:
        return None if nullable else MISSING
    if kind == "const":
        return v if v == node["v"] else MISSING
    if kind == "int":
        return v if type(v) is int and node["min"] <= v <= node["max"] else (None if nullable else MISSING)
    if kind == "bool":
        return v if type(v) is bool else (None if nullable else MISSING)
    if kind == "word":
        if type(v) is str and v in node["words"]:
            return v
        if "other" in node["words"]:
            return "other"
        return None if nullable else MISSING
    if kind == "text":
        if type(v) is str and re.fullmatch(node["pattern"], v) and not NETWORK.search(v):
            return v
        return None if nullable else MISSING
    if kind == "object":
        if type(v) is not dict:
            return None if nullable else MISSING
        out = {}
        optional = set(node.get("optional", ()))
        for k, sub in node["members"].items():
            r = _project(v[k], sub, allow, depth + 1) if k in v else MISSING
            if r is not MISSING:
                out[k] = r
            elif k not in optional:
                return None if nullable else MISSING  # a required member that does not fit: the object is not written
        return out
    if kind == "list":
        if type(v) is not list:
            return None if nullable else MISSING
        out = []
        for item in v[:node["max"]]:
            r = _project(item, node["items"], allow, depth + 1)
            if r is not MISSING:
                out.append(r)
        return out
    if kind == "ext":
        out = {}
        if type(v) is dict:
            for k, item in v.items():
                if len(out) < node["max"] and type(k) is str and re.fullmatch(node["key"], k):
                    if type(item) is bool or (type(item) is int and abs(item) <= 2 ** 53):
                        out[k] = item
        return out
    return MISSING


def project(doc, allow=None):
    """What a maker may write of a draft report: only allow-listed members, only values that fit. The result may be
    incomplete (a member that did not fit is absent); validate() then refuses it instead of letting anything private
    through."""
    allow = allow or allowlist()
    out = _project(doc, allow["root"], allow)
    return {} if out is MISSING else out


def new_report_id():
    """26 random characters (130 bit), never derived from data."""
    return "".join(secrets.choice(BASE32) for _ in range(26))


def new_tester_code():
    """13 random characters (65 bit): stored once per installation by the maker."""
    return "".join(secrets.choice(BASE32) for _ in range(13))


def dump(doc):
    return (json.dumps(doc, indent=1, sort_keys=False, ensure_ascii=True) + "\n").encode("utf-8")


# ---- boiler-share 1 stays readable ----------------------------------------------------------------------------------------

LINK_OF_FAMILY = {"plus": "ems_plus", "classic": "ems_classic"}


def convert_v1(v1, source_bytes=None):
    """A validated boiler-share 1 document as format 2 input: run.state "legacy", what format 1 never had is null or
    empty, and `converted` names the source. It can never count as a complete format 2 report: the checker judges it
    by the old rules only. The caller validates the v1 document first (check_share.validate)."""
    family = v1["boiler"]["family"]
    link = LINK_OF_FAMILY.get(family, "unknown")
    probe = v1.get("probe")
    last = (probe or {}).get("last")
    rec = v1["recording"]
    digest = hashlib.sha256(source_bytes if source_bytes is not None else
                            json.dumps(v1, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
    ems = {
        "fields": v1["fields"], "telegrams": v1["telegrams"], "settings": v1["settings"], "writes_to_boiler": [],
        "limit": {"c": None, "source": "none"}, "view": None, "fault": {"seen": False, "code": None, "class": "none"},
    }
    doc = {
        "schema": SCHEMA, "schema_minor": 0, "report_id": None, "tester_code": None, "created": v1["created"],
        "board": "unknown", "link": link,
        "software": {"firmware": v1["software"]["e32"], "integration": v1["software"]["integration"],
                     "table": v1["software"]["table"], "table_current": v1["software"]["table_current"]},
        "consent": None,
        "run": {"state": "legacy", "minutes": min(60, rec["seconds"] // 60), "marks": [], "phases_seen": [], "missing": []},
        "human": None,
        "boiler": {"product": v1["boiler"]["product"], "version": v1["boiler"]["version"], "brand": v1["boiler"]["brand"],
                   "family": family if family in ("plus", "classic") else "unknown", "row": v1["boiler"]["row"]},
        "match": v1["match"],
        "link_data": {"ems": ems},
        "test": {"kind": "plus_probe" if last else "none", "source": "legacy" if last else "none", "at_day": None,
                 "outcome": last["outcome"] if last else "none", "detail": last["detail"] if last else "", "steps": [],
                 "readback": probe["readback"] if probe else None, "reverted": last["reverted"] if last else None,
                 "probe": probe, "opentherm": None},
        "recording": {"state": rec["state"], "chosen": rec["file"] is not None,
                      "kind": "emsrec 1" if rec["file"] is not None else None, "file": rec["file"], "bytes": rec["bytes"],
                      "sha256": rec["sha256"], "seconds": rec["seconds"], "frames": rec["frames"], "polls": rec["polls"],
                      "dropped": rec["dropped"]},
        "converted": {"from": SCHEMA_V1, "source_sha256": digest},
    }
    if v1.get("active_control") is not None:
        doc["active_control"] = v1["active_control"]
    return doc


# ---- the JSON schema, generated -------------------------------------------------------------------------------------------

def _schema_node(node, allow, nullable_extra=False):
    node = node_of(allow, node)
    kind = node["t"]
    if kind == "const":
        out = {"const": node["v"]}
    elif kind == "int":
        out = {"type": "integer", "minimum": node["min"], "maximum": node["max"]}
    elif kind == "bool":
        out = {"type": "boolean"}
    elif kind == "word":
        out = {"enum": list(node["words"])}
    elif kind == "text":
        out = {"type": "string", "pattern": "^(?:" + node["pattern"] + ")$"}
    elif kind == "object":
        props = {k: _schema_node(sub, allow) for k, sub in node["members"].items()}
        optional = set(node.get("optional", ()))
        out = {"type": "object", "properties": props, "required": [k for k in node["members"] if k not in optional],
               "additionalProperties": False}
    elif kind == "list":
        out = {"type": "array", "items": _schema_node(node["items"], allow), "maxItems": node["max"]}
    elif kind == "ext":
        out = {"type": "object", "maxProperties": node["max"], "additionalProperties": False,
               "patternProperties": {"^(?:" + node["key"] + ")$": {"anyOf": [
                   {"type": "boolean"}, {"type": "integer", "minimum": -(2 ** 53), "maximum": 2 ** 53}]}}}
    else:  # pragma: no cover
        raise ValueError(kind)
    if node.get("null") or nullable_extra:
        return {"anyOf": [out, {"type": "null"}]}
    return out


def json_schema(allow=None):
    """The JSON Schema (draft 2020-12) of the allow-list: members, types, ranges, words, patterns and the link rules.
    The checks a schema cannot say (consent, recordings, the legacy rules) are the reader's (validate)."""
    allow = allow or allowlist()
    root = _schema_node(allow["root"], allow)
    legacy_null = set(allow["legacy"]["nullable_only_when_legacy"])
    for k in legacy_null:
        root["properties"][k] = _schema_node(allow["root"]["members"][k], allow, nullable_extra=True)
    clauses = []
    for link, rules in allow["link_rules"].items():
        then = {"allOf": []}
        for path in rules["require"]:
            then["allOf"].append(_path_clause(path, required=True))
        for path in rules["forbid"]:
            then["allOf"].append(_path_clause(path, required=False))
        then["properties"] = {"board": {"enum": rules["boards"]}, "boiler": {"properties": {"family": {"enum": rules["families"]}}}}
        if not then["allOf"]:
            del then["allOf"]
        clauses.append({"if": {"properties": {"link": {"const": link}}, "required": ["link"]}, "then": then})
    root["allOf"] = clauses
    root["$schema"] = "https://json-schema.org/draft/2020-12/schema"
    root["title"] = "boiler-share 2 (minor %d)" % allow["minor"]
    root["$comment"] = ("Generated from allowlist.json by tools/emsplus/share2.py; do not edit. report_id, tester_code, "
                        "consent and human are null only in a converted (run.state legacy) report; the reader, not this "
                        "schema, enforces that and the checks across members.")
    return root


def _path_clause(path, required):
    parts = path.split(".")
    leaf = {"required": [parts[-1]]}
    clause = leaf if required else {"not": leaf}
    for part in reversed(parts[:-1]):
        clause = {"properties": {part: clause}, "required": [part]} if required else {"properties": {part: clause}}
    return clause


def schema_text(allow=None):
    return json.dumps(json_schema(allow), indent=1) + "\n"
