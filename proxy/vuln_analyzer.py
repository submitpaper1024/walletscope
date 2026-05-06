"""
Per-scenario vulnerability analysis (paper Phase 3, Task B).

Each scenario produces a small structured verdict that downstream report
generation can render directly. Scenarios are dispatched by the `scenario`
field stamped on every captured record by mitm_addon.

Scenarios understood here:
  benign            -- no vulnerability check, only baseline traffic
  A1_drain          -- token draining: vulnerable iff no simulation precedes
                       the malicious submit_tx
  A2_sim_phish      -- transaction-simulation phishing: vulnerable iff the
                       wallet only simulates once (static) instead of
                       repeatedly (real-time) before submit_tx
  A3_addr_poison    -- address poisoning: classify each USDT-like transfer
                       seen in tx_history responses (legit / zero / dust /
                       fake) and report which categories were exposed
  recipient_verify  -- recipient verification: detect whether any captured
                       provider response flagged the recipient address

The detectors are intentionally heuristic: we observe the wallet through
the proxy and can therefore only see what crossed the wire. The paper
framing matches this scope.
"""

from __future__ import annotations

import json
import re
from collections import defaultdict
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

# canonical USDT contract on Ethereum mainnet
USDT_MAINNET = "0xdac17f958d2ee523a2206206994597c13d831ec7"

# 6-decimal USDT: 1.00 USDT = 1_000_000 raw units. Anything below this is
# treated as dust per common wallet UX heuristics.
DUST_USDT_RAW = 1_000_000

# ERC-20 Transfer event topic
TRANSFER_TOPIC = "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef"

WARNING_KEYWORDS = (
    "phishing",
    "scam",
    "malicious",
    "fraud",
    "blacklist",
    "block_list",
    "blocklist",
    "risk_high",
    '"risk":"high"',
    '"warning":true',
    "is_blocked",
)


# -------------------------------------------------------------- shared helpers


def _parse_time(record: Dict[str, Any]) -> Optional[datetime]:
    raw = record.get("time")
    if not isinstance(raw, str) or not raw:
        return None
    candidate = raw[:-1] + "+00:00" if raw.endswith("Z") else raw
    try:
        return datetime.fromisoformat(candidate)
    except ValueError:
        return None


def _is_simulation(record: Dict[str, Any]) -> bool:
    if record.get("tag") == "simulation":
        return True
    method = (record.get("rpc_method") or "").lower()
    return method in {"eth_call", "eth_estimategas", "eth_createaccesslist"}


def _is_submit_tx(record: Dict[str, Any]) -> bool:
    if record.get("tag") == "submit_tx":
        return True
    method = (record.get("rpc_method") or "").lower()
    return method in {"eth_sendrawtransaction", "eth_sendtransaction"}


def _load_json(text: str) -> Optional[Any]:
    if not text:
        return None
    try:
        return json.loads(text)
    except (TypeError, ValueError):
        return None


# ------------------------------------------------------------- A1 token drain


@dataclass
class DrainVerdict:
    scenario: str = "A1_drain"
    submit_tx_count: int = 0
    simulation_count: int = 0
    simulation_before_submit: int = 0
    vulnerable: bool = False
    rationale: str = ""


def analyze_drain(records: List[Dict[str, Any]]) -> DrainVerdict:
    sims = [r for r in records if _is_simulation(r)]
    submits = [r for r in records if _is_submit_tx(r)]
    verdict = DrainVerdict(
        submit_tx_count=len(submits),
        simulation_count=len(sims),
    )

    if not submits:
        verdict.rationale = "no submit_tx observed; cannot evaluate"
        return verdict

    first_submit_time = _parse_time(submits[0])
    if first_submit_time is None:
        # if timestamps are unusable, fall back to raw counts
        verdict.simulation_before_submit = len(sims)
    else:
        verdict.simulation_before_submit = sum(
            1
            for s in sims
            if (t := _parse_time(s)) is not None and t <= first_submit_time
        )

    if verdict.simulation_before_submit == 0:
        verdict.vulnerable = True
        verdict.rationale = "submit_tx issued without preceding simulation"
    else:
        verdict.rationale = (
            f"{verdict.simulation_before_submit} simulation call(s) preceded submit_tx"
        )
    return verdict


# --------------------------------------------------------- A2 sim phishing


@dataclass
class SimPhishVerdict:
    scenario: str = "A2_sim_phish"
    simulation_count: int = 0
    distinct_simulation_seconds: int = 0
    is_real_time: bool = False
    submit_tx_count: int = 0
    vulnerable: bool = False
    rationale: str = ""


