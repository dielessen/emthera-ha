"""The consent text of the tester program: one source as data (consent.json), English and Dutch, with the version that
goes into the report. Pure: the caller loads the JSON bytes (an executor job inside Home Assistant)."""
import hashlib
import json
from pathlib import Path

PATH = Path(__file__).with_name("consent.json")
LANGUAGES = ("en", "nl")


def load(data=None):
    return json.loads(data if data is not None else PATH.read_text(encoding="utf-8"))


def version(doc):
    return doc["version"]


def text_hash(doc, which=None):
    """The SHA-256 of the texts of both languages (a change of a word changes it, so the version must go up)."""
    payload = json.dumps({lang: doc[lang] for lang in LANGUAGES}, sort_keys=True, ensure_ascii=True)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


PATH_AUTO = Path(__file__).with_name("consent_auto.json")


def load_auto(data=None):
    """The text of the one yes that lets the Hub share by itself (version 4, a PROPOSAL; consent.json keeps version 3 for the ten-step run)."""
    return json.loads(data if data is not None else PATH_AUTO.read_text(encoding="utf-8"))


def text_auto(doc, lang, link="ems", boiler_only=True):
    """The automatic consent text of a language: the paragraph about the recording has three forms (only the boiler's own
    messages, the whole cable, an OpenTherm boiler). `boiler_only` is the switch of owner decision 2 (material.BOILER_TELEGRAMS_ONLY)."""
    source = doc[lang if lang in LANGUAGES else "en"]
    out = {k: v for k, v in source.items() if k not in ("recording_whole", "recording_opentherm")}
    second = source.get("recording_opentherm") if link == "opentherm" else (None if boiler_only else source.get("recording_whole"))
    if second is not None:
        out["paragraphs"] = [dict(second) if p["id"] == second["id"] else p for p in out["paragraphs"]]
    return out


def text(doc, lang, link="ems"):
    """The consent text of a language for the link of the run: the paragraph about the recording has a second form for an OpenTherm boiler
    (its log holds boiler values only and has no tick of its own). Everything else is the same for both."""
    source = doc[lang if lang in LANGUAGES else "en"]
    out = {k: v for k, v in source.items() if k != "recording_opentherm"}
    second = source.get("recording_opentherm")
    if link == "opentherm" and second is not None:
        out["paragraphs"] = [dict(second) if p["id"] == second["id"] else p for p in out["paragraphs"]]
    return out
