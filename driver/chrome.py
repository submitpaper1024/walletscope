"""
Phase 2 — wallet UI driver.

Launches Chrome with the wallet profile, serves the DApp via a static
http.server, and drives the wallet UI through a mix of Selenium (DApp
tab) + CDP WebSocket (extension popup) + pyautogui (password keystrokes).

Config flows in from walletscope.config (loaded from walletscope/.env).
"""

import atexit
import json
import os
import subprocess
import time
import urllib.request

import pyautogui
import websocket
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from .. import config, scenarios
from .click import (
    Change_max_base_fee,
    click_Custom,
    click_Normal,
    click_Save,
    click_connect_Nufi,
    click_ignore_and_proceed,
    click_unlock,
    next_id,
)
from .result import check_file_for_keywords  # noqa: F401


# Mirror config so legacy callers can still read these names directly.
DAPP_BIND = config.DAPP_BIND
DAPP_PORT = config.DAPP_PORT
DAPP_URL = config.DAPP_URL
CHROME_PROFILE_DIR = config.CHROME_PROFILE_DIR
CHROME_PROFILE_NAME = config.CHROME_PROFILE_NAME
CHROME_BIN = config.CHROME_BIN
CDP_PORT = config.CDP_PORT


# ----------------------------------------------------------------- DApp server

def _port_in_use(host, port) -> bool:
    import socket
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(0.3)
    try:
        s.connect((host, int(port)))
        return True
    except (ConnectionRefusedError, OSError):
        return False
    finally:
        s.close()


_DAPP_PROC: "subprocess.Popen | None" = None


def _stop_dapp_server():
    """Terminate the DApp http.server child if it's still running.
    Registered via atexit so a crashed driver doesn't leave port 8080 held."""
    global _DAPP_PROC
    proc = _DAPP_PROC
    if proc is None or proc.poll() is not None:
        return
    try:
        proc.terminate()
        try:
            proc.wait(timeout=2)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=2)
    except Exception:
        pass
    _DAPP_PROC = None


def serve_scenario(scenario: str):
    """Start the DApp http.server for a scenario (serves walletscope/dapps/<mapping>/).

    Stops any previously-started DApp server (so back-to-back runs don't
    trip over their own orphaned 8080 holder) and registers an atexit
    handler to clean up the new one when the Python process exits."""
    global _DAPP_PROC
    target_dir = scenarios.dapp_dir(scenario)
    if not target_dir.is_dir():
        raise FileNotFoundError(f"DApp directory not found: {target_dir}")

    # If we started a server earlier in this process, stop it before re-binding.
    _stop_dapp_server()
    # Wait for the kernel to release the port after our own child exits.
    for _ in range(20):
        if not _port_in_use(DAPP_BIND, DAPP_PORT):
            break
        time.sleep(0.1)

    if _port_in_use(DAPP_BIND, DAPP_PORT):
        raise RuntimeError(
            f"DApp port {DAPP_BIND}:{DAPP_PORT} already in use. "
            f"Run `lsof -i :{DAPP_PORT}` and kill the holder, then retry."
        )
    os.chdir(target_dir)
    _DAPP_PROC = subprocess.Popen(
        ["python3", "-m", "http.server", DAPP_PORT, "--bind", DAPP_BIND]
    )
    atexit.register(_stop_dapp_server)
    # Wait briefly for the child to actually bind, then verify.
    for _ in range(20):
        if _port_in_use(DAPP_BIND, DAPP_PORT):
            break
        time.sleep(0.1)
    else:
        raise RuntimeError(
            f"DApp server on {DAPP_BIND}:{DAPP_PORT} failed to start"
        )
    print(f"DApp server: {target_dir} on {DAPP_BIND}:{DAPP_PORT}")


# Legacy aliases used by per-wallet flows.
def Dapp_running():
    serve_scenario("benign")


def Dapp_running_Blocknumber():
    serve_scenario("A2_sim_phish_block")


# ------------------------------------------------------------------- Selenium

