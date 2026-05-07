# WalletScope


WalletScope automatically uncovers (i) the **backend service models**
behind crypto wallet extensions and (ii) their **security robustness**
under emerging phishing attacks. The four-phase pipeline maps cleanly
onto the codebase:

| Phase | Paper section | Code |
|---|---|---|
| 1. DApp setup | §III.D Phase 1 | [`walletscope/dapps/`](walletscope/dapps/) |
| 2. Wallet UI driver | §III.D Phase 2 | [`walletscope/driver/`](walletscope/driver/) |
| 3a. Provider dependency | §III.D Phase 3 / Task A | [`walletscope/proxy/`](walletscope/proxy/) |
| 3b. Vulnerability analysis | §III.D Phase 3 / Task B | [`walletscope/proxy/vuln_analyzer.py`](walletscope/proxy/vuln_analyzer.py) |
| 4. Reporting | §III.D Phase 4 | [`walletscope/proxy/analyzer.py`](walletscope/proxy/analyzer.py) |

```
walletscope/                       Python package
├── __main__.py                    CLI entry — python -m walletscope ...
├── config.py                      central .env loader + project paths
├── scenarios.py                   scenario → DApp mapping + proxy notification
├── orchestrator.py                glue: serve DApp → notify proxy → run wallet flow
├── driver/                        Phase 2 — wallet UI driver (Selenium + CDP + pyautogui)
├── proxy/                         Phase 3 — mitmproxy addon, classifier, analyzer
├── dapps/                         Phase 1 — DApps the wallet connects to
│   ├── benign/                    baseline (claim() on Ethereum mainnet)
│   ├── sim_phish_block/           A2: block-number-triggered storage flip
│   ├── sim_phish_addr/            A2: setBA-triggered storage flip
│   └── caller/                    multi-wallet selector debug page
└── data/                          outputs 
    ├── captures/                  mitmproxy JSONL — one file per (wallet, scenario)
    ├── page_sources/              driver-captured wallet popup HTML
    ├── reports/                   HTML + JSON reports
    └── diagnostics/               driver debug screenshots

```

---

## 1. System requirements

| Requirement | Why |
|---|---|
| **macOS** | The driver uses `pyautogui` for keystrokes and `osascript` for window-focus checks. Linux/Windows have not been ported. |
| **Python ≥ 3.10** | f-strings, `match`-free, type hints. Tested on 3.11. |
| **Google Chrome ≥ 147** | Driver attaches via Chrome DevTools Protocol. Earlier Chrome may work but is untested. |
| **mitmproxy ≥ 10** | For Phase 3 traffic capture.  |
| **Anthropic API key** |  Required only for the Claude-assisted provider classifier.  |

The host machine must be able to display Chrome GUI windows — the driver
clicks visible UI elements via Selenium and types passwords via OS-level
keystrokes. 

---

## 2. Install

```bash
git clone <this repo> walletscope
cd walletscope
pip install -r requirements.txt
```

Dependencies installed:

- `selenium`, `websocket-client`, `pyautogui`, `python-dotenv` — Phase 2 driver
- `mitmproxy`, `anthropic`, `pyyaml` — Phase 3 capture + classification

---

## 3. One-time Chrome profile setup

This is the most error-prone part of the setup. **Read every step.**

### 3.1 Create an isolated test profile

WalletScope runs in a dedicated Chrome `user-data-dir` so the test
environment is fully isolated from your daily Chrome (separate cookies,
extensions, history, sync state).

```bash
"/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" \
  --user-data-dir="$HOME/chrome_selenium_profile" \
  --profile-directory="Profile 9"
```

The first launch creates `~/chrome_selenium_profile/Profile 9/` and opens
a fresh Chrome window with no bookmarks, no extensions, no Google
account. **Do not sign in to your real Google account in this profile.**

For convenience, add an alias to `~/.zshrc`:

```bash
alias chrome-walletscope='"/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" --user-data-dir="$HOME/chrome_selenium_profile" --profile-directory="Profile 9"'
```

After `source ~/.zshrc`, simply run `chrome-walletscope` to launch the
test profile.

### 3.2 Install wallet extensions

Inside the test Chrome window, install each wallet you want to evaluate
from the **Chrome Web Store**.


After installation:

1. Click Chrome's puzzle-piece icon (top-right) → **pin every installed
   wallet** to the toolbar. Without pinning, EIP-6963 wallet announce
   may not fire reliably.
2. Click each wallet icon to open it for the first time.

