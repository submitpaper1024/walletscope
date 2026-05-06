"""
Extract third-party API keys leaked in captured wallet traffic, and
optionally re-issue requests with the leaked credentials to confirm they
are usable by an unrelated client (free-rider test from result1.tex §B).

Each detector is a (provider, host_substring, regex) triple. A regex match
on the URL is treated as a leaked key. The same key seen on different
endpoints is collapsed to one record.
"""

from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Iterable, List, Optional
from urllib.parse import urlparse


@dataclass(frozen=True)
class KeyPattern:
    provider: str
    host_substr: str
    regex: re.Pattern


# Patterns derived from public docs of each provider's URL scheme.
# We deliberately match URL path/query positions rather than the bare key
# so a random 32-hex string elsewhere does not produce a false positive.
PATTERNS: List[KeyPattern] = [
    KeyPattern(
        provider="infura",
        host_substr="infura.io",
        regex=re.compile(r"/v3/(?P<key>[A-Za-z0-9]{20,})"),
    ),
    KeyPattern(
        provider="alchemy",
        host_substr="alchemy.com",
        regex=re.compile(r"/v2/(?P<key>[A-Za-z0-9_-]{20,})"),
    ),
    KeyPattern(
        provider="quicknode",
        host_substr="quiknode.pro",
        regex=re.compile(r"://[^/]*\.quiknode\.pro/(?P<key>[A-Za-z0-9]{20,})"),
    ),
    KeyPattern(
        provider="chainstack",
        host_substr="chainstack.com",
        regex=re.compile(r"/(?P<key>[a-f0-9]{32,})"),
    ),
    KeyPattern(
        provider="etherscan",
        host_substr="etherscan.io",
        regex=re.compile(r"[?&]apikey=(?P<key>[A-Za-z0-9]{20,})"),
    ),
    KeyPattern(
        provider="twonodes",
        host_substr="twonodes.com",
        regex=re.compile(r"/(?P<key>[A-Za-z0-9_-]{16,})"),
    ),
    KeyPattern(
        provider="tenderly",
        host_substr="tenderly.co",
        regex=re.compile(r"/(?P<key>[A-Za-z0-9_-]{16,})"),
    ),
    KeyPattern(
        provider="ankr",
        host_substr="rpc.ankr.com",
        regex=re.compile(r"/eth/(?P<key>[A-Za-z0-9]{20,})"),
    ),
    KeyPattern(
        provider="moralis",
        host_substr="moralis.io",
        regex=re.compile(r"[?&]apikey=(?P<key>[A-Za-z0-9]{20,})"),
    ),
]


@dataclass
class LeakedKey:
    provider: str
    key: str
    sample_url: str
    sample_host: str
    occurrences: int = 0
    free_rider_status: Optional[int] = None
    free_rider_note: str = ""


def _scan_url(url: str, host: str) -> Optional[LeakedKey]:
    for pat in PATTERNS:
        if pat.host_substr not in host:
            continue
        match = pat.regex.search(url)
        if not match:
            continue
        key = match.group("key")
        # Filter obviously non-secret tokens.
        if key.lower() in {"v1", "v2", "v3", "api", "eth", "mainnet"}:
            continue
        return LeakedKey(
            provider=pat.provider,
            key=key,
            sample_url=url,
            sample_host=host,
        )
    return None


def extract_from_records(records: Iterable[Dict]) -> List[LeakedKey]:
    """Return one LeakedKey entry per (provider, key) seen in records."""
    seen: Dict[tuple, LeakedKey] = {}
    for r in records:
        url = r.get("url", "") or ""
        host = r.get("host", "") or ""
        if not url:
            continue
        leak = _scan_url(url, host)
        if leak is None:
            continue
        bucket = seen.get((leak.provider, leak.key))
        if bucket is None:
            seen[(leak.provider, leak.key)] = leak
            leak.occurrences = 1
        else:
            bucket.occurrences += 1
    return list(seen.values())


def extract_from_log(path: str | Path) -> List[LeakedKey]:
    records = []
    with Path(path).open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return extract_from_records(records)


# ---------------------------------------------------------------- free-rider

# Minimal probe payloads chosen so a single GET/POST is sufficient to
# confirm the key is honored without consuming meaningful quota.
_FREE_RIDER_PROBES = {
    "infura": ("POST", '{"jsonrpc":"2.0","method":"eth_blockNumber","params":[],"id":1}'),
    "alchemy": ("POST", '{"jsonrpc":"2.0","method":"eth_blockNumber","params":[],"id":1}'),
    "quicknode": ("POST", '{"jsonrpc":"2.0","method":"eth_blockNumber","params":[],"id":1}'),
    "ankr": ("POST", '{"jsonrpc":"2.0","method":"eth_blockNumber","params":[],"id":1}'),
    "twonodes": ("POST", '{"jsonrpc":"2.0","method":"eth_blockNumber","params":[],"id":1}'),
    "etherscan": ("GET", None),
    "moralis": ("GET", None),
    "chainstack": ("POST", '{"jsonrpc":"2.0","method":"eth_blockNumber","params":[],"id":1}'),
    "tenderly": ("GET", None),
}


def free_rider_probe(leak: LeakedKey, timeout: float = 5.0) -> LeakedKey:
    """Re-issue a single request using the leaked key. Updates leak in place."""
    try:
        import urllib.request
    except Exception as exc:  # pragma: no cover
        leak.free_rider_status = None
        leak.free_rider_note = f"urllib unavailable: {exc}"
        return leak

    method, body = _FREE_RIDER_PROBES.get(leak.provider, ("GET", None))
    parsed = urlparse(leak.sample_url)
    target = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
    if parsed.query:
        target += f"?{parsed.query}"

    req = urllib.request.Request(
        target,
        method=method,
        data=body.encode("utf-8") if body else None,
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "walletscope-freerider/1.0",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            leak.free_rider_status = resp.status
            leak.free_rider_note = resp.reason or ""
    except Exception as exc:  # network / 4xx / 5xx
        leak.free_rider_status = getattr(exc, "code", None)
        leak.free_rider_note = str(exc)
    return leak


def free_rider_check(leaks: List[LeakedKey], pause: float = 0.0) -> List[LeakedKey]:
    """Probe each leaked key once. Pause between requests to be polite."""
    for leak in leaks:
        free_rider_probe(leak)
        if pause > 0:
            time.sleep(pause)
    return leaks


# ------------------------------------------------------------------- entrypoint

def main(argv: List[str]) -> int:
    if len(argv) < 2:
        print("usage: api_keys.py <log.jsonl> [--probe]")
        return 1
    log_path = Path(argv[1])
    probe = "--probe" in argv[2:]

    leaks = extract_from_log(log_path)
    if not leaks:
        print("no leaked keys found")
        return 0

    if probe:
        free_rider_check(leaks, pause=0.2)

    for leak in leaks:
        line = f"{leak.provider:10s} {leak.key}  ({leak.occurrences} hits)"
        if probe:
            line += f"  free-rider={leak.free_rider_status} {leak.free_rider_note}"
        print(line)
    return 0


if __name__ == "__main__":
    import sys
    raise SystemExit(main(sys.argv))
