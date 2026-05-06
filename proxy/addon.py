"""
mitmproxy addon: capture wallet traffic with scenario tagging.

Each captured request-response pair is stamped with the current wallet name
and scenario (e.g. benign, A1_drain, A2_sim_phish, A3_addr_poison,
recipient_verify) so downstream analysis can correlate traffic to the
attack phase that produced it.

Configuration is read from environment variables at startup:

  WALLETSCOPE_WALLET     wallet under test, e.g. "metamask"  (default: "unknown")
  WALLETSCOPE_SCENARIO   initial scenario tag                (default: "benign")
  WALLETSCOPE_LOG_DIR    directory to write capture files    (default: "captures")

The scenario can also be switched at runtime by issuing a request to a
sentinel URL through the proxy. The request is consumed by the addon and
never forwarded:

  GET http://walletscope.local/scenario/<name>

Example: open http://walletscope.local/scenario/A1_drain in a tab whose
proxy points at this mitmproxy instance, and subsequent traffic will be
tagged with scenario=A1_drain.

Each scenario writes to its own JSONL file at
<WALLETSCOPE_LOG_DIR>/<wallet>__<scenario>.jsonl
"""

from __future__ import annotations

import json
import os
import sys
import threading
from datetime import datetime
from pathlib import Path
from typing import Any, Dict

# mitmdump loads this file via -s <path>, so the package isn't on sys.path.
# Adding the addon's directory lets sibling imports (rule_engine etc.) resolve.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from mitmproxy import http

import rule_engine

SENTINEL_HOST = "walletscope.local"
SCENARIO_PREFIX = "/scenario/"
RESPONSE_BODY_LIMIT = 50_000


class WalletInspectorAddon:
    """Capture HTTP request/response pairs from a wallet under test."""

    def __init__(self) -> None:
        self.wallet = os.environ.get("WALLETSCOPE_WALLET", "unknown").strip() or "unknown"
        self.scenario = os.environ.get("WALLETSCOPE_SCENARIO", "benign").strip() or "benign"
        log_dir = os.environ.get("WALLETSCOPE_LOG_DIR", "captures").strip() or "captures"
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)

        self._lock = threading.Lock()
        self._pending: Dict[int, Dict[str, Any]] = {}

    # ------------------------------------------------------------------ helpers

    def _log_path(self, scenario: str | None = None) -> Path:
        scenario = scenario or self.scenario
        safe_wallet = self.wallet.replace("/", "_")
        safe_scenario = scenario.replace("/", "_")
        return self.log_dir / f"{safe_wallet}__{safe_scenario}.jsonl"

    def _write(self, record: Dict[str, Any]) -> None:
        path = self._log_path(record.get("scenario"))
        with self._lock, path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")

    def _handle_sentinel(self, flow: http.HTTPFlow) -> bool:
        """Intercept walletscope.local control requests; return True if consumed."""
        if flow.request.host != SENTINEL_HOST:
            return False

        path = flow.request.path or "/"
        if path.startswith(SCENARIO_PREFIX):
            new_scenario = path[len(SCENARIO_PREFIX):].split("?", 1)[0].strip("/")
            if new_scenario:
                self.scenario = new_scenario
                body = f"scenario set to {new_scenario}\n"
                status = 200
            else:
                body = "missing scenario name\n"
                status = 400
        elif path.rstrip("/") == "":
            body = (
                f"walletscope active\nwallet={self.wallet}\nscenario={self.scenario}\n"
            )
            status = 200
        else:
            body = "unknown walletscope endpoint\n"
            status = 404

        flow.response = http.Response.make(
            status,
            body.encode("utf-8"),
            {"Content-Type": "text/plain; charset=utf-8"},
        )
        return True

    # ------------------------------------------------------------------ hooks

    def request(self, flow: http.HTTPFlow) -> None:
        if self._handle_sentinel(flow):
            return

        url = flow.request.pretty_url
        host = flow.request.host
        path = flow.request.path
        body = flow.request.get_text() or ""

        tag, is_jsonrpc, rpc_method, rpc_params = rule_engine.classify_request(
            url=url, host=host, path=path, body=body
        )

        self._pending[id(flow)] = {
            "time": datetime.utcnow().isoformat(),
            "wallet": self.wallet,
            "scenario": self.scenario,
            "method": flow.request.method,
            "url": url,
            "host": host,
            "path": path,
            "tag": tag,
            "is_jsonrpc": is_jsonrpc,
            "rpc_method": rpc_method,
            "rpc_params": rpc_params,
            "request_body": body,
        }

    def response(self, flow: http.HTTPFlow) -> None:
        if flow.request.host == SENTINEL_HOST:
            return

        record = self._pending.pop(id(flow), None)
        if record is None:
            record = {
                "time": datetime.utcnow().isoformat(),
                "wallet": self.wallet,
                "scenario": self.scenario,
                "method": flow.request.method,
                "url": flow.request.pretty_url,
                "host": flow.request.host,
                "path": flow.request.path,
                "tag": "other",
                "is_jsonrpc": False,
                "rpc_method": None,
                "rpc_params": None,
                "request_body": "",
            }

        record["response_status"] = flow.response.status_code
        record["response_headers"] = dict(flow.response.headers)

        try:
            body_text = flow.response.get_text() or ""
        except Exception:
            body_text = ""

        truncated = len(body_text) > RESPONSE_BODY_LIMIT
        record["response_body"] = body_text[:RESPONSE_BODY_LIMIT]
        record["response_truncated"] = truncated

        self._write(record)


addons = [WalletInspectorAddon()]