def analyze_sim_phish(records: List[Dict[str, Any]]) -> SimPhishVerdict:
    sims = [r for r in records if _is_simulation(r)]
    submits = [r for r in records if _is_submit_tx(r)]
    verdict = SimPhishVerdict(
        simulation_count=len(sims),
        submit_tx_count=len(submits),
    )

    sim_seconds = set()
    for r in sims:
        t = _parse_time(r)
        if t is not None:
            sim_seconds.add(int(t.timestamp()))
    verdict.distinct_simulation_seconds = len(sim_seconds)
    verdict.is_real_time = verdict.distinct_simulation_seconds >= 2

    if verdict.simulation_count == 0:
        verdict.vulnerable = False
        verdict.rationale = (
            "no simulation observed; user is not shown misleading preview"
        )
    elif verdict.is_real_time:
        verdict.vulnerable = False
        verdict.rationale = (
            f"simulation refreshed across {verdict.distinct_simulation_seconds} time slots"
        )
    else:
        verdict.vulnerable = True
        verdict.rationale = (
            "simulation called once and not refreshed before submit_tx (static)"
        )
    return verdict


# --------------------------------------------------------- A3 addr poisoning


@dataclass
class TransferRow:
    kind: str  # legit | zero | dust | fake
    token_contract: str
    from_addr: str
    to_addr: str
    raw_value: str  # decimal string


@dataclass
class AddrPoisonVerdict:
    scenario: str = "A3_addr_poison"
    history_responses_seen: int = 0
    transfers: List[TransferRow] = field(default_factory=list)
    counts: Dict[str, int] = field(default_factory=lambda: defaultdict(int))
    vulnerable_zero: bool = False
    vulnerable_dust: bool = False
    vulnerable_fake: bool = False
    rationale: str = ""


def _hex_to_int(value: str) -> Optional[int]:
    if not isinstance(value, str):
        return None
    value = value.strip()
    if not value:
        return None
    try:
        if value.startswith(("0x", "0X")):
            return int(value, 16)
        return int(value)
    except ValueError:
        return None


def _topic_to_address(topic: str) -> Optional[str]:
    if not isinstance(topic, str) or len(topic) < 42:
        return None
    return "0x" + topic[-40:].lower()


def _classify_transfer(
    token_contract: str, value_raw: int, expected_token: str = USDT_MAINNET
) -> str:
    is_canonical = token_contract.lower() == expected_token.lower()
    if not is_canonical:
        return "fake"
    if value_raw == 0:
        return "zero"
    if value_raw < DUST_USDT_RAW:
        return "dust"
    return "legit"


def _walk_for_transfers(node: Any) -> Iterable[Dict[str, Any]]:
    """Yield dict candidates that look like ERC-20 transfer entries."""
    if isinstance(node, dict):
        keys = set(node.keys())
        # raw eth_getLogs entry
        if "topics" in keys and "data" in keys and "address" in keys:
            yield node
        # alchemy / etherscan transfer entry
        if {"contractAddress", "value", "from", "to"} <= keys:
            yield node
        if {"tokenAddress", "value", "from", "to"} <= keys:
            yield node
        for v in node.values():
            yield from _walk_for_transfers(v)
    elif isinstance(node, list):
        for item in node:
            yield from _walk_for_transfers(item)


def _extract_transfers_from_response(payload: Any) -> List[TransferRow]:
    rows: List[TransferRow] = []
    for entry in _walk_for_transfers(payload):
        # eth_getLogs shape
        topics = entry.get("topics") if isinstance(entry, dict) else None
        if isinstance(topics, list) and topics and topics[0] == TRANSFER_TOPIC:
            token = (entry.get("address") or "").lower()
            from_addr = _topic_to_address(topics[1]) if len(topics) > 1 else ""
            to_addr = _topic_to_address(topics[2]) if len(topics) > 2 else ""
            value = _hex_to_int(entry.get("data", "")) or 0
            kind = _classify_transfer(token, value)
            rows.append(
                TransferRow(
                    kind=kind,
                    token_contract=token,
                    from_addr=from_addr or "",
                    to_addr=to_addr or "",
                    raw_value=str(value),
                )
            )
            continue

        # provider-shaped transfer entry
        contract = (
            entry.get("contractAddress")
            or entry.get("tokenAddress")
            or entry.get("rawContract", {}).get("address")
            or ""
        )
        if not isinstance(contract, str):
            contract = ""
        value_field = entry.get("value")
        value = _hex_to_int(value_field) if isinstance(value_field, str) else None
        if value is None and isinstance(value_field, (int, float)):
            try:
                value = int(value_field)
            except (TypeError, ValueError):
                value = 0
        if value is None:
            continue
        rows.append(
            TransferRow(
                kind=_classify_transfer(contract.lower(), value),
                token_contract=contract.lower(),
                from_addr=str(entry.get("from", "")).lower(),
                to_addr=str(entry.get("to", "")).lower(),
                raw_value=str(value),
            )
        )
    return rows


