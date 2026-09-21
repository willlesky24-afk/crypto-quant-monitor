from __future__ import annotations

import argparse
import os
import subprocess
import sys


def run_api(host: str = "0.0.0.0", port: int = 8000, reload: bool = False, workers: int = 1) -> int:
    """Launch the FastAPI Operator Gateway via Uvicorn."""
    import uvicorn

    print(f"Starting Crypto Quant Operator API Gateway on {host}:{port} (workers={workers})...")
    uvicorn.run(
        "src.operator_api.app:app",
        host=host,
        port=port,
        reload=reload,
        workers=workers,
    )
    return 0


def run_ui(port: int = 8501, host: str = "0.0.0.0") -> int:
    """Launch the Streamlit Dashboard."""
    print(f"Starting Crypto Quant Streamlit Dashboard on {host}:{port}...")
    cmd = [
        sys.executable,
        "-m",
        "streamlit",
        "run",
        "src/app.py",
        "--server.address",
        host,
        "--server.port",
        str(port),
        "--server.headless",
        "true",
    ]
    return subprocess.call(cmd)


def run_worker(
    symbols: list[str] | None = None,
    interval: str = "1h",
    db_path: str = "data/market_contexts.db",
    dry_run: bool = False,
    bootstrap: bool = True,
) -> int:
    """Launch the Live Market Worker daemon."""
    from src.streaming.live_worker import LiveMarketWorker

    sym_list = symbols or ["BTCUSDT"]
    print(f"Starting Live Market Worker for {sym_list} ({interval}) -> {db_path} (dry_run={dry_run})...")
    worker = LiveMarketWorker(
        symbols=sym_list,
        interval=interval,
        db_path=db_path,
        dry_run=dry_run,
    )
    worker.run_forever(bootstrap=bootstrap)
    return 0


def check_health(url: str = "http://localhost:8000/health/ready") -> int:

    """Check readiness status of the Operator API Gateway via HTTP GET."""
    import urllib.error
    import urllib.request

    print(f"Checking readiness probe at {url}...")
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "CryptoQuant-CLI/1.0"})
        with urllib.request.urlopen(req, timeout=5.0) as response:
            status = response.status
            body = response.read().decode("utf-8")
            if status == 200:
                print(f"[SUCCESS] Service is READY (HTTP {status}):\n{body}")
                return 0
            else:
                print(f"[UNREADY] Service returned HTTP {status}:\n{body}")
                return 1
    except urllib.error.HTTPError as err:
        body = err.read().decode("utf-8") if err.fp else str(err)
        print(f"[ERROR] Service returned HTTP {err.code}: {body}")
        return 1
    except Exception as exc:
        print(f"[FAILURE] Unable to connect to {url}: {exc}")
        return 2


def main() -> int:
    """CLI Entrypoint parser for production service orchestration."""
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    parser = argparse.ArgumentParser(
        description="Crypto Quant Monitor — Production Service Entrypoint",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )

    subparsers = parser.add_subparsers(dest="command", help="Operational command to execute")

    # API subcommand
    api_parser = subparsers.add_parser("api", help="Start the FastAPI Operator Gateway")
    api_parser.add_argument("--host", default=os.getenv("SERVER_HOST", "0.0.0.0"), help="Bind host")
    api_parser.add_argument("--port", type=int, default=int(os.getenv("SERVER_PORT", "8000")), help="Bind port")
    api_parser.add_argument("--workers", type=int, default=int(os.getenv("SERVER_WORKERS", "1")), help="Workers")
    api_parser.add_argument(
        "--reload",
        action="store_true",
        default=os.getenv("SERVER_RELOAD", "false").lower() in ("true", "1", "yes"),
        help="Enable auto-reload",
    )

    # UI subcommand
    ui_parser = subparsers.add_parser("ui", help="Start the Streamlit UI dashboard")
    ui_parser.add_argument("--port", type=int, default=8501, help="Dashboard port")
    ui_parser.add_argument("--host", default="0.0.0.0", help="Dashboard host")

    # Worker subcommand
    worker_parser = subparsers.add_parser("worker", aliases=["stream"], help="Start the Live Market Worker daemon")
    worker_parser.add_argument(
        "--symbols",
        default=os.getenv("SYMBOLS", "BTCUSDT"),
        help="Comma-separated list of symbols (e.g. BTCUSDT,ETHUSDT)",
    )
    worker_parser.add_argument(
        "--interval",
        default=os.getenv("TIMEFRAME", "1h"),
        help="Candle timeframe interval (e.g. 1h, 15m)",
    )
    worker_parser.add_argument(
        "--db-path",
        default=os.getenv("DATABASE_PATH", "data/market_contexts.db"),
        help="SQLite context database path",
    )
    worker_parser.add_argument(
        "--dry-run",
        action="store_true",
        default=os.getenv("WORKER_DRY_RUN", "false").lower() in ("true", "1", "yes"),
        help="Enable dry-run mode (no live WebSocket connection)",
    )
    worker_parser.add_argument(
        "--no-bootstrap",
        action="store_true",
        help="Disable historical warm-up candle prefetching",
    )

    # Health subcommand
    health_parser = subparsers.add_parser("health", help="Check readiness status of the running service")
    health_parser.add_argument(
        "--url",
        default=os.getenv("HEALTH_CHECK_URL", "http://localhost:8000/health/ready"),
        help="Healthcheck URL",
    )

    # CLI subcommand
    cli_parser = subparsers.add_parser("cli", help="Start the Operator AI Copilot CLI")
    cli_parser.add_argument("--symbol", default="BTCUSDT", help="Initial symbol")
    cli_parser.add_argument("--interval", default="1h", help="Initial timeframe")
    cli_parser.add_argument("--query", default=None, help="One-shot question for Copilot")
    cli_parser.add_argument("--report", action="store_true", help="Generate market report")
    cli_parser.add_argument("--status", action="store_true", help="Display market status")

    args = parser.parse_args()

    if args.command == "api":
        return run_api(host=args.host, port=args.port, reload=args.reload, workers=args.workers)
    elif args.command == "ui":
        return run_ui(port=args.port, host=args.host)
    elif args.command in ("worker", "stream"):
        syms = [s.strip().upper() for s in args.symbols.split(",") if s.strip()]
        return run_worker(
            symbols=syms,
            interval=args.interval,
            db_path=args.db_path,
            dry_run=args.dry_run,
            bootstrap=not args.no_bootstrap,
        )
    elif args.command == "cli":
        from src.operator_cli.client import OperatorCLI

        op_cli = OperatorCLI()
        if args.status:
            print(op_cli.format_status_output(op_cli.get_status(args.symbol, args.interval)))
            return 0
        elif args.report:
            print(op_cli.get_report(args.symbol, args.interval))
            return 0
        elif args.query:
            print(op_cli.ask(args.query, args.symbol, args.interval))
            return 0
        else:
            op_cli.run_repl(default_symbol=args.symbol, default_timeframe=args.interval)
            return 0
    elif args.command == "health":
        return check_health(url=args.url)
    else:
        parser.print_help()
        return 1


if __name__ == "__main__":
    sys.exit(main())


