"""The one log line behind a plain sentence: what a person reads has no code, the log keeps it.

A sentence of the panel, the cards, the options flows or a Home Assistant exception says what happened in words. The
raw code that came with the failure (a name of the Hub or of the link such as ``controller_unreachable``) goes to
Home Assistant's log in ONE line, so that a tester can send it:

    Emthera: shown "e32_unreachable"; code: controller_unreachable

Only a code that looks like a name (lower case letters, digits, underscores) is written. Anything else (a text of a
network library may hold an address) is written as its kind only; a password or a token is never part of a code.
"""
from __future__ import annotations

import logging
import re
import time

_LOGGER = logging.getLogger("custom_components.emthera.failure")
_NAME = re.compile(r"[a-z][a-z0-9_]{0,63}")


def code_name(code):
    """The code as a name for the log: the name itself, or the kind of the thing that is not a name."""
    if isinstance(code, BaseException):
        return str(code) if _NAME.fullmatch(str(code)) else f"other:{type(code).__name__}"
    if type(code) is not str:
        return "none" if code is None else f"other:{type(code).__name__}"
    return code if _NAME.fullmatch(code) else "other"


# A failure passes through several layers (the link, the flow or the panel); the layer that finds the code writes the
# line and the next one, finding the same code within a second, does not write it again.
_LAST = [None, 0.0]
SAME_FAILURE_S = 1.0


def log_failure(key, code):
    """Writes the one line (level warning) for the sentence ``key`` that was shown, with the raw ``code``."""
    name, now = code_name(code), time.monotonic()
    if _LAST[0] == name and now - _LAST[1] < SAME_FAILURE_S:
        return
    _LAST[0], _LAST[1] = name, now
    _LOGGER.warning('Emthera: shown "%s"; code: %s', key, name)


_SEEN = set()


def log_failure_once(key, code):
    """Like ``log_failure``, but one line per (sentence, code) for a state that is read again and again."""
    name = (key, code_name(code))
    if name not in _SEEN:
        if len(_SEEN) > 200:
            _SEEN.clear()
        _SEEN.add(name)
        log_failure(key, code)


def coded_error(error_class, key, code, **extra):
    """A Home Assistant exception with the sentence ``key``; the raw ``code`` is logged and rides along as the
    ``error`` placeholder (its sentence does not print it), so that a screen can still tell a refusal apart."""
    from .const import DOMAIN
    log_failure(key, code)
    return error_class(translation_domain=DOMAIN, translation_key=key,
                       translation_placeholders={"error": code, **extra})