def _clear_crashed_flag():
    """Mark the Chrome profile as cleanly exited.

    Without this, repeated pkill of Chrome leaves exit_type='Crashed' in
    Preferences. Chrome then opens with a hidden "restore tabs?" bubble
    that wedges the renderer (window allocates with 0×0 size, page is
    visibilityState=hidden). Done in-place by editing the JSON file.
    """
    pref_path = os.path.join(CHROME_PROFILE_DIR, CHROME_PROFILE_NAME, "Preferences")
    if not os.path.exists(pref_path):
        return
    try:
        with open(pref_path, "r", encoding="utf-8") as f:
            prefs = json.load(f)
        prefs.setdefault("profile", {})
        prefs["profile"]["exit_type"] = "Normal"
        prefs["profile"]["exited_cleanly"] = True
        with open(pref_path, "w", encoding="utf-8") as f:
            json.dump(prefs, f)
    except Exception as exc:
        print(f"[chrome] could not reset exit_type: {exc}")


def SetUpDriver():
    """
    Launch Chrome via macOS `open -na` for a proper GUI session, then
    attach Selenium via debuggerAddress. Chrome 147+ launched directly
    by chromedriver allocates a 0×0 hidden window, so we go through the
    macOS app launcher instead.
    """
    _clear_crashed_flag()

    args = [
        "open",
        "-na",
        "Google Chrome",
        "--args",
        f"--user-data-dir={CHROME_PROFILE_DIR}",
        f"--profile-directory={CHROME_PROFILE_NAME}",
        f"--remote-debugging-port={CDP_PORT}",
        "--remote-allow-origins=*",
        "--no-first-run",
        "--no-default-browser-check",
        "--disable-session-crashed-bubble",
        "--restore-last-session=false",
        "--window-size=1280,900",
    ]
    if config.USE_PROXY:
        args.append(f"--proxy-server=http://127.0.0.1:{config.MITMPROXY_PORT}")
    subprocess.Popen(args)

    # Wait for Chrome's CDP endpoint to come up.
    import urllib.error
    deadline = time.time() + 20
    while time.time() < deadline:
        try:
            urllib.request.urlopen(
                f"http://127.0.0.1:{CDP_PORT}/json/version", timeout=1
            ).read()
            break
        except (urllib.error.URLError, OSError):
            time.sleep(0.3)
    else:
        raise RuntimeError(
            f"Chrome did not expose CDP on 127.0.0.1:{CDP_PORT} within 20s"
        )

    opts = Options()
    opts.add_experimental_option("debuggerAddress", f"127.0.0.1:{CDP_PORT}")
    return webdriver.Chrome(options=opts)


def All_The_Way_To_8080():
    driver = SetUpDriver()
    # Give Chrome a moment to come up before talking to it.
    time.sleep(2)
    # Force a real window size; without this Chrome sometimes lays out
    # the page at 0×0 and Selenium reports every element as not visible
    # (.text == '', is_displayed() == False).
    try:
        driver.set_window_size(1280, 900)
        driver.set_window_position(120, 80)
    except Exception as exc:
        print(f"[chrome] set_window_size/position failed: {exc}")
    # Bring Chrome to the foreground (macOS) so wallet popups can grab
    # focus and pyautogui keystrokes land in the right window.
    try:
        subprocess.run(
            ["osascript", "-e", 'tell application "Google Chrome" to activate'],
            timeout=2, check=False,
        )
    except Exception:
        pass

    driver.get(DAPP_URL)
    # Block until document.readyState === 'complete'; abort if Chrome
    # never reaches it (extension content scripts can still be loading
    # after this, but at least the DApp DOM exists).
    WebDriverWait(driver, 30).until(
        lambda d: d.execute_script("return document.readyState") == "complete"
    )
    return driver


def Check_Connection(driver):
    return "Ready to call claim()" in driver.page_source


def Click_Claim(driver):
    """Click the DApp's "Call claim()" button. Waits for it to become
    enabled — first-time flows need the user / wallet to approve the
    connection request before the DApp's JS un-disables the button."""
    xpath = "//button[contains(text(), 'Call claim()')]"
    WebDriverWait(driver, 30).until(
        lambda d: (
            (b := d.find_elements(By.XPATH, xpath))
            and b[0].is_displayed()
            and b[0].is_enabled()
        )
    )
    driver.find_element(By.XPATH, xpath).click()


