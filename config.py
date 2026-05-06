"""
Centralized configuration. All env vars + project paths flow through here
so the rest of the package doesn't repeat path math or dotenv loading.

Loaded once on first import; reading os.environ later still works
because dotenv populated the process env.
"""

import os
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent
PACKAGE_ROOT = Path(__file__).resolve().parent

DAPPS_DIR = PACKAGE_ROOT / "dapps"
DATA_DIR = PACKAGE_ROOT / "data"
CAPTURES_DIR = DATA_DIR / "captures"
REPORTS_DIR = DATA_DIR / "reports"

load_dotenv(PACKAGE_ROOT / ".env")


def env(name: str, default: str = "") -> str:
    val = os.environ.get(name, "")
    return val if val else default


WALLET_PASSWORD = env("WALLET_PASSWORD")

CHROME_BIN = env(
    "CHROME_BIN",
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
)
CHROME_PROFILE_DIR = env(
    "CHROME_PROFILE_DIR",
    str(Path.home() / "chrome_selenium_profile"),
)
CHROME_PROFILE_NAME = env("CHROME_PROFILE_NAME", "Profile 9")
CDP_PORT = env("CDP_PORT", "9222")

DAPP_BIND = env("DAPP_BIND", "127.0.0.1")
DAPP_PORT = env("DAPP_PORT", "8080")
DAPP_URL = env("DAPP_URL", f"http://{DAPP_BIND}:{DAPP_PORT}/index.html")

MITMPROXY_PORT = env("MITMPROXY_PORT", "8081")
USE_PROXY = env("WALLETSCOPE_USE_PROXY", "0") == "1"

CAPTURES_DIR.mkdir(parents=True, exist_ok=True)
REPORTS_DIR.mkdir(parents=True, exist_ok=True)
