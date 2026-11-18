"""The request to forget "boiler-forget 1": the second, tiny format of the Hub's automatic sharing (TESTER-AUTO-4A).

A person chooses "Wis wat ik heb gedeeld" in the Hub; the Hub sends this document by itself, the way it sends a bundle. Four members
and nothing else (forget.json: the allow-list; the same four names as the receiver on the website checks). The intake deletes what it
holds of that reference only when the report id AND the tester code belong to the same stored report (tools/testers/intake).

Also here: the three hashes the intake keeps instead of the identifiers once raw data is gone (a hash of the pair, of the id alone, of
the code alone), each with its own prefix so that one can never be mistaken for another. Standard library only.
"""
import datetime
import hashlib
import json
import re
from pathlib import Path

from . import fmt

SCHEMA = "boiler-forget 1"
DATA = Path(__file__).resolve().parent
_CACHE = {}


def spec():
    if "spec" not in _CACHE:
        _CACHE["spec"] = fmt.load_json_file(DATA / "forget.json")
    return _CACHE["spec"]


def members():
    return list(spec()["root"]["members"])


def parse(data):
    """(request, problems) of the bytes of a request file: size, UTF-8, JSON without duplicate keys or NaN, an object."""
    p = fmt.Problems()
    limit = spec()["limits"]["request_bytes"]
    if len(data) > limit:
        p.add("file", "size", f"larger than {limit} bytes")
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


def validate(doc):
    """The problems of a request (an empty list: valid). Strict: exactly the four members; a key that is not listed makes it invalid
    and its name is never echoed (a private string can be a key)."""
    p = fmt.Problems()
    if type(doc) is not dict:
        p.add("file", "type", "must be a JSON object")
        return p
    node = spec()["root"]["members"]
    if doc.get("schema") != SCHEMA:
        p.add("schema", "word", f'must be "{SCHEMA}"')
        return p
    missing = [k for k in node if k not in doc]
    extra = [k for k in doc if k not in node]
    if missing:
        p.add("file", "missing", "missing " + ", ".join(missing))
    if extra:
        p.add("file", "unknown_key", f"{len(extra)} unexpected key(s) (not in the allow-list)")
    for k, sub in node.items():
        if k in doc and k != "schema":
            v = doc[k]
            if type(v) is not str or not re.fullmatch(sub["pattern"], v):
                p.add(k, "pattern", "unexpected value")
    if "created" in doc and not any(x["path"] == "created" for x in p):
        try:
            datetime.date.fromisoformat(doc["created"])
        except ValueError:
            p.add("created", "pattern", "not a day")
    return p


# ---- what is kept instead of an identifier ----------------------------------------------------------------------------------------

def _h(tag, *parts):
    return hashlib.sha256((tag + "\0" + "\0".join(parts)).encode("utf-8")).hexdigest()


def hash_id(report_id):
    """Of the report id alone: finds a later bundle with the same reference and names a kept line in the owner's pages."""
    return _h("emthera-ref-v1", report_id)


def hash_pair(report_id, tester_code):
    """Of the pair: a request to forget matches a kept line only when BOTH values belong to it."""
    return _h("emthera-pair-v1", report_id, tester_code)


def hash_installation(tester_code):
    """Of the tester code alone: tells two installations apart, nothing else."""
    return _h("emthera-installation-v1", tester_code)


def label(ref):
    """How a kept line is named where a report id used to be (the owner's pages, a proposal): the start of the hash of its id."""
    return "ref:" + ref[:20]
