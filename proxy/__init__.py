"""
Phase 3 — traffic capture, classification, and reporting.

The proxy modules also need to work when mitmdump loads addon.py via
``-s walletscope/proxy/addon.py``. To keep the same files usable in both
contexts, we add this directory to sys.path so bare sibling imports
(``import rule_engine`` etc.) resolve uniformly.
"""

import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)
