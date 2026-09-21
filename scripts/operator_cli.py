from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Ensure root directory is on sys.path
root_dir = Path(__file__).resolve().parent.parent
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

from src.operator_cli.client import OperatorCLI  # noqa: E402


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    parser = argparse.ArgumentParser(
        description="Crypto Quant Monitor — Operator AI Copilot Terminal Interface",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--db-path", default="data/market_contexts.db", help="Path to SQLite context database")
    parser.add_argument("--provider", default=None, help="Override AI provider (gemini, openai, ollama, mock)")

    subparsers = parser.add_subparsers(dest="command", help="Command to execute")

    # Status command
    status_parser = subparsers.add_parser("status", help="Inspect current market status for a symbol")
    status_parser.add_argument("--symbol", default="BTCUSDT", help="Symbol to inspect")
    status_parser.add_argument("--interval", default="1h", help="Timeframe interval")

    # Ask command
    ask_parser = subparsers.add_parser("ask", help="Ask a question to the AI Copilot")
    ask_parser.add_argument("query", help="Question or prompt for the Copilot")
    ask_parser.add_argument("--symbol", default="BTCUSDT", help="Symbol context")
    ask_parser.add_argument("--interval", default="1h", help="Timeframe interval")

    # Report command
    report_parser = subparsers.add_parser("report", help="Generate institutional market report")
    report_parser.add_argument("--symbol", default="BTCUSDT", help="Symbol context")
    report_parser.add_argument("--interval", default="1h", help="Timeframe interval")

    # REPL command
    repl_parser = subparsers.add_parser("repl", help="Start interactive conversational session")
    repl_parser.add_argument("--symbol", default="BTCUSDT", help="Initial symbol")
    repl_parser.add_argument("--interval", default="1h", help="Initial timeframe")

    args = parser.parse_args()

    cli = OperatorCLI(db_path=args.db_path, provider_type=args.provider)

    if args.command == "status":
        status = cli.get_status(symbol=args.symbol, timeframe=args.interval)
        print(cli.format_status_output(status))
        return 0
    elif args.command == "ask":
        print(cli.ask(query=args.query, symbol=args.symbol, timeframe=args.interval))
        return 0
    elif args.command == "report":
        print(cli.get_report(symbol=args.symbol, timeframe=args.interval))
        return 0
    elif args.command == "repl":
        cli.run_repl(default_symbol=args.symbol, default_timeframe=args.interval)
        return 0
    else:
        # Default to interactive REPL if no command specified
        cli.run_repl(default_symbol="BTCUSDT", default_timeframe="1h")
        return 0


if __name__ == "__main__":
    sys.exit(main())