def selector(driver, name):
    """Click a wallet button on a EIP-6963 multi-wallet selector page.

    Raises if the button can't be found within the timeout — the caller
    must NOT proceed to pswdInput() in that case, because pyautogui will
    happily type the password into whatever window currently has focus.
    """
    xpath = f"//button[contains(., '{name}')]"
    try:
        btn = WebDriverWait(driver, 20).until(
            EC.element_to_be_clickable((By.XPATH, xpath))
        )
    except Exception:
        # Diagnostic dump: capture state so we can see why the button is missing.
        diag_dir = config.DATA_DIR / "diagnostics"
        diag_dir.mkdir(parents=True, exist_ok=True)
        try:
            png = diag_dir / f"selector_failed_{name.replace(' ', '_')}.png"
            driver.save_screenshot(str(png))
            print(f"[selector diag] screenshot → {png}")
            print(f"[selector diag] current_url = {driver.current_url}")
            print(f"[selector diag] title       = {driver.title}")
            buttons = driver.find_elements(By.XPATH, "//button")
            print(f"[selector diag] {len(buttons)} <button> on page:")
            for i, b in enumerate(buttons):
                txt = (b.text or "").strip().replace("\n", " | ")[:120]
                print(f"  [{i}] {txt!r}")
        except Exception as diag_exc:
            print(f"[selector diag] dump failed: {diag_exc}")
        raise
    btn.click()


# ----------------------------------------------------------- keyboard / mouse

def _frontmost_app_is_chrome() -> bool:
    """macOS: return True only if Google Chrome is the frontmost application.

    Used as a safety check before pswdInput types the wallet password via
    pyautogui — without this, a misfire would leak the password into
    whatever window happens to be focused (terminal, browser URL bar, …).
    """
    try:
        out = subprocess.check_output(
            [
                "osascript",
                "-e",
                'tell application "System Events" to get name of first '
                "application process whose frontmost is true",
            ],
            text=True,
            timeout=2,
        ).strip()
    except Exception:
        return False
    return out.lower().startswith("google chrome")


def pswdInput():
    """Type the wallet password and press Enter. Reads WALLET_PASSWORD from .env.

    Aborts loudly if Chrome is not the frontmost app; pyautogui will type
    into whatever window happens to be focused, so a silent misfire would
    leak the password to the terminal.
    """
    password = os.environ.get("WALLET_PASSWORD")
    if not password:
        raise RuntimeError(
            "WALLET_PASSWORD not set. Copy .env.example to .env and fill it in."
        )
    time.sleep(2)
    if not _frontmost_app_is_chrome():
        raise RuntimeError(
            "pswdInput aborted: Chrome is not the frontmost application. "
            "The wallet popup probably failed to open. Check the previous "
            "step (selector / connect click) and retry. Refusing to type "
            "the password into a non-Chrome window."
        )
    pyautogui.write(password, interval=0.1)
    time.sleep(1)
    pyautogui.press("enter")
    time.sleep(1)


def oneKey():
    """OneKey shows a passkey popup before the password field; press Esc to dismiss."""
    pyautogui.press("esc")


# --------------------------------------------------------------- CDP plumbing

def _open_cdp_ws():
    resp = urllib.request.urlopen(f"http://localhost:{CDP_PORT}/json/version")
    info = json.loads(resp.read())
    ws_url = info["webSocketDebuggerUrl"]
    print("CDP WebSocket:", ws_url)
    return websocket.create_connection(
        ws_url, header=["Origin: chrome-devtools://devtools"]
    )


def _output_path(filename):
    return str(config.DATA_DIR / "page_sources" / filename)


os.makedirs(str(config.DATA_DIR / "page_sources"), exist_ok=True)


def get_PS(ws, session_id, fileName):
    """Capture outerHTML of the page attached to session_id and write to fileName."""
    ws.send(json.dumps({
        "sessionId": session_id,
        "id": 3,
        "method": "Runtime.evaluate",
        "params": {
            "expression": "document.documentElement.outerHTML",
            "returnByValue": True,
        },
    }))

    resp = json.loads(ws.recv())  # ack — must consume or recv blocks next time
    resp = json.loads(ws.recv())
    result = resp.get("result", {}).get("result", {})
    if "value" in result:
        html_source = result["value"]
        out = _output_path(fileName)
        with open(out, "w") as g:
            g.write(html_source)
        print(f"Got HTML → {out}")
    else:
        print("Runtime.evaluate failed:", resp)


