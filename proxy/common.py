import json
import re
from typing import Any, Tuple

ADDR_RE = re.compile(r"^0x[0-9a-fA-F]{40}$")
HEX_RE = re.compile(r"^0x[0-9a-fA-F]+$")

PRICE_HINTS = [
    "price",
    "prices",
    "quote",
    "quotes",
    "ticker",
    "tickers",
    "marketdata",
    "markets",
    "coingecko",
    "defillama",
    "1inch",
    "paraswap",
    "zerox",
    "0x.org",
]


# ========== Basic helpers ==========

def looks_like_address(v: Any) -> bool:
    """Heuristic: does v look like an Ethereum address?"""
    return isinstance(v, str) and bool(ADDR_RE.match(v))


def looks_like_hex(v: Any) -> bool:
    """Heuristic: does v look like a 0x-prefixed hex string?"""
    return isinstance(v, str) and bool(HEX_RE.match(v))


def contains_eth_address(s: str) -> bool:
    """Does this string contain an Ethereum address substring?"""
    if not isinstance(s, str):
        return False
    return bool(ADDR_RE.search(s))


# ========== JSON-RPC parsing ==========

def parse_jsonrpc(body: str) -> Tuple[bool, str | None, Any]:
    """
    Try to parse request body as JSON-RPC.
    Return (is_jsonrpc: bool, method: str|None, params: Any|None).
    """
    if not body:
        return False, None, None
    try:
        data = json.loads(body)
    except Exception:
        return False, None, None

    # Single request
    if isinstance(data, dict) and data.get("jsonrpc") == "2.0":
        return True, data.get("method"), data.get("params")

    # Batch request
    if (
        isinstance(data, list)
        and data
        and isinstance(data[0], dict)
        and data[0].get("jsonrpc") == "2.0"
    ):
        return True, data[0].get("method"), data[0].get("params")

    return False, None, None


# ========== Semantic detectors: submit_tx / simulation / history / address / price ==========

def _is_tx_object(p: Any) -> bool:
    """Heuristic: tx-like dict (from/to/data/gas/...)"""
    if not isinstance(p, dict):
        return False
    keys = set(p.keys())
    tx_like_keys = {"from", "to", "data", "gas", "gasPrice", "value", "maxFeePerGas"}
    return bool(keys & tx_like_keys)


def _is_raw_tx(p: Any) -> bool:
    """Heuristic: raw tx hex string."""
    if not looks_like_hex(p):
        return False
    # require some minimum length so we don't misclassify small hex values
    return len(p) > 66


def is_submit_tx_call(method: str | None, params: Any) -> bool:
    """
    Detect submit transaction calls, across different providers.

    Typical:
    - eth_sendRawTransaction
    - eth_sendTransaction
    - custom sendXxxTransaction methods with tx-like params
    """
    m = (method or "").lower()
    if not isinstance(params, list) or not params:
        return False
    p0 = params[0]

    # Standard JSON-RPC
    if m in ("eth_sendrawtransaction", "eth_sendtransaction"):
        return True

    # Custom sendXxxTransaction
    if "send" in m and "transaction" in m and (_is_raw_tx(p0) or _is_tx_object(p0)):
        return True

    return False


def is_simulation_call(method: str | None, params: Any) -> bool:
    """
    Detect tx simulation / pre-exec / gas estimation calls.

    Typical:
    - eth_call(tx)
    - eth_estimateGas(tx)
    - eth_createAccessList(tx)
    - simulateXxx(tx)
    - estimateXxxGas(tx)
    """
    m = (method or "").lower()
    if not isinstance(params, list) or not params:
        return False
    p0 = params[0]

    jsonrpc_sim_methods = {
        "eth_call",
        "eth_estimategas",
        "eth_createaccesslist",
    }

    if m in jsonrpc_sim_methods and _is_tx_object(p0):
        return True

    if "simulate" in m and _is_tx_object(p0):
        return True

    if "estimate" in m and "gas" in m and _is_tx_object(p0):
        return True

    return False


def is_address_check_call(method: str | None, params: Any) -> bool:
    """
    Detect address-related checks, e.g.:

    - eth_getBalance(address, ...)
    - eth_getCode(address, ...)
    - eth_getTransactionCount(address, ...)
    - methods with param dict containing address/from/to/owner
    """
    m = (method or "").lower()
    if not isinstance(params, list) or not params:
        return False

    addr_methods = {
        "eth_getbalance",
        "eth_getcode",
        "eth_gettransactioncount",
        "eth_getstorageat",
    }

    if m in addr_methods and looks_like_address(params[0]):
        return True

    p0 = params[0]
    if isinstance(p0, dict):
        if any(
            looks_like_address(p0.get(k)) for k in ("address", "from", "to", "owner")
        ):
            return True

    return False


def is_tx_history_call(method: str | None, params: Any) -> bool:
    """
    Detect calls for tx history / logs.

    Typical:
    - eth_getLogs({ address, fromBlock/toBlock/... })
    - getAssetTransfers / ...history... / ...logs...
    """
    m = (method or "").lower()
    if not isinstance(params, list) or not params:
        return False

    if m == "eth_getlogs" and isinstance(params[0], dict):
        f = params[0]
        if looks_like_address(f.get("address")) and (
            f.get("fromBlock") or f.get("toBlock") or f.get("blockHash")
        ):
            return True

    if any(x in m for x in ["assettransfers", "getassettransfers", "history", "logs"]):
        return True

    return False


def looks_like_price_api(url_low: str, body_low: str) -> bool:
    """
    Detect token price API by URL/body keywords.

    We don't rely on specific provider names, but hint tokens:
    - price / prices / quote / quotes / ticker / tickers / markets ...
    - body contains vs_currency / fiat / symbol / symbols
    """
    if any(x in url_low for x in PRICE_HINTS):
        return True

    if any(x in body_low for x in ["vs_currency", "fiat", "symbol", "symbols"]):
        return True

    return False
