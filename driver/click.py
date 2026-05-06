"""
JS-injection helpers run via CDP `Runtime.evaluate` on a wallet extension
page. Each helper sends a small IIFE and prints the response. They are
intended to be called from set.py after the caller has obtained a CDP
session_id for the target popup.
"""

import json


_id_counter = 0


def next_id():
    global _id_counter
    _id_counter += 1
    return _id_counter


def _eval(ws, session_id, expression):
    ws.send(json.dumps({
        "sessionId": session_id,
        "id": next_id(),
        "method": "Runtime.evaluate",
        "params": {"expression": expression, "returnByValue": True},
    }))
    print(json.loads(ws.recv()))


def click_Normal(ws, session_id):
    _eval(ws, session_id, """
    (() => {
      const btns = [...document.querySelectorAll('button')];
      const normal = btns.find(b => b.innerText.includes('Normal'));
      if (normal) { normal.click(); return 'clicked'; }
      return 'not found';
    })()
    """)


def click_Custom(ws, session_id):
    _eval(ws, session_id, """
    (() => {
      const tab = [...document.querySelectorAll('button, div')]
        .find(el => el.textContent.trim() === 'Custom');
      if (!tab) return 'custom not found';
      tab.click();
      return 'clicked custom';
    })()
    """)


def Change_max_base_fee(ws, session_id):
    _eval(ws, session_id, """
    (() => {
      const inputs = document.querySelectorAll('input');
      for (const i of inputs) {
        const label = i.previousElementSibling?.textContent || '';
        if (label.includes('Max base fee')) {
          i.focus();
          i.value = '0.2';
          i.dispatchEvent(new Event('input', { bubbles: true }));
          i.dispatchEvent(new Event('change', { bubbles: true }));
          return 'set to 0.2';
        }
      }
      return 'not found';
    })()
    """)


def click_Save(ws, session_id):
    _eval(ws, session_id, """
    (() => {
      const btn = [...document.querySelectorAll('button')]
        .find(el => el.textContent.trim() === 'Save');
      if (!btn) return 'save not found';
      btn.click();
      return 'clicked save';
    })()
    """)


def click_unlock(ws, session_id):
    _eval(ws, session_id, """
    (() => {
      const btns = [...document.querySelectorAll('button')];
      const unlockBtn = btns.find(b => b.innerText.trim() === 'Unlock');
      if (unlockBtn) { unlockBtn.click(); return 'clicked'; }
      return 'not found';
    })()
    """)


def click_ignore_and_proceed(ws, session_id):
    _eval(ws, session_id, """
    (() => {
      const el = [...document.querySelectorAll('div.css-g5y9jx.r-1loqt21.r-1otgn73')]
        .find(e => e.innerText && e.innerText.trim() === 'Ignore and Proceed');
      if (!el) return 'not found';
      el.scrollIntoView({behavior:'smooth', block:'center'});
      const rect = el.getBoundingClientRect();
      const evt = new MouseEvent('click', {
        bubbles: true, cancelable: true,
        clientX: rect.left + rect.width / 2,
        clientY: rect.top + rect.height / 2,
      });
      el.dispatchEvent(evt);
      return 'dom click dispatched';
    })()
    """)


def click_connect_Nufi(ws, session_id):
    _eval(ws, session_id, """
    (() => {
      const btns = [...document.querySelectorAll('button')];
      const connectBtn = btns.find(b => b.innerText.trim() === 'Connect');
      if (connectBtn) { connectBtn.click(); return 'clicked'; }
      return 'not found';
    })()
    """)