### 3.3 Initialize each wallet

For each wallet:

1. **Create a new wallet** (do **not** import your real seed phrase —
   these accounts are throwaway).
2. **Set a password.** Use the **same password across all wallets** —
   the driver only reads `WALLET_PASSWORD` from `.env`.
3. **Back up the seed phrase** in case you want to move test funds
   between machines.

if testing on Sepolia testnet: 

4. **Add Sepolia testnet** if not already present:
   - MetaMask: Networks → Show test networks → select Sepolia
   - Rabby: Settings → Chain → enable Sepolia (Chain ID 11155111)
5. **Fund the test account on Sepolia.** The benign DApp lives on Ethereum
   mainnet (it just verifies wallet connectivity); the A2 phishing DApps
   are deployed on Sepolia. To run those scenarios you need test ETH:
   - <https://www.alchemy.com/faucets/ethereum-sepolia>
   - <https://sepoliafaucet.com/>
   - <https://sepolia-faucet.pk910.de/> (proof-of-work, no signup)
6. Send 0.05+ SepoliaETH to the test wallet address.

### 3.4  Install the mitmproxy CA

This step is required only if you plan to use Phase 3 traffic capture
(`WALLETSCOPE_USE_PROXY=1`). Without the CA, HTTPS traffic from the
wallet extensions decrypts to TLS errors and the rule engine sees only
URL/host metadata.

In the test Chrome profile (after wallets are installed):

1. Set the system HTTP/HTTPS proxy to `127.0.0.1:8081`
   (System Settings → Network → choose your interface → Details →
   Proxies → check HTTP / HTTPS, set Server to `127.0.0.1`, Port `8081`).
   Alternatively, install a proxy-switcher Chrome extension.
2. Visit <http://mitm.it> in the test Chrome.
3. Download the **macOS** PEM certificate.
4. Open it → Keychain Access → search "mitmproxy" → double-click → Trust
   → "When using this certificate" → **Always Trust**.
5. Disable the system proxy when not running mitmproxy
   (otherwise normal Chrome browsing breaks).

### 3.5 One-time DApp connection approval

Each wallet remembers which DApps it has authorized. The driver flows
**assume the test DApp is already authorized** — they don't include a
"click Approve in the connection popup" step. Without this step, the
DApp's `eth_requestAccounts` blocks waiting for user input, the claim
button stays `disabled`, and the flow times out.

Do this manually, once per wallet, before the first automated run:

```bash
# Shell A — start the DApp server
python -m walletscope serve benign

# Shell B — open the test Chrome
chrome-walletscope
```

In the test Chrome:

1. Visit `http://127.0.0.1:8080/index.html`.
2. Click **MetaMask** in the EIP-6963 wallet selector.
3. MetaMask opens a "Connect to 127.0.0.1:8080?" popup → click **Connect**.
4. Verify the page's **Call claim()** button turns blue (enabled).
   Don't click it — the connection is what matters.
5. Click **Disconnect** to disconnect, then repeat for **Rabby** and any
   other wallet you intend to test.
6. Quit Chrome (`Cmd + Q` — fully exit, not just close window).
7. Stop the DApp server in Shell A (`Ctrl + C`).

---

## 4. Configuration

```bash
cp walletscope/.env.example walletscope/.env
```

Edit `.env`:

| Variable | Required? | Notes |
|---|---|---|
| `WALLET_PASSWORD` | yes | Same password used in every test wallet. |
| `CHROME_PROFILE_DIR` | no | Default: `~/chrome_selenium_profile` |
| `CHROME_PROFILE_NAME` | no | Default: `Profile 9` |
| `CHROME_BIN` | no | Default: `/Applications/Google Chrome.app/Contents/MacOS/Google Chrome` |
| `CDP_PORT` | no | Default: `9222`. Chrome DevTools Protocol port. |
| `DAPP_BIND` / `DAPP_PORT` | no | Default `127.0.0.1:8080` for the static DApp server. |
| `MITMPROXY_PORT` | no | Default `8081`. |
| `WALLETSCOPE_USE_PROXY` | no | Set to `1` to route Chrome through mitmproxy. Default `0`. |
| `ANTHROPIC_API_KEY` | no | Optional — needed for Claude-assisted classification. |

For Claude classification, set `ANTHROPIC_API_KEY` in `.env`. Non-secret
classifier settings (model, temperature, batch size) live in
[`walletscope/proxy/config.yaml`](walletscope/proxy/config.yaml); the API
key is never read from there.

