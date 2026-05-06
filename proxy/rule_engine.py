import os
import re
from typing import Any, Dict, List, Optional

import yaml  # via pyyaml in requirements.txt

from common import (
    parse_jsonrpc,
    looks_like_price_api,
    contains_eth_address,
    is_submit_tx_call,
    is_simulation_call,
    is_tx_history_call,
    is_address_check_call,
)

RULES_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "rules.yaml")


# ========== Rule loading ==========

def load_rules(path: str = RULES_FILE) -> List[Dict[str, Any]]:
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
    except FileNotFoundError:
        return []
    rules = data.get("rules", [])
    # ensure list[dict]
    return [r for r in rules if isinstance(r, dict)]


RULES: List[Dict[str, Any]] = load_rules()


# ========== Matching helpers ==========

def _match_str_in_list(target: str, lst: List[str]) -> bool:
    target = target.lower()
    return any(target == x.lower() for x in lst)


def _match_contains_any(target: str, lst: List[str]) -> bool:
    t = target.lower()
    return any(s.lower() in t for s in lst)


def _semantic_match(kind: str, ctx: Dict[str, Any]) -> bool:
    """
    Dispatch into one of the built-in semantic detectors:
    - submit_tx
    - simulation
    - tx_history
    - address_check
    - token_price
    - chain_state (simple form)
    """
    kind = kind.lower()
    method = ctx["method"]
    params = ctx["params"]

    if kind == "submit_tx":
        return is_submit_tx_call(method, params)

    if kind == "simulation":
        return is_simulation_call(method, params)

    if kind == "tx_history":
        return is_tx_history_call(method, params)

    if kind == "address_check":
        return is_address_check_call(method, params)

    if kind == "token_price":
        return looks_like_price_api(ctx["url_low"], ctx["body_low"])

    if kind == "chain_state":
        m = (method or "").lower()
        return m in [
            "eth_getbalance",
            "eth_getcode",
            "eth_blocknumber",
            "eth_getblockbyhash",
            "eth_getblockbynumber",
            "eth_chainid",
            "net_version",
        ]

    return False


def match_rule(ctx: Dict[str, Any], when: Dict[str, Any]) -> bool:
    """
    Check whether ctx satisfies a rule's `when` block (AND across fields).
    Supported fields (usable in rules.yaml):
      - is_jsonrpc: bool
      - method_in: [str]
      - method_regex: str
      - url_contains_any: [str]
      - host_contains_any: [str]
      - host_equals_any: [str]
      - path_contains_any: [str]
      - body_contains_any: [str]
      - semantic: str (submit_tx / simulation / tx_history / address_check / token_price / chain_state)
      - params_0_is_address: bool
      - params_0_is_tx: bool
      - contains_address_in_url: bool
      - contains_address_anywhere: bool
    """
    # 1. is_jsonrpc
    if "is_jsonrpc" in when:
        if bool(when["is_jsonrpc"]) != bool(ctx["is_jsonrpc"]):
            return False

    # 2. semantic
    if "semantic" in when:
        if not _semantic_match(str(when["semantic"]), ctx):
            return False

    method = ctx["method"] or ""
    method_low = method.lower()

    # 3. method_in
    if "method_in" in when:
        if not _match_str_in_list(method, list(when["method_in"])):
            return False

    # 4. method_regex
    if "method_regex" in when and when["method_regex"]:
        pattern = str(when["method_regex"])
        if not re.search(pattern, method, flags=re.IGNORECASE):
            return False

    # 5. url_contains_any
    if "url_contains_any" in when:
        if not _match_contains_any(ctx["url"], list(when["url_contains_any"])):
            return False

    # 6. host_contains_any
    if "host_contains_any" in when:
        if not _match_contains_any(ctx["host"], list(when["host_contains_any"])):
            return False

    # 7. host_equals_any
    if "host_equals_any" in when:
        if not _match_str_in_list(ctx["host"], list(when["host_equals_any"])):
            return False

    # 8. path_contains_any
    if "path_contains_any" in when:
        if not _match_contains_any(ctx["path"], list(when["path_contains_any"])):
            return False

    # 9. body_contains_any
    if "body_contains_any" in when:
        if not _match_contains_any(ctx["body"], list(when["body_contains_any"])):
            return False

    # 10. params_0_is_address
    if "params_0_is_address" in when:
        expected = bool(when["params_0_is_address"])
        params = ctx["params"]
        is_addr = False
        if isinstance(params, list) and params:
            from common import looks_like_address  # lazy import to avoid cycle
            is_addr = looks_like_address(params[0])
        if is_addr != expected:
            return False

    # 11. params_0_is_tx
    if "params_0_is_tx" in when:
        expected = bool(when["params_0_is_tx"])
        params = ctx["params"]
        is_tx = False
        if isinstance(params, list) and params:
            from common import _is_tx_object  # type: ignore
            is_tx = _is_tx_object(params[0])
        if is_tx != expected:
            return False

    # 12. contains_address_in_url
    if "contains_address_in_url" in when:
        expected = bool(when["contains_address_in_url"])
        has_addr = contains_eth_address(ctx["url"])
        if has_addr != expected:
            return False

    # 13. contains_address_anywhere
    if "contains_address_anywhere" in when:
        expected = bool(when["contains_address_anywhere"])
        has_addr = contains_eth_address(ctx["url"]) or contains_eth_address(ctx["body"])
        if has_addr != expected:
            return False

    return True


