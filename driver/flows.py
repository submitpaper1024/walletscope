"""
Per-wallet driver flows. Each *_wallet() function drives one wallet
extension through a connect → claim → page-source-capture cycle.

Use the orchestrator (`python -m walletscope drive <wallet> <scenario>`)
or import a flow function directly.
"""

import time

import pyautogui
from selenium.webdriver.common.by import By

from .. import scenarios
from .chrome import (
    All_The_Way_To_8080,
    Check_Connection,
    Click_Claim,
    Click_Claim_Meta,
    Click_Conn_Meta,
    Dapp_running,
    Dapp_running_Blocknumber,
    SetUpDriver,
    backpack_warning,
    csp,
    csp_OK,
    csp_oneKey,
    nufi_connect,
    oneKey,
    pswdInput,
    selector,
    serve_scenario,
)


# ---------------------------------------------------- legacy single-wallet flows

def OneKey():
    Dapp_running()
    driver = SetUpDriver()
    driver.get("http://mylocal.test:8080/")

    connect_button = driver.find_element(By.XPATH, "//button[contains(text(), 'Connect Wallet')]")
    connect_button.click()
    time.sleep(2)

    connect_button2 = driver.find_element(By.XPATH, "//button[contains(text(), 'Call claim()')]")
    connect_button2.click()

    time.sleep(4)
    oneKey()
    time.sleep(1)
    pswdInput()
    time.sleep(2)

    csp_oneKey()

    handles = driver.window_handles
    print(handles)
    if len(handles) > 1:
        driver.switch_to.window(handles[1])
        print("Popup URL:", driver.current_url)
        print("Popup title:", driver.title)

    input("Press Enter to quit and close the browser...")
    driver.quit()


def Meta():
    driver = All_The_Way_To_8080()
    time.sleep(2)
    if not Check_Connection(driver):
        Click_Conn_Meta(driver)
    Click_Claim_Meta(driver)
    time.sleep(2)
    csp("Meta_page.txt")


def Backpack():
    Dapp_running()
    driver = All_The_Way_To_8080()
    time.sleep(2)
    Click_Claim(driver)
    time.sleep(2)
    pswdInput()
    backpack_warning()


def nufi_first_connect():
    Dapp_running()
    All_The_Way_To_8080()
    time.sleep(2)
    pswdInput()
    nufi_connect()


def nufi():
    Dapp_running()
    driver = All_The_Way_To_8080()
    time.sleep(2)
    pswdInput()
    nufi_connect()
    Click_Claim(driver)  # mouse may still be on the address bar; click twice to be sure
    Click_Claim(driver)
    time.sleep(2)
    pswdInput()
    csp("Nufi_pagesource.txt")


def CTRL():
    Dapp_running()
    driver = All_The_Way_To_8080()
    time.sleep(2)
    Click_Claim(driver)
    time.sleep(2)
    pswdInput()
    csp("CTRL_pagesource.txt")


def rabby():
    driver = All_The_Way_To_8080()
    time.sleep(2)
    pyautogui.press("enter")
    time.sleep(1)
    connect_button = driver.find_element(By.XPATH, "//button[contains(text(), 'Connect Wallet')]")
    connect_button.click()
    time.sleep(1)
    pswdInput()
    time.sleep(1)
    Click_Claim(driver)
    time.sleep(2)
    csp("rabby_pagesource.txt")


# --------------------------------------------------- multi-wallet selector flows

def nufi_wallet():
    driver = All_The_Way_To_8080()
    time.sleep(3)
    selector(driver, "NUFI")
    time.sleep(2)
    pswdInput()
    time.sleep(1)
    nufi_connect()
    Click_Claim(driver)
    time.sleep(2)
    pswdInput()
    csp("Nufi_pagesource.txt")


def backpack_wallet():
    driver = All_The_Way_To_8080()
    time.sleep(3)
    selector(driver, "Backpack")
    time.sleep(1)
    Click_Claim(driver)
    time.sleep(2)
    pswdInput()
    backpack_warning()


def Pontem_Wallet():
    driver = All_The_Way_To_8080()
    time.sleep(3)
    selector(driver, "Pontem Wallet")
    time.sleep(1)
    Click_Claim(driver)
    time.sleep(1)
    csp("Pontem_pagesource.txt")


def MetaMask_wallet():
    driver = All_The_Way_To_8080()
    time.sleep(3)
    selector(driver, "MetaMask")
    time.sleep(1)
    Click_Claim(driver)
    time.sleep(2)
    pswdInput()
    time.sleep(1)
    csp("MetaMask_pagesource.txt")


def TokenPocket_wallet():
    driver = All_The_Way_To_8080()
    time.sleep(3)
    selector(driver, "TokenPocket")
    time.sleep(1)
    pswdInput()
    time.sleep(1)
    Click_Claim(driver)
    time.sleep(2)
    csp("TokenPocket_pagesource.txt")


def Zerion_wallet():
    driver = All_The_Way_To_8080()
    time.sleep(3)
    selector(driver, "Zerion")
    time.sleep(1)
    pswdInput()
    time.sleep(1)
    Click_Claim(driver)
    time.sleep(2)
    csp("Zerion_pagesource.txt")


def oneKey_wallet():
    driver = All_The_Way_To_8080()
    time.sleep(3)
    selector(driver, "OneKey")
    time.sleep(1)
    Click_Claim(driver)
    time.sleep(2)
    csp_OK()
    time.sleep(1)
    pswdInput()
    time.sleep(1)
    csp("OneKey_pagesource.txt")


def Phantom_Wallet():
    driver = All_The_Way_To_8080()
    time.sleep(3)
    selector(driver, "Phantom")
    time.sleep(1)
    Click_Claim(driver)
    time.sleep(1)
    pswdInput()
    time.sleep(1)
    csp("Phantom_pagesource.txt")


def core_wallet():
    driver = All_The_Way_To_8080()
    time.sleep(3)
    selector(driver, "Core")
    time.sleep(1)
    pswdInput()
    time.sleep(2)
    pyautogui.press("tab")
    pyautogui.press("tab")
    pyautogui.press("enter")
    time.sleep(1)
    Click_Claim(driver)
    time.sleep(1)
    pyautogui.press("tab")
    pyautogui.press("tab")
    pyautogui.press("tab")
    pyautogui.press("enter")
    csp("Core_pagesource.txt")


def rabby_wallet():
    driver = All_The_Way_To_8080()
    time.sleep(3)
    selector(driver, "Rabby Wallet")
    time.sleep(1)
    pswdInput()
    time.sleep(1)
    Click_Claim(driver)
    time.sleep(1)
    csp("Rabby Wallet_pagesource.txt")


# Registry consumed by walletscope/__main__.py and the orchestrator.
WALLET_FLOWS = {
    "backpack": backpack_wallet,
    "core": core_wallet,
    "ctrl": CTRL,
    "metamask": MetaMask_wallet,
    "nest": nufi_wallet,
    "nufi": nufi_wallet,
    "onekey": oneKey_wallet,
    "phantom": Phantom_Wallet,
    "pontem": Pontem_Wallet,
    "rabby": rabby_wallet,
    "tokenpocket": TokenPocket_wallet,
    "zerion": Zerion_wallet,
}


def run_flow(wallet: str):
    flow = WALLET_FLOWS.get(wallet.lower())
    if flow is None:
        raise KeyError(
            f"unknown wallet {wallet!r}; known: {sorted(WALLET_FLOWS)}"
        )
    flow()