---

## 5. Running the pipeline


### 5.1 Drive a single scenario (Phase 1 + 2 only — no traffic capture)

```bash
python -m walletscope drive metamask benign
```

Effect, in order:

1. Starts the DApp HTTP server on `127.0.0.1:8080`.
2. Pokes `http://walletscope.local/scenario/benign` through the proxy
   so the addon (if running) tags subsequent traffic with that scenario.
   Skipped silently if mitmproxy isn't up.
3. Launches Chrome with the test profile, navigates to the DApp.
4. Clicks the wallet's button in the EIP-6963 selector.
5. Waits for the claim button to enable, clicks it.
6. Types `WALLET_PASSWORD` (only after verifying Chrome is the
   frontmost app — the focus guard refuses otherwise).
7. Captures the wallet popup HTML to `walletscope/data/page_sources/<Wallet>_pagesource.txt`.

### 5.2 Full pipeline (Phase 1 + 2 + 3 + 4)

```bash
# Shell A — start mitmproxy with the WalletScope addon
WALLETSCOPE_WALLET=metamask \
WALLETSCOPE_SCENARIO=benign \
WALLETSCOPE_LOG_DIR=walletscope/data/captures \
mitmdump -p 8081 -s walletscope/proxy/addon.py

# Shell B — drive (USE_PROXY=1 routes Chrome through mitmproxy)
WALLETSCOPE_USE_PROXY=1 python -m walletscope drive metamask benign

# Stop the mitmdump in Shell A: Ctrl+C

# Shell B — analyze
python -m walletscope analyze metamask --probe-keys
```

The CLI also prints the exact mitmdump command it expects:

```bash
python -m walletscope addon
# WALLETSCOPE_LOG_DIR=.../walletscope/data/captures WALLETSCOPE_WALLET=<wallet> \
# WALLETSCOPE_SCENARIO=<scenario> mitmdump -p 8081 -s .../walletscope/proxy/addon.py
```

### 5.3 Switch scenario without restarting the proxy

A single long-running `mitmdump` can cover the full matrix:

```bash
# Shell B — switch scenario tag mid-session
python -m walletscope notify A2_sim_phish_block

# subsequent traffic is now logged to <wallet>__A2_sim_phish_block.jsonl
WALLETSCOPE_USE_PROXY=1 python -m walletscope drive metamask A2_sim_phish_block
```

The orchestrator already does this for you when running
`python -m walletscope drive ...`.

### 5.4 Free-rider key probe

The analyzer can verify whether leaked third-party API keys are
exploitable from outside the wallet:

```bash
python -m walletscope analyze metamask --probe-keys
```



The probe is also available standalone:

```bash
python walletscope/proxy/api_keys.py walletscope/data/captures/metamask__benign.jsonl --probe
```

### 5.5 Skip Claude

The rule-based classifier and free-rider probe work without Claude:

```bash
python -m walletscope analyze metamask --no-claude
```

---

## 6. Output files

```
walletscope/data/
├── captures/
│   └── <wallet>__<scenario>.jsonl       Phase 3 traffic capture.
│                                        One JSONL line per HTTP exchange,
│                                        stamped with wallet + scenario tags.
│                                        Schema: time, wallet, scenario,
│                                        method, url, host, path, tag,
│                                        is_jsonrpc, rpc_method, rpc_params,
│                                        request_body, response_status,
│                                        response_headers, response_body.
│
├── page_sources/
│   └── <Wallet>_pagesource.txt         Phase 2 captured wallet popup HTML.
│                                        Overwritten on every run.
│                                        Note: csp() currently writes the
│                                        last extension target it sees, not
│                                        only the wallet — see Limitations.
│
├── reports/
│   ├── <wallet>_report.html             Combined Phase 4 report:
│   │                                    - capture index
│   │                                    - rule-based provider attribution
│   │                                    - Claude-classified provider summary
│   │                                    - leaked API keys (with free-rider
│   │                                      probe results if --probe-keys)
│   │                                    - per-scenario vulnerability verdict
│   │
│   └── <wallet>_report.json             Same data as the HTML, machine-readable.
│
└── diagnostics/
    ├── diag_open.png                    Screenshot of test Chrome's first DApp page.
    │                                    Generated by scripts/diag_open.py.
    └── selector_failed_<name>.png       Auto-saved when selector() can't  find a wallet button — useful to see what was on screen at the time.
```

