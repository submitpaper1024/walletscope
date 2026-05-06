"""
End-to-end pipeline glue. One call drives:

  Phase 1  serve the scenario's DApp on the static server
  Phase 3  notify the running mitmproxy addon to tag traffic with this scenario
  Phase 2  run the per-wallet driver flow

The proxy must already be running (start it with `python -m walletscope addon`
in another shell). The driver flow itself still requires a human-friendly
Chrome profile that has the wallet extension installed and unlocked once.
"""

from __future__ import annotations

import time

from . import scenarios
from .driver import chrome, flows


def run(wallet: str, scenario: str, *, skip_serve: bool = False, skip_notify: bool = False):
    print(f"=== walletscope: wallet={wallet} scenario={scenario} ===")

    if not skip_serve:
        chrome.serve_scenario(scenario)
        time.sleep(1)
    else:
        print("(skip-serve) DApp server not started by orchestrator")

    if not skip_notify:
        body = scenarios.notify_proxy(scenario)
        if body is not None:
            print(f"proxy ack: {body.strip()}")
    else:
        print("(skip-notify) proxy scenario not switched")

    flows.run_flow(wallet)
    print("=== flow complete ===")
