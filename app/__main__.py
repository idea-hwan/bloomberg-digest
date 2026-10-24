from __future__ import annotations

import argparse
import sys

from app.errors import ConfigError
from app.ingest import ingest, reextract_all
from app.paths import ROOT
from app.store import status_rows


def _print_summary(summary: list[dict], dry_run: bool) -> int:
    failed = False
    for row in summary:
        print(
            f"{row['series']}  찾음 {row['found']}  저장 {row['saved']}  "
            f"추출 {row['extracted']}  건너뜀 {row['skipped']}"
        )
        if dry_run:
            print(f"  검색  {row['query']}")
            for line in row["preview"]:
                print(f"  {line}")
            if not row["preview"] and not row["errors"]:
                print("  해당하는 메일이 없습니다.")
        for error in row["errors"]:
            failed = True
            print(f"  오류  {error}", file=sys.stderr)
    return 1 if failed else 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="bloomberg-digest", description="블룸버그 레터를 JSON으로 저장합니다.")
    sub = parser.add_subparsers(dest="cmd", required=True)

    sub.add_parser("auth", help="Gmail 읽기 권한으로 로그인합니다.")
    sub.add_parser("renew", help="지금 다시 로그인해서 7일을 이 시점부터 시작합니다.")

    ingest_parser = sub.add_parser("ingest", help="최근 메일을 받아 원문과 추출본을 저장합니다.")
    ingest_parser.add_argument("--days", type=int, default=3, help="최근 N일. 기본 3.")
    ingest_parser.add_argument("--series", action="append", dest="series_ids", help="이 시리즈만. 여러 번 쓸 수 있습니다.")
    ingest_parser.add_argument("--dry-run", action="store_true", help="저장하지 않고 제목만 보여 줍니다.")
    ingest_parser.add_argument("--reextract", action="store_true", help="이미 받은 원문으로 추출본을 다시 만듭니다.")

    sub.add_parser("extract", help="저장된 원문 전체로 추출본을 다시 만듭니다.")
    sub.add_parser("status", help="시리즈별 저장 건수를 보여 줍니다.")

    args = parser.parse_args(argv)
    try:
        if args.cmd in {"auth", "renew"}:
            from app.gmail import authenticate

            force = args.cmd == "renew"
            if force:
                print("브라우저에서 로그인하면 지금부터 7일이 다시 시작됩니다.")
            authenticate(force=force)
            if force:
                print("로그인했습니다. 지금부터 7일간 받을 수 있습니다.")
            else:
                print("Gmail 읽기 권한이 준비되었습니다. token.json에 저장했습니다.")
            return 0
        if args.cmd == "status":
            rows = status_rows(ROOT)
            if not rows:
                print("아직 저장된 메일이 없습니다.")
                return 0
            for row in rows:
                print(f"{row['series']}  {row['count']}통  {row['first']} ~ {row['last']}")
            return 0
        if args.cmd == "extract":
            count = reextract_all(ROOT)
            print(f"추출본 {count}건을 다시 썼습니다.")
            return 0
        summary = ingest(
            days=args.days,
            dry_run=args.dry_run,
            reextract=args.reextract,
            series_ids=args.series_ids,
        )
    except ConfigError as exc:
        print(exc, file=sys.stderr)
        return 1
    return _print_summary(summary, args.dry_run)


if __name__ == "__main__":
    raise SystemExit(main())