def analyze_addr_poison(records: List[Dict[str, Any]]) -> AddrPoisonVerdict:
    verdict = AddrPoisonVerdict(counts=defaultdict(int))

    for r in records:
        if r.get("tag") != "tx_history":
            continue
        verdict.history_responses_seen += 1
        payload = _load_json(r.get("response_body", ""))
        if payload is None:
            continue
        for row in _extract_transfers_from_response(payload):
            verdict.transfers.append(row)
            verdict.counts[row.kind] += 1

    verdict.vulnerable_zero = verdict.counts.get("zero", 0) > 0
    verdict.vulnerable_dust = verdict.counts.get("dust", 0) > 0
    verdict.vulnerable_fake = verdict.counts.get("fake", 0) > 0

    flagged = [
        kind
        for kind, present in (
            ("zero", verdict.vulnerable_zero),
            ("dust", verdict.vulnerable_dust),
            ("fake", verdict.vulnerable_fake),
        )
        if present
    ]
    if flagged:
        verdict.rationale = (
            f"history responses surfaced {', '.join(flagged)} phishing transfer(s)"
        )
    elif verdict.history_responses_seen == 0:
        verdict.rationale = "no tx_history responses captured"
    else:
        verdict.rationale = "history responses contained no phishing transfers"

    return verdict


# ------------------------------------------------------- recipient verify


@dataclass
class RecipientVerdict:
    scenario: str = "recipient_verify"
    verification_endpoints: List[str] = field(default_factory=list)
    warning_observed: bool = False
    rationale: str = ""


def _looks_like_verification(record: Dict[str, Any]) -> bool:
    url = (record.get("url") or "").lower()
    body = (record.get("request_body") or "").lower()
    hints = (
        "blockaid",
        "scamsniffer",
        "harpie",
        "scanner",
        "address-check",
        "recipient",
        "phish",
        "scam",
        "blacklist",
        "blocklist",
        "risk",
    )
    return any(h in url for h in hints) or any(h in body for h in hints)


def _has_warning(text: str) -> bool:
    if not text:
        return False
    low = text.lower()
    return any(k in low for k in WARNING_KEYWORDS)


def analyze_recipient_verify(records: List[Dict[str, Any]]) -> RecipientVerdict:
    verdict = RecipientVerdict()
    seen_endpoints: List[str] = []
    for r in records:
        if not _looks_like_verification(r):
            continue
        host = r.get("host") or ""
        if host and host not in seen_endpoints:
            seen_endpoints.append(host)
        if _has_warning(r.get("response_body") or ""):
            verdict.warning_observed = True
    verdict.verification_endpoints = seen_endpoints

    if not seen_endpoints:
        verdict.rationale = "no recipient verification endpoint contacted"
    elif verdict.warning_observed:
        verdict.rationale = (
            f"warning surfaced by {', '.join(seen_endpoints)}"
        )
    else:
        verdict.rationale = (
            f"endpoint(s) {', '.join(seen_endpoints)} returned no warning keywords"
        )
    return verdict


# ----------------------------------------------------------------- dispatch


SCENARIO_ANALYZERS = {
    "A1_drain": analyze_drain,
    "A2_sim_phish": analyze_sim_phish,
    "A3_addr_poison": analyze_addr_poison,
    "recipient_verify": analyze_recipient_verify,
}


def analyze_scenario(scenario: str, records: List[Dict[str, Any]]) -> Dict[str, Any]:
    analyzer = SCENARIO_ANALYZERS.get(scenario)
    if analyzer is None:
        return {
            "scenario": scenario,
            "vulnerable": False,
            "rationale": f"no analyzer registered for scenario={scenario}",
        }
    verdict = analyzer(records)
    payload = asdict(verdict)
    # transfers are dataclasses → asdict already nested them.
    return payload


def analyze_log(path: str | Path) -> Dict[str, Any]:
    """Load a single capture file and run the matching scenario analyzer.

    The scenario is taken from the records themselves; if records carry
    multiple scenarios (e.g. capture-wide log) every scenario is analyzed.
    """
    records: List[Dict[str, Any]] = []
    with Path(path).open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError:
                continue

    by_scenario: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for r in records:
        by_scenario[r.get("scenario", "benign")].append(r)

    return {
        "log_path": str(path),
        "total_records": len(records),
        "verdicts": {
            scenario: analyze_scenario(scenario, items)
            for scenario, items in by_scenario.items()
        },
    }


def main(argv: List[str]) -> int:
    if len(argv) < 2:
        print("usage: vuln_analyzer.py <log.jsonl> [<log.jsonl> ...]")
        return 1
    for path in argv[1:]:
        result = analyze_log(path)
        print(json.dumps(result, indent=2, ensure_ascii=False, default=str))
    return 0


if __name__ == "__main__":
    import sys
    raise SystemExit(main(sys.argv))