def get_session_id(ws, target_id, fileName):
    ws.send(json.dumps({
        "id": next_id(),
        "method": "Target.attachToTarget",
        "params": {"targetId": target_id, "flatten": True},
    }))
    attach_resp = json.loads(ws.recv())
    session_id = attach_resp["params"]["sessionId"]
    time.sleep(3)
    get_PS(ws, session_id, fileName)


def csp(fileName):
    """Find any extension page and dump its HTML to fileName."""
    ws = _open_cdp_ws()
    ws.send(json.dumps({"id": next_id(), "method": "Target.getTargets"}))
    targets = json.loads(ws.recv())["result"]["targetInfos"]
    for t in targets:
        if t["type"] == "page" and ".html" in t["url"]:
            print(t["targetId"], t["type"], t["url"])
            get_session_id(ws, t["targetId"], fileName)


# ------------------------------------------------------------------- OneKey

def get_session_id_oneKey(ws, target_id):
    ws.send(json.dumps({
        "id": next_id(),
        "method": "Target.attachToTarget",
        "params": {"targetId": target_id, "flatten": True},
    }))
    attach_resp = json.loads(ws.recv())
    session_id = attach_resp["params"]["sessionId"]
    get_PS(ws, session_id, "oneKey_pagesource.txt")

    time.sleep(1)
    click_Normal(ws, session_id)
    time.sleep(1)
    click_Custom(ws, session_id)
    time.sleep(1)
    Change_max_base_fee(ws, session_id)
    time.sleep(1)
    click_Save(ws, session_id)


def csp_oneKey():
    ws = _open_cdp_ws()
    ws.send(json.dumps({"id": 1, "method": "Target.getTargets"}))
    targets = json.loads(ws.recv())["result"]["targetInfos"]
    for t in targets:
        if t["type"] == "page" and ".html" in t["url"]:
            print(t["targetId"], t["type"], t["url"])
            get_session_id_oneKey(ws, t["targetId"])


# --------------------------------------------------------- OneKey 2 (csp_OK)

OK_EXTENSION_ID = "jnmbobjmhlngoefaiojfljckilhhlhcj"


def get_session_id_OK(ws, target_id):
    ws.send(json.dumps({
        "id": next_id(),
        "method": "Target.attachToTarget",
        "params": {"targetId": target_id, "flatten": True},
    }))
    json.loads(ws.recv())
    attach_resp = json.loads(ws.recv())

    try:
        session_id = attach_resp["params"]["sessionId"]
    except KeyError:
        session_id = attach_resp["result"]["sessionId"]

    time.sleep(3)
    focus_js = """
    (function() {
        var input = document.querySelector('input[data-testid="password-input"]');
        if (!input) {
            input = document.querySelector('input[placeholder="Enter your passcode"]');
        }
        if (input) {
            input.click();
            input.focus();
            return "focused";
        }
        return "not found";
    })();
    """
    ws.send(json.dumps({
        "sessionId": session_id,
        "id": 6,
        "method": "Runtime.evaluate",
        "params": {"expression": focus_js, "returnByValue": True},
    }))


def csp_OK(_unused=None):
    """Focus OneKey's password input. Argument is ignored (kept for legacy callers)."""
    ws = _open_cdp_ws()
    ws.send(json.dumps({"id": next_id(), "method": "Target.getTargets"}))
    targets = json.loads(ws.recv())["result"]["targetInfos"]
    for t in targets:
        if t["type"] == "page" and OK_EXTENSION_ID in t["url"]:
            print(t["targetId"], t["type"], t["url"])
            get_session_id_OK(ws, t["targetId"])


# ------------------------------------------------------------------ Backpack

def get_session_id_Backpack(ws, target_id, fileName):
    ws.send(json.dumps({
        "id": next_id(),
        "method": "Target.attachToTarget",
        "params": {"targetId": target_id, "flatten": True},
    }))
    attach_resp = json.loads(ws.recv())
    session_id = attach_resp["params"]["sessionId"]
    time.sleep(3)
    get_PS_Backpack(ws, session_id, fileName)


