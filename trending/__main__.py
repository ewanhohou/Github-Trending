"""
用法：
  python -m trending daily  [--no-notify]   產生今日報告、重建網頁、發通知
  python -m trending weekly [--no-notify]   產生本週精選
  python -m trending pick   [--no-notify]   替最新日報挑每日精選，產生說明圖與 Threads 貼文
                            [--redo]        重新挑選與產生（預設同一天沿用已選的）
                            [--render-only] 只依既有資料重畫說明圖
  python -m trending render                 只依 data/ 重建網頁
  python -m trending translate              替既有報告補上中文翻譯並重建網頁
  python -m trending notify daily|weekly|pick  傳送最新一份報告或精選的通知
"""
from __future__ import annotations

import argparse
import logging
import sys

from . import notify, pick, render, report, translate


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    parser = argparse.ArgumentParser(prog="trending")
    sub = parser.add_subparsers(dest="cmd", required=True)
    for kind in ("daily", "weekly"):
        p = sub.add_parser(kind)
        p.add_argument("--no-notify", action="store_true")
    p = sub.add_parser("pick")
    p.add_argument("--no-notify", action="store_true")
    p.add_argument("--redo", action="store_true")
    p.add_argument("--render-only", action="store_true")
    sub.add_parser("render")
    sub.add_parser("translate")
    p = sub.add_parser("notify")
    p.add_argument("kind", choices=["daily", "weekly", "pick"])
    args = parser.parse_args()

    if args.cmd in ("daily", "weekly"):
        result = report.build_daily() if args.cmd == "daily" else report.build_weekly()
        render.render_all()
        logging.info("built %s report %s with %d repos", args.cmd, result["id"], len(result["repos"]))
        if not args.no_notify:
            notify.send(result)
    elif args.cmd == "pick":
        result = pick.build(redo=args.redo, render_only=args.render_only)
        if not result:
            return 1
        render.render_all()
        logging.info("daily pick %s: %s", result["date"], result["full_name"])
        if not args.no_notify:
            notify.send_pick(result)
    elif args.cmd == "render":
        render.render_all()
    elif args.cmd == "translate":
        if not translate.enabled():
            logging.error("CLOUDFLARE_ACCOUNT_ID / CLOUDFLARE_API_TOKEN not set")
            return 1
        logging.info("translated %d repos", report.backfill_translations())
        render.render_all()
    elif args.cmd == "notify" and args.kind == "pick":
        latest = pick.latest_pick()
        if not latest:
            logging.error("no daily pick found")
            return 1
        notify.send_pick(latest)
    elif args.cmd == "notify":
        latest = report.latest_report(args.kind)
        if not latest:
            logging.error("no %s report found", args.kind)
            return 1
        notify.send(latest)
    return 0


if __name__ == "__main__":
    sys.exit(main())
