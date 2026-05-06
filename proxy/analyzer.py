"""
WalletScope analyzer: turn capture files into a single HTML report
covering Output A (provider dependency + leaked API keys) and Output B
(per-scenario vulnerability verdicts).

Usage
-----

  python analyzer.py captures/metamask__benign.jsonl \
                     captures/metamask__A1_drain.jsonl \
                     captures/metamask__A2_sim_phish.jsonl \
                     --wallet metamask --out reports/metamask.html

  # or, pass a directory and let the analyzer pick up everything
  python analyzer.py captures/ --wallet metamask --out reports/metamask.html

  # disable the Claude classifier (skips Output A's AI section)
  python analyzer.py captures/ --wallet metamask --no-claude

If --wallet is omitted, the wallet name is inferred from the first record
in each capture file.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from dataclasses import asdict
from html import escape
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

import api_keys
import vuln_analyzer

try:
    from classifier import TrafficClassifier  # optional
except Exception:  # pragma: no cover - optional dependency
    TrafficClassifier = None  # type: ignore


# ----------------------------------------------------------------- loading


def _iter_log_paths(targets: Iterable[str]) -> List[Path]:
    paths: List[Path] = []
    for t in targets:
        p = Path(t)
        if p.is_dir():
            paths.extend(sorted(p.glob("*.jsonl")))
        elif p.exists():
            paths.append(p)
    return paths


def load_records(path: Path) -> List[Dict[str, Any]]:
    records: List[Dict[str, Any]] = []
    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return records


# ---------------------------------------------------------------- providers


FEATURE_DISPLAY = {
    "token_price": "Token price",
    "tx_history": "Transaction history",
    "recipient_verification": "Recipient verification",
    "rpc_relay": "RPC relay",
    "simulation": "Transaction simulation",
}

FEATURE_TAGS = {
    "submit_tx": "rpc_relay",
    "simulation": "simulation",
    "tx_history": "tx_history",
    "token_price": "token_price",
    "address_check": "recipient_verification",
}


def aggregate_providers(records: List[Dict[str, Any]]) -> Dict[str, List[str]]:
    """Best-effort provider attribution from rule-engine tags."""
    by_feature: Dict[str, set] = defaultdict(set)
    for r in records:
        feature = FEATURE_TAGS.get(r.get("tag"))
        host = r.get("host")
        if feature and host:
            by_feature[feature].add(host)
    return {k: sorted(v) for k, v in by_feature.items()}


def merge_provider_maps(*maps: Dict[str, List[str]]) -> Dict[str, List[str]]:
    merged: Dict[str, set] = defaultdict(set)
    for m in maps:
        for k, vs in m.items():
            merged[k].update(vs)
    return {k: sorted(v) for k, v in merged.items()}


# --------------------------------------------------------------- HTML render


CSS = """
body { font-family: -apple-system, system-ui, "Segoe UI", sans-serif;
       max-width: 1100px; margin: 24px auto; padding: 0 20px; color: #222; }
h1 { border-bottom: 2px solid #333; padding-bottom: 6px; }
h2 { margin-top: 32px; color: #1a4f8b; }
h3 { color: #444; }
table { border-collapse: collapse; width: 100%; margin: 12px 0 24px; }
th, td { border: 1px solid #ddd; padding: 6px 10px; vertical-align: top;
         font-size: 13px; }
th { background: #f3f3f3; text-align: left; }
code { font-family: "SF Mono", Menlo, monospace; font-size: 12px;
       word-break: break-all; }
.badge { display: inline-block; padding: 2px 8px; border-radius: 10px;
         font-size: 12px; font-weight: 600; }
.badge.vuln { background: #f8d7da; color: #842029; }
.badge.safe { background: #d1e7dd; color: #0f5132; }
.badge.na   { background: #e2e3e5; color: #41464b; }
.summary { background: #f7f9fc; border-left: 4px solid #1a4f8b;
           padding: 10px 14px; }
small.dim { color: #666; }
"""


def _badge(verdict: str) -> str:
    cls = {"vuln": "vuln", "safe": "safe", "na": "na"}.get(verdict, "na")
    label = {"vuln": "vulnerable", "safe": "not vulnerable", "na": "n/a"}[cls]
    return f'<span class="badge {cls}">{label}</span>'


def _verdict_class(payload: Dict[str, Any]) -> str:
    if "vulnerable" in payload:
        return "vuln" if payload["vulnerable"] else "safe"
    if any(k.startswith("vulnerable_") for k in payload):
        any_true = any(v for k, v in payload.items() if k.startswith("vulnerable_"))
        return "vuln" if any_true else "safe"
    return "na"


def render_provider_section(providers: Dict[str, List[str]]) -> str:
    rows = ["<h2>Output A — Provider dependency</h2>", "<table>",
            "<tr><th>Feature</th><th>Hosts observed</th></tr>"]
    for key, label in FEATURE_DISPLAY.items():
        hosts = providers.get(key, [])
        host_html = (
            "<ul>" + "".join(f"<li><code>{escape(h)}</code></li>" for h in hosts) + "</ul>"
            if hosts
            else "<em>not observed</em>"
        )
        rows.append(f"<tr><td>{escape(label)}</td><td>{host_html}</td></tr>")
    rows.append("</table>")
    return "\n".join(rows)


def render_keys_section(leaks: List[api_keys.LeakedKey]) -> str:
    if not leaks:
        return (
            "<h3>Exposed API keys</h3>"
            "<p><em>No third-party API keys detected in capture.</em></p>"
        )
    head = ["<h3>Exposed API keys</h3>", "<table>",
            "<tr><th>Provider</th><th>Key</th><th>Sample host</th>"
            "<th>Hits</th><th>Free-rider</th></tr>"]
    body = []
    for leak in leaks:
        if leak.free_rider_status is None:
            fr = "<small class='dim'>not probed</small>"
        else:
            fr = f"HTTP {leak.free_rider_status} {escape(leak.free_rider_note)[:60]}"
        body.append(
            "<tr>"
            f"<td>{escape(leak.provider)}</td>"
            f"<td><code>{escape(leak.key)}</code></td>"
            f"<td><code>{escape(leak.sample_host)}</code></td>"
            f"<td>{leak.occurrences}</td>"
            f"<td>{fr}</td>"
            "</tr>"
        )
    return "\n".join(head + body + ["</table>"])


def render_vuln_section(verdicts: Dict[str, Dict[str, Any]]) -> str:
    if not verdicts:
        return (
            "<h2>Output B — Vulnerability analysis</h2>"
            "<p><em>No scenario captures found.</em></p>"
        )
    parts = ["<h2>Output B — Vulnerability analysis</h2>"]
    for scenario, payload in verdicts.items():
        cls = _verdict_class(payload)
        parts.append(f"<h3>{escape(scenario)} {_badge(cls)}</h3>")
        parts.append('<div class="summary">')
        parts.append(f"<p>{escape(payload.get('rationale', ''))}</p>")
        parts.append("</div>")

        # render the rest of the verdict as a small key/value table
        parts.append("<table>")
        for k, v in payload.items():
            if k in {"rationale", "scenario"}:
                continue
            if isinstance(v, list):
                if not v:
                    rendered = "<em>none</em>"
                elif isinstance(v[0], dict):
                    inner = ["<table>"]
                    headers = list(v[0].keys())
                    inner.append("<tr>" + "".join(
                        f"<th>{escape(h)}</th>" for h in headers
                    ) + "</tr>")
                    for row in v[:50]:
                        inner.append("<tr>" + "".join(
                            f"<td>{escape(str(row.get(h, '')))}</td>"
                            for h in headers
                        ) + "</tr>")
                    if len(v) > 50:
                        inner.append(
                            f"<tr><td colspan='{len(headers)}'>"
                            f"… {len(v) - 50} more rows omitted</td></tr>"
                        )
                    inner.append("</table>")
                    rendered = "\n".join(inner)
                else:
                    rendered = ", ".join(escape(str(x)) for x in v)
            elif isinstance(v, dict):
                rendered = "<br>".join(
                    f"{escape(str(kk))}: {escape(str(vv))}" for kk, vv in v.items()
                )
            else:
                rendered = escape(str(v))
            parts.append(f"<tr><th>{escape(k)}</th><td>{rendered}</td></tr>")
        parts.append("</table>")
    return "\n".join(parts)


def render_classifier_section(classifier_result: Optional[Dict[str, Any]]) -> str:
    if classifier_result is None:
        return ""
    parts = ["<h3>Claude-assisted classification</h3>"]
    summary = classifier_result.get("provider_summary", {})
    if summary:
        parts.append("<table><tr><th>Feature</th><th>Providers</th></tr>")
        for key, label in FEATURE_DISPLAY.items():
            ps = summary.get(key, [])
            cell = (
                "<ul>" + "".join(f"<li><code>{escape(p)}</code></li>" for p in ps) + "</ul>"
                if ps
                else "<em>none</em>"
            )
            parts.append(f"<tr><td>{escape(label)}</td><td>{cell}</td></tr>")
        parts.append("</table>")
    classifications = classifier_result.get("classifications") or []
    if classifications:
        parts.append(
            f"<p><small class='dim'>{len(classifications)} requests classified.</small></p>"
        )
    return "\n".join(parts)


def render_capture_index(per_capture: List[Dict[str, Any]]) -> str:
    if not per_capture:
        return ""
    rows = ["<h2>Captures</h2>", "<table>",
            "<tr><th>File</th><th>Wallet</th><th>Scenario</th>"
            "<th>Records</th><th>Hosts</th></tr>"]
    for entry in per_capture:
        rows.append(
            "<tr>"
            f"<td><code>{escape(entry['path'])}</code></td>"
            f"<td>{escape(entry['wallet'])}</td>"
            f"<td>{escape(entry['scenario'])}</td>"
            f"<td>{entry['record_count']}</td>"
            f"<td>{entry['unique_hosts']}</td>"
            "</tr>"
        )
    rows.append("</table>")
    return "\n".join(rows)


def render_report(
    title: str,
    captures_index: List[Dict[str, Any]],
    providers: Dict[str, List[str]],
    leaks: List[api_keys.LeakedKey],
    vuln_verdicts: Dict[str, Dict[str, Any]],
    classifier_result: Optional[Dict[str, Any]],
) -> str:
    parts = [
        "<!DOCTYPE html>",
        "<html><head><meta charset='utf-8'>",
        f"<title>{escape(title)}</title>",
        f"<style>{CSS}</style>",
        "</head><body>",
        f"<h1>{escape(title)}</h1>",
        render_capture_index(captures_index),
        render_provider_section(providers),
        render_classifier_section(classifier_result),
        render_keys_section(leaks),
        render_vuln_section(vuln_verdicts),
        "</body></html>",
    ]
    return "\n".join(p for p in parts if p)


# ---------------------------------------------------------------- main flow


def run(
    capture_targets: List[str],
    wallet_override: Optional[str],
    output_path: str,
    use_claude: bool,
    probe_keys: bool,
) -> int:
    paths = _iter_log_paths(capture_targets)
    if not paths:
        print("no capture files matched", file=sys.stderr)
        return 1

    all_records: List[Dict[str, Any]] = []
    captures_index: List[Dict[str, Any]] = []
    by_scenario: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    detected_wallet: Optional[str] = None

    for path in paths:
        records = load_records(path)
        if not records:
            continue
        wallet = wallet_override or records[0].get("wallet") or path.stem.split("__")[0]
        detected_wallet = detected_wallet or wallet
        scenario = records[0].get("scenario") or path.stem.rsplit("__", 1)[-1]

        captures_index.append({
            "path": str(path),
            "wallet": wallet,
            "scenario": scenario,
            "record_count": len(records),
            "unique_hosts": len({r.get("host", "") for r in records}),
        })

        all_records.extend(records)
        # Trust per-record scenario field for vuln dispatch (single capture
        # may carry multiple scenarios when switched at runtime).
        for r in records:
            by_scenario[r.get("scenario") or scenario].append(r)

    title = f"WalletScope report — {detected_wallet or 'unknown'}"

    providers = aggregate_providers(all_records)
    leaks = api_keys.extract_from_records(all_records)
    if probe_keys and leaks:
        api_keys.free_rider_check(leaks, pause=0.2)

    vuln_verdicts: Dict[str, Dict[str, Any]] = {}
    for scenario, items in by_scenario.items():
        vuln_verdicts[scenario] = vuln_analyzer.analyze_scenario(scenario, items)

    classifier_result = None
    if use_claude and TrafficClassifier is not None:
        try:
            classifier = TrafficClassifier()
            classifier_result = classifier.analyze_traffic(all_records)
        except Exception as exc:
            print(f"classifier disabled: {exc}", file=sys.stderr)

    html = render_report(
        title=title,
        captures_index=captures_index,
        providers=providers,
        leaks=leaks,
        vuln_verdicts=vuln_verdicts,
        classifier_result=classifier_result,
    )

    out_path = Path(output_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(html, encoding="utf-8")
    print(f"report written: {out_path}")

    summary_payload = {
        "wallet": detected_wallet,
        "captures": captures_index,
        "providers": providers,
        "exposed_keys": [asdict(k) for k in leaks],
        "vulnerability": vuln_verdicts,
    }
    json_path = out_path.with_suffix(".json")
    json_path.write_text(json.dumps(summary_payload, indent=2, default=str), encoding="utf-8")
    print(f"summary  : {json_path}")
    return 0


def parse_args(argv: List[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="WalletScope analyzer")
    parser.add_argument(
        "captures", nargs="+",
        help="capture files or directories containing *.jsonl captures",
    )
    parser.add_argument("--wallet", default=None,
                        help="wallet name to display (overrides per-record wallet)")
    parser.add_argument("--out", default="report.html",
                        help="HTML report path (default: report.html)")
    parser.add_argument("--no-claude", action="store_true",
                        help="skip Claude-assisted classification")
    parser.add_argument("--probe-keys", action="store_true",
                        help="re-issue requests to verify exposed API keys still work")
    return parser.parse_args(argv)


def main(argv: List[str]) -> int:
    args = parse_args(argv)
    return run(
        capture_targets=args.captures,
        wallet_override=args.wallet,
        output_path=args.out,
        use_claude=not args.no_claude,
        probe_keys=args.probe_keys,
    )


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
