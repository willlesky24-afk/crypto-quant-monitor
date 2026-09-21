from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Ensure root directory is on sys.path
root_dir = Path(__file__).resolve().parent.parent
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

from src.streaming.market_validator import RealMarketValidator  # noqa: E402


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    parser = argparse.ArgumentParser(
        description="Crypto Quant Monitor — Production Live Deployment & Market Validator",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--symbol", default="BTCUSDT", help="Cryptocurrency symbol to validate")
    parser.add_argument("--interval", default="1h", help="Candle timeframe interval")
    parser.add_argument("--db-path", default=":memory:", help="SQLite test database path")
    parser.add_argument("--dry-run", action="store_true", help="Run in dry-run mode without external exchange ping")
    parser.add_argument("--json", action="store_true", help="Output report in JSON format")

    args = parser.parse_args()

    validator = RealMarketValidator(
        symbol=args.symbol,
        interval=args.interval,
        db_path=args.db_path,
    )

    if not args.json:
        print("\n=======================================================")
        print("🚀 Crypto Quant Monitor — Live Market Validator")
        print("=======================================================")
        print(f"Symbol:   {args.symbol}")
        print(f"Interval: {args.interval}")
        print(f"Dry Run:  {args.dry_run}")
        print(f"Database: {args.db_path}\n")

    report = validator.run_full_validation(dry_run=args.dry_run)

    if args.json:
        print(json.dumps(report.to_dict(), indent=2))
        return 0 if report.overall_status in ("PASS", "WARN") else 1

    for check in report.checks:
        icon = "✅" if check.status == "PASS" else ("⚠️" if check.status == "WARN" else "❌")
        latency_str = f"({check.latency_ms:.1f}ms)" if check.latency_ms > 0 else ""
        print(f"[{icon} {check.status:4s}] {check.name:<28s} {latency_str:<10s} {check.message}")

    print("\n=======================================================")
    print(f"OVERALL STATUS: {report.overall_status} — {report.summary}")
    print("=======================================================\n")

    return 0 if report.overall_status in ("PASS", "WARN") else 1


if __name__ == "__main__":
    sys.exit(main())