def get_PS_Backpack(ws, session_id, fileName):
    expr = "document.documentElement.outerHTML"
    ws.send(json.dumps({
        "sessionId": session_id,
        "id": 3,
        "method": "Runtime.evaluate",
        "params": {"expression": expr, "returnByValue": True},
    }))

    resp = json.loads(ws.recv())
    resp = json.loads(ws.recv())
    result = resp.get("result", {}).get("result", {})
    if "value" in result:
        with open(_output_path(fileName), "w") as g:
            g.write(result["value"])
        print(f"Got HTML → {_output_path(fileName)}")
    else:
        print("Runtime.evaluate failed:", resp)

    click_ignore_and_proceed(ws, session_id)
    time.sleep(1)

    ws.send(json.dumps({
        "sessionId": session_id,
        "id": 3,
        "method": "Runtime.evaluate",
        "params": {"expression": expr, "returnByValue": True},
    }))
    resp = json.loads(ws.recv())
    result = resp.get("result", {}).get("result", {})
    if "value" in result:
        with open(_output_path("Backpack_pagesource"), "w") as g:
            g.write(result["value"])
        print(f"Got HTML → {_output_path('Backpack_pagesource')}")
    else:
        print("Runtime.evaluate failed:", resp)


def csp_Backpack(fileName):
    ws = _open_cdp_ws()
    ws.send(json.dumps({"id": next_id(), "method": "Target.getTargets"}))
    targets = json.loads(ws.recv())["result"]["targetInfos"]
    for t in targets:
        if t["type"] == "page" and ".html" in t["url"]:
            print(t["targetId"], t["type"], t["url"])
            get_session_id_Backpack(ws, t["targetId"], fileName)


def backpack_warning():
    csp_Backpack("Backpack Warning.txt")


# ------------------------------------------------------------------ MetaMask

def Click_Claim_Meta(driver):
    btn = driver.find_element(By.XPATH, "//button[contains(text(), 'Call claim()')]")
    btn.click()
    time.sleep(2)
    Meta_Mask_Switch()
    time.sleep(1)
    btn = driver.find_element(By.XPATH, "//button[contains(text(), 'Call claim()')]")
    btn.click()


def Click_Conn_Meta(driver):
    btn = driver.find_element(By.XPATH, "//button[contains(text(), 'Connect Wallet')]")
    btn.click()
    time.sleep(2)
    Meta_Mask_Switch()
    time.sleep(1)


def Meta_Attach(ws, target_id):
    ws.send(json.dumps({
        "id": next_id(),
        "method": "Target.attachToTarget",
        "params": {"targetId": target_id, "flatten": True},
    }))
    attach_resp = json.loads(ws.recv())
    session_id = attach_resp["params"]["sessionId"]
    time.sleep(1)
    pswdInput()
    click_unlock(ws, session_id)
    time.sleep(1)
    Meta_Close_Tab(ws, target_id)


def Meta_Close_Tab(ws, target_id):
    ws.send(json.dumps({
        "id": next_id(),
        "method": "Target.closeTarget",
        "params": {"targetId": target_id},
    }))


def Meta_Mask_Switch():
    ws = _open_cdp_ws()
    ws.send(json.dumps({"id": 1, "method": "Target.getTargets"}))
    targets = json.loads(ws.recv())["result"]["targetInfos"]
    for t in targets:
        if t["type"] == "page" and ".html" in t["url"]:
            print(t["targetId"], t["type"], t["url"])
            Meta_Attach(ws, t["targetId"])


# ---------------------------------------------------------------------- Nufi

def get_session_id_Nufi(ws, target_id, fileName):
    ws.send(json.dumps({
        "id": next_id(),
        "method": "Target.attachToTarget",
        "params": {"targetId": target_id, "flatten": True},
    }))
    attach_resp = json.loads(ws.recv())
    print(attach_resp)
    session_id = attach_resp["params"]["sessionId"]
    time.sleep(3)
    click_connect_Nufi(ws, session_id)


def csp_Nufi(fileName):
    ws = _open_cdp_ws()
    ws.send(json.dumps({"id": next_id(), "method": "Target.getTargets"}))
    targets = json.loads(ws.recv())["result"]["targetInfos"]
    for t in targets:
        if t["type"] == "page" and ".html" in t["url"]:
            print(t["targetId"], t["type"], t["url"])
            get_session_id_Nufi(ws, t["targetId"], fileName)


def nufi_connect():
    return csp_Nufi("Nufi.txt")