def apply_rules(ctx: Dict[str, Any], rules: List[Dict[str, Any]]) -> Optional[str]:
    """
    Walk rules in order, return the tag of the first match.
    """
    for rule in rules:
        when = rule.get("when", {})
        tag = rule.get("tag")
        if not tag or not isinstance(when, dict):
            continue
        if match_rule(ctx, when):
            return str(tag)
    return None


# ========== Fallback classifier (when no rule in rules.yaml matched) ==========

def classify_fallback(ctx: Dict[str, Any]) -> str:
    """
    No rule matched — fall back to built-in heuristics.
    """
    is_jsonrpc = ctx["is_jsonrpc"]
    method = ctx["method"]
    params = ctx["params"]
    url_low = ctx["url_low"]
    body_low = ctx["body_low"]

    if is_jsonrpc:
        if is_submit_tx_call(method, params):
            return "submit_tx"

        if is_simulation_call(method, params):
            return "simulation"

        if is_tx_history_call(method, params):
            return "tx_history"

        if is_address_check_call(method, params):
            return "address_check"

        m = (method or "").lower()
        if m in [
            "eth_getbalance",
            "eth_getcode",
            "eth_blocknumber",
            "eth_getblockbyhash",
            "eth_getblockbynumber",
            "eth_chainid",
            "net_version",
        ]:
            return "chain_state"

        return f"jsonrpc_{m or 'unknown'}"

    # Non-JSON-RPC: REST / other HTTP APIs
    if looks_like_price_api(url_low, body_low):
        return "token_price"

    if contains_eth_address(ctx["url"]) and any(
        x in url_low for x in ["balance", "account", "profile", "address"]
    ):
        return "address_check"

    if contains_eth_address(ctx["url"]) and any(
        x in url_low for x in ["tx", "transactions", "history", "transfers", "logs"]
    ):
        return "tx_history"

    return "other"


# ========== Public entry point used by mitm_addon ==========

def classify_request(
    url: str,
    host: str,
    path: str,
    body: str | None,
) -> tuple[str, bool, str | None, Any]:
    """
    Called by mitm_addon:
      input  : URL/host/path/body
      returns: (tag, is_jsonrpc, rpc_method, rpc_params)
    """
    body_text = body or ""
    is_jsonrpc, rpc_method, rpc_params = parse_jsonrpc(body_text)

    ctx: Dict[str, Any] = {
        "url": url,
        "url_low": url.lower(),
        "host": host,
        "path": path,
        "body": body_text,
        "body_low": body_text.lower(),
        "is_jsonrpc": is_jsonrpc,
        "method": rpc_method or "",
        "params": rpc_params or [],
    }

    # Try the rule engine first
    tag = apply_rules(ctx, RULES)

    # Fall back to heuristics if nothing matched
    if tag is None:
        tag = classify_fallback(ctx)

    return tag, is_jsonrpc, rpc_method, rpc_params
