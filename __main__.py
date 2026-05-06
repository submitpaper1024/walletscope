"""
WalletScope CLI.

Subcommands:

  drive WALLET SCENARIO   run an end-to-end driver flow (start DApp,
                          notify proxy, run wallet UI flow)

  serve SCENARIO          just start the DApp http.server for a scenario

  notify SCENARIO         tell the running mitm addon to switch its tag

  analyze WALLET          run the proxy analyzer on walletscope/data/captures/<wallet>__*

  scenarios               list the scenario → DApp mapping

  addon                   print the mitmdump command to start capturing
"""

from __future__ import annotations

import argparse
import sys

from . import config, scenarios


def cmd_drive(args):
    from . import orchestrator
    orchestrator.run(
        wallet=args.wallet,
        scenario=args.scenario,
        skip_serve=args.skip_serve,
        skip_notify=args.skip_notify,
    )


def cmd_serve(args):
    from .driver import chrome
    chrome.serve_scenario(args.scenario)
    print("server running in foreground; Ctrl-C to stop")
    try:
        import signal
        signal.pause()
    except (AttributeError, KeyboardInterrupt):
        pass


def cmd_notify(args):
    body = scenarios.notify_proxy(args.scenario)
    if body is None:
        sys.exit(1)
    print(body.strip())


def cmd_analyze(args):
    from .proxy import analyzer
    captures = list(config.CAPTURES_DIR.glob(f"{args.wallet}*.jsonl"))
    if not captures:
        print(f"no captures matching {args.wallet}*.jsonl in {config.CAPTURES_DIR}")
        sys.exit(1)
    out = config.REPORTS_DIR / f"{args.wallet}_report.html"
    analyzer.run(
        capture_targets=[str(p) for p in captures],
        wallet_override=args.wallet,
        output_path=str(out),
        use_claude=not args.no_claude,
        probe_keys=args.probe_keys,
    )


def cmd_scenarios(_args):
    print("Known scenarios:")
    print(scenarios.scenario_summary())


def cmd_addon(_args):
    addon = config.PACKAGE_ROOT / "proxy" / "addon.py"
    print(
        "WALLETSCOPE_LOG_DIR={log} WALLETSCOPE_WALLET=<wallet> "
        "WALLETSCOPE_SCENARIO=<scenario> mitmdump -p {port} -s {addon}".format(
            log=config.CAPTURES_DIR,
            port=config.MITMPROXY_PORT,
            addon=addon,
        )
    )


def main(argv=None):
    p = argparse.ArgumentParser(prog="walletscope")
    sub = p.add_subparsers(dest="cmd", required=True)

    pd = sub.add_parser("drive", help="run end-to-end driver flow")
    pd.add_argument("wallet")
    pd.add_argument("scenario")
    pd.add_argument("--skip-serve", action="store_true",
                    help="don't start the DApp server (use if it's already up)")
    pd.add_argument("--skip-notify", action="store_true",
                    help="don't poke the proxy sentinel URL")
    pd.set_defaults(func=cmd_drive)

    ps = sub.add_parser("serve", help="serve a scenario's DApp")
    ps.add_argument("scenario")
    ps.set_defaults(func=cmd_serve)

    pn = sub.add_parser("notify", help="switch proxy scenario tag")
    pn.add_argument("scenario")
    pn.set_defaults(func=cmd_notify)

    pa = sub.add_parser("analyze", help="run proxy analyzer on capture(s)")
    pa.add_argument("wallet")
    pa.add_argument("--no-claude", action="store_true")
    pa.add_argument("--probe-keys", action="store_true")
    pa.set_defaults(func=cmd_analyze)

    psc = sub.add_parser("scenarios", help="list scenario → DApp mapping")
    psc.set_defaults(func=cmd_scenarios)

    pad = sub.add_parser("addon", help="print mitmdump command for the addon")
    pad.set_defaults(func=cmd_addon)

    args = p.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
