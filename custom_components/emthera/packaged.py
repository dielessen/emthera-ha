"""Files that ship with the integration and never change while Home Assistant runs, read ONCE.

Home Assistant imports the package's ``__init__`` in its import executor, never in the event loop, and the package's
``__init__`` imports this module at its top. So the reads below run there, before any set-up, config flow, options
flow, diagnostics download or repair step can need them, and everything afterwards is served from memory. Nothing
else may read these files in a coroutine or a callback; a module imported lazily (inside a function) must not read a
file in its body (tests_native/test_no_blocking_file_reads.py scans for it and walks the integration with Home
Assistant's own blocking-call detection switched on).
"""
import json
from pathlib import Path

HERE = Path(__file__).parent
MANIFEST = json.loads((HERE / "manifest.json").read_text(encoding="utf-8"))
# The text of the tester programme's consent (share_format/consent.json). This module carries the file's text and nothing
# else: what the text means is share_format/consent.py's business, and tools/emsplus/test_ot_run_report.py names this file
# among the few that may name that folder. A missing or unreadable file must never stop the integration (the rooms come
# first): with None the tester programme reads the file itself (consent.load) and the fault shows there, where it belongs.
try:
    CONSENT_TEXT = (HERE / "share_format" / "consent.json").read_text(encoding="utf-8")
except (OSError, ValueError):
    CONSENT_TEXT = None
