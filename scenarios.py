"""
Scenario glue between Phase 1 (DApp), Phase 2 (driver) and Phase 3 (proxy).

A "scenario" identifies one experiment cell in the paper's matrix:

    benign            — baseline traffic capture
    A1_drain          — token-draining DApp           (TODO: needs new DApp)
    A2_sim_phish      — simulation phishing           (uses sim_phish_block / sim_phish_addr)
    A3_addr_poison    — address poisoning             (TODO: needs new DApp)
    recipient_verify  — recipient verification        (TODO: needs target address harness)

The mapping below tells the driver which DApp directory to serve, and the
proxy add-on which scenario tag to attach to captured records.
"""

from __future__ import annotations

import json
import urllib.request
from typing import Optional

from . import config

SCENARIO_TO_DAPP = {
    "benign": "benign",
    "A2_sim_phish_block": "sim_phish_block",
    "A2_sim_phish_addr": "sim_phish_addr",
    # "A1_drain": ...,
    # "A3_addr_poison": ...,
    # "recipient_verify": ...,
}


def dapp_dir(scenario: str):
    """Return the walletscope/dapps/<...> directory for a given scenario."""
    name = SCENARIO_TO_DAPP.get(scenario)
    if name is None:
        raise KeyError(
            f"unknown scenario {scenario!r}; known: {sorted(SCENARIO_TO_DAPP)}"
        )
    return config.DAPPS_DIR / name


def notify_proxy(scenario: str, timeout: float = 2.0) -> Optional[str]:
    """
    Tell the running mitmproxy addon to switch its scenario tag, by issuing
    a request to the sentinel host through the proxy. Returns the response
    body, or None if the proxy isn't running / not reachable.

    Requires mitmdump to be running on MITMPROXY_PORT with proxy/addon.py.
    """
    target = f"http://walletscope.local/scenario/{scenario}"
    proxy_url = f"http://127.0.0.1:{config.MITMPROXY_PORT}"
    handler = urllib.request.ProxyHandler({"http": proxy_url, "https": proxy_url})
    opener = urllib.request.build_opener(handler)
    try:
        with opener.open(target, timeout=timeout) as resp:
            return resp.read().decode("utf-8", errors="replace")
    except Exception as exc:
        print(f"notify_proxy({scenario}): proxy unreachable ({exc}) — skipped")
        return None


def known_scenarios():
    return list(SCENARIO_TO_DAPP)


def scenario_summary() -> str:
    lines = []
    for s, d in SCENARIO_TO_DAPP.items():
        path = config.DAPPS_DIR / d
        ok = "✓" if path.exists() else "✗"
        lines.append(f"  {ok} {s:24s} → walletscope/dapps/{d}")
    return "\n".join(lines)
