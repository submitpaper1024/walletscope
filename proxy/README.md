# WalletScope — mitm

Capture and analyze browser-extension wallet traffic for the WalletScope
paper. Implements Phase 3 of the framework:

* **Output A — Provider dependency**
  * rule-based + Claude-assisted classification of captured requests into
    the five wallet feature buckets (`token_price`, `tx_history`,
    `recipient_verification`, `rpc_relay`, `simulation`)
  * leaked third-party API key extraction (Infura, Alchemy, QuickNode,
    Etherscan, …) with optional free-rider verification
* **Output B — Vulnerability analysis** (per scenario)
  * `A1_drain` — token draining
  * `A2_sim_phish` — transaction-simulation phishing (static vs real-time)
  * `A3_addr_poison` — address poisoning (zero / dust / fake-token transfers)
  * `recipient_verify` — recipient verification warnings


## Files

| File              | Purpose                                                  |
| ----------------- | -------------------------------------------------------- |
| `mitm_addon.py`   | mitmproxy addon. Captures requests/responses with `wallet` and `scenario` tags. |
| `rule_engine.py`  | Rule-based JSON-RPC / REST classifier driven by `rules.yaml`. |
| `rules.yaml`      | Pluggable rules (semantic + URL/host/method matching).   |
| `common.py`       | JSON-RPC parsing and address heuristics.                 |
| `classifier.py`   | Claude-assisted classifier (`TrafficClassifier`).        |
| `api_keys.py`     | Extract leaked API keys; `--probe` re-issues them.       |
| `vuln_analyzer.py`| Per-scenario vulnerability dispatch (Output B).          |
| `analyzer.py`     | End-to-end report generator (Output A + Output B).       |
| `config.yaml`     | Claude model + analysis settings + feature definitions.  |


## Install

```
pip install -r requirements.txt
```

Configure the Claude API key (only needed for the AI-assisted Output A
section):

```
cp config.yaml.example config.yaml
# then edit config.yaml and set claude.api_key
# or:
export ANTHROPIC_API_KEY=...
```


## Capture workflow

The addon stamps each record with `wallet` and `scenario`, and writes one
JSONL file per `(wallet, scenario)` pair under `WALLETSCOPE_LOG_DIR`
(default `captures/`).

### Per-scenario invocation (recommended)

Run mitmdump once per scenario:

```
WALLETSCOPE_WALLET=metamask \
WALLETSCOPE_SCENARIO=A1_drain \
mitmdump -s mitm_addon.py
```

Each scenario writes to `captures/<wallet>__<scenario>.jsonl`. Repeat for
the other scenarios (`benign`, `A2_sim_phish`, `A3_addr_poison`,
`recipient_verify`).

### Single mitmdump, scenario switched at runtime

If you prefer a single long-running proxy, switch scenarios on the fly by
making the wallet (or any browser tab proxied through mitmproxy) hit a
sentinel URL:

```
http://walletscope.local/scenario/A2_sim_phish
```

The addon intercepts that request, updates its scenario tag, and never
forwards it to the network. Subsequent captures land in
`captures/<wallet>__A2_sim_phish.jsonl`.

### HTTPS

mitmproxy's CA must be trusted by the wallet/browser. Visit
<http://mitm.it> through the proxy to install it.


## Generate the report

```
python analyzer.py captures/ --wallet metamask --out reports/metamask.html
```

Outputs:

* `reports/metamask.html` — combined report (provider deps + leaked keys +
  per-scenario verdicts + Claude classification table).
* `reports/metamask.json` — machine-readable summary of the same data.

Useful flags:

| Flag             | Effect                                           |
| ---------------- | ------------------------------------------------ |
| `--no-claude`    | Skip Claude classification (Output A still includes rule-based providers + leaked keys). |
| `--probe-keys`   | Re-issue a single probe request per leaked key (free-rider check from result1.tex §B). |
| `--wallet NAME`  | Override the wallet label on the report.         |

Single-purpose entry points are also available:

```
python api_keys.py captures/metamask__benign.jsonl --probe
python vuln_analyzer.py captures/metamask__A1_drain.jsonl
```


## Scenario semantics

| Scenario           | Detection signal                                                                 |
| ------------------ | -------------------------------------------------------------------------------- |
| `benign`           | baseline traffic; no vuln check                                                  |
| `A1_drain`         | vulnerable iff `submit_tx` was issued with **no** preceding simulation call      |
| `A2_sim_phish`     | vulnerable iff simulation fired only once (static); safe iff simulated repeatedly across multiple seconds |
| `A3_addr_poison`   | inspects `tx_history` responses for ERC-20 Transfer entries; flags zero-value, dust (<1 USDT raw), or non-canonical USDT contracts |
| `recipient_verify` | scans for any captured response containing a phishing/scam/risk warning keyword  |

The rationale text in each verdict explains what was observed; thresholds
live near the top of `vuln_analyzer.py`.


## Gotchas

* The Claude classifier filters captures down to Ethereum mainnet
  requests; testnet-only captures will produce an empty Output A AI
  section.
* Old captures (predating the scenario tagging) still load; they are
  treated as a single anonymous scenario and Output B will mark them as
  `n/a`.
* `pyautogui`-based wallet UI driving (Phase 2) is not part of this
  module; bring your own driver.