The `walletscope/data/` directory is gitignored. Captured page sources, JSONL logs,
and reports never leave your machine.

---

## 7. Example: end-to-end MetaMask run

A successful run looks like this. Output abbreviated.

```bash
# Shell A
$ WALLETSCOPE_WALLET=metamask WALLETSCOPE_SCENARIO=benign \
  WALLETSCOPE_LOG_DIR=walletscope/data/captures \
  mitmdump -p 8081 -s walletscope/proxy/addon.py
[mitmdump listening]

# Shell B
$ WALLETSCOPE_USE_PROXY=1 python -m walletscope drive metamask benign
=== walletscope: wallet=metamask scenario=benign ===
DApp server: walletscope/dapps/benign on 127.0.0.1:8080
proxy ack: scenario set to benign
Got HTML → walletscope/data/page_sources/MetaMask_pagesource.txt
=== flow complete ===

# Shell B (after Ctrl+C in Shell A)
$ python -m walletscope analyze metamask --probe-keys
Total requests: 183
Ethereum mainnet requests: 111
Analyzing batch 1 (50 requests)...
Analyzing batch 2 (50 requests)...
Analyzing batch 3 (11 requests)...
report written: walletscope/data/reports/metamask_report.html
summary  : walletscope/data/reports/metamask_report.json
```

Resulting `metamask_report.json` excerpt:

```json
{
  "wallet": "metamask",
  "providers": {
    "rpc_relay":               ["mainnet.infura.io"],
    "simulation":              ["mainnet.infura.io",
                                "tx-sentinel-ethereum-mainnet.api.cx.metamask.io"],
    "token_price":             ["price.api.cx.metamask.io"],
    "recipient_verification":  ["mainnet.infura.io"]
  },
  "exposed_keys": [
    {
      "provider": "infura",
      "key": "b6bf7d3508c941499b10025c0776eaf8",
      "occurrences": 28,
      "free_rider_status": 200,
      "free_rider_note": "OK"
    }
  ]
}
```

Compare to paper Table 1 (MetaMask row): RPC = infura, simulation =
infura, token price = metamask, recipient verify = infura, exposed key =
infura. ✓ All five fields match.

---

## 8. Troubleshooting

### Driver hangs / `selector` times out / `b.text == ''`

- `Preferences.profile.exit_type == 'Crashed'` from a previous `pkill` —
  the driver clears this automatically on each launch
  (`_clear_crashed_flag()`). If you've manually killed Chrome and the
  driver still hangs, delete and re-create the profile.
- Chrome window allocated at 0×0 — the driver passes `--window-size=1280,900`,
  uses `open -na` to launch, and disables the session-crashed bubble.
  All three are required on Chrome 147+.
- `--disable-web-security`, `--disable-features=IsolateOrigins,site-per-process`,
  and similar flags trigger Chrome's "incorrect profile type" error.
  The driver uses a minimal flag set; do not add these back.

### "Address already in use" on port 8080 / 8081 / 9222

```bash
lsof -i :8080 -i :8081 -i :9222
kill <pid>
```

Or, more aggressively:

```bash
pkill -9 -f "user-data-dir=$HOME/chrome_selenium_profile"
pkill -f chromedriver
pkill -f "mitmdump.*walletscope"
```

The `serve_scenario()` function precondition-checks the DApp port and
fails fast if it's busy.

### Wallet password gets typed into the terminal

`pswdInput()` includes a frontmost-app guard: it asks `osascript` for
the foreground macOS app and refuses to type unless that app is
"Google Chrome". If you ever see your password in zsh history:

1. Change the wallet password.
2. Edit `~/.zsh_history` to remove the leaked line.
3. Update `.env` with the new `WALLET_PASSWORD`.
4. File a bug — the focus guard should have caught it.

### Selector can't find the wallet button

1. Confirm the wallet extension is installed and pinned in the
   test Chrome profile (`ls ~/chrome_selenium_profile/Profile\ 9/Extensions/`).
2. Confirm you completed the one-time DApp approval (§3.5).
3. Check `walletscope/data/diagnostics/selector_failed_<name>.png` for the screenshot
   the driver auto-saves on timeout.

### Claude returns "credit balance is too low"

Top up at <https://console.anthropic.com/settings/billing>, or skip the
classifier with `--no-claude`. The rule-based provider attribution still
runs.

### HTTPS traffic decrypts to TLS errors in the capture

The mitmproxy CA isn't trusted by the test Chrome profile. Re-do §3.4.

---


