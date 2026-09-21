from __future__ import annotations

import io
import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

from config.settings import AppSettings
from scripts.entrypoint import check_health, main, run_api, run_ui


class TestConfigurationSettings:
    def test_settings_defaults(self):
        with patch.dict(os.environ, {}, clear=True):
            s = AppSettings.from_env()
            assert s.environment == "production"
            assert s.server.host == "0.0.0.0"
            assert s.server.port == 8000
            assert s.server.workers == 1
            assert s.server.reload is False
            assert s.server.log_level == "info"
            assert s.storage.data_dir.name == "data"
            assert "market_contexts.db" in str(s.storage.database_path)
            assert s.streaming.symbols == ("BTCUSDT",)
            assert s.streaming.timeframe == "1h"
            assert s.streaming.buffer_size == 500
            assert s.security.security_enabled is False
            assert s.security.rate_limit_enabled is True
            assert s.security.rate_limit_per_minute == 60
            assert s.observability.metrics_enabled is True
            assert s.observability.json_logging_enabled is True
            assert s.ai_provider.provider == "mock"
            assert s.ai_provider.gemini_model == "gemini-2.5-flash"
            assert s.ai_provider.openai_model == "gpt-4o-mini"
            assert s.ai_provider.ollama_url == "http://localhost:11434"
            assert s.ai_provider.timeout_seconds == 10.0
            assert s.ai_provider.max_retries == 2

    def test_settings_environment_overrides(self, tmp_path: Path):
        custom_data = tmp_path / "custom_data"
        env_vars = {
            "ENVIRONMENT": "staging",
            "SERVER_HOST": "127.0.0.1",
            "SERVER_PORT": "9000",
            "SERVER_WORKERS": "4",
            "SERVER_RELOAD": "true",
            "LOG_LEVEL": "debug",
            "DATA_DIR": str(custom_data),
            "DATABASE_PATH": str(custom_data / "test.db"),
            "PARQUET_DIR": str(custom_data / "parquet_cache"),
            "SYMBOL": "ETHUSDT, SOLUSDT",
            "TIMEFRAME": "15m",
            "STREAMING_BUFFER_SIZE": "1000",
            "OPERATOR_API_KEY": "supersecretkey",
            "OPERATOR_API_SECURITY_ENABLED": "true",
            "OPERATOR_API_RATE_LIMIT_ENABLED": "false",
            "OPERATOR_API_RATE_LIMIT_PER_MINUTE": "120",
            "OPERATOR_API_CORS_ORIGINS": "http://localhost:3000, https://myapp.com",
            "METRICS_ENABLED": "false",
            "JSON_LOGGING_ENABLED": "false",
            "AI_PROVIDER": "gemini",
            "GEMINI_API_KEY": "test_gemini_key",
            "GEMINI_MODEL": "gemini-pro",
            "OPENAI_API_KEY": "test_openai_key",
            "OPENAI_MODEL": "gpt-4o",
            "OLLAMA_URL": "http://custom:11434",
            "OLLAMA_MODEL": "mistral",
            "LLM_TIMEOUT_SECONDS": "20.0",
            "LLM_MAX_RETRIES": "4",
        }
        with patch.dict(os.environ, env_vars, clear=True):
            s = AppSettings.from_env()
            assert s.environment == "staging"
            assert s.server.host == "127.0.0.1"
            assert s.server.port == 9000
            assert s.server.workers == 4
            assert s.server.reload is True
            assert s.server.log_level == "debug"
            assert s.storage.data_dir == custom_data.resolve()
            assert s.storage.database_path == (custom_data / "test.db").resolve()
            assert s.storage.parquet_dir == (custom_data / "parquet_cache").resolve()
            assert s.streaming.symbols == ("ETHUSDT", "SOLUSDT")
            assert s.streaming.timeframe == "15m"
            assert s.streaming.buffer_size == 1000
            assert s.security.api_key == "supersecretkey"
            assert s.security.security_enabled is True
            assert s.security.rate_limit_enabled is False
            assert s.security.rate_limit_per_minute == 120
            assert s.security.cors_origins == ("http://localhost:3000", "https://myapp.com")
            assert s.observability.metrics_enabled is False
            assert s.observability.json_logging_enabled is False
            assert s.ai_provider.provider == "gemini"
            assert s.ai_provider.gemini_api_key == "test_gemini_key"
            assert s.ai_provider.gemini_model == "gemini-pro"
            assert s.ai_provider.openai_api_key == "test_openai_key"
            assert s.ai_provider.openai_model == "gpt-4o"
            assert s.ai_provider.ollama_url == "http://custom:11434"
            assert s.ai_provider.ollama_model == "mistral"
            assert s.ai_provider.timeout_seconds == 20.0
            assert s.ai_provider.max_retries == 4


    def test_ensure_directories(self, tmp_path: Path):
        custom_data = tmp_path / "deep" / "nested" / "data"
        env_vars = {
            "DATA_DIR": str(custom_data),
            "DATABASE_PATH": str(custom_data / "db" / "market.db"),
            "PARQUET_DIR": str(custom_data / "pq"),
        }
        with patch.dict(os.environ, env_vars, clear=True):
            s = AppSettings.from_env()
            assert not custom_data.exists()
            s.ensure_directories()
            assert custom_data.exists()
            assert (custom_data / "db").exists()
            assert (custom_data / "pq").exists()


class TestDeploymentArtifacts:
    def test_env_example_exists_and_content(self):
        env_file = Path(".env.example")
        assert env_file.exists()
        content = env_file.read_text(encoding="utf-8")
        assert "OPERATOR_API_KEY=" in content
        assert "DATABASE_PATH=" in content
        assert "SERVER_PORT=" in content
        assert "SYMBOL=" in content
        assert "TIMEFRAME=" in content
        assert "METRICS_ENABLED=" in content

    def test_dockerfile_specification(self):
        dockerfile = Path("Dockerfile")
        assert dockerfile.exists()
        content = dockerfile.read_text(encoding="utf-8")
        assert "FROM python:3.11-slim" in content
        assert "appuser" in content
        assert "EXPOSE 8000 8501" in content
        assert "ENTRYPOINT" in content
        assert "curl" in content

    def test_docker_compose_specification(self):
        compose_file = Path("docker-compose.yml")
        assert compose_file.exists()
        content = compose_file.read_text(encoding="utf-8")
        assert "operator-api:" in content
        assert "dashboard:" in content
        assert "quant_data:" in content
        assert "quant_logs:" in content
        assert "curl -f http://localhost:8000/health/ready" in content
        assert "8000" in content
        assert "8501" in content

    def test_dockerignore_specification(self):
        d_ignore = Path(".dockerignore")
        assert d_ignore.exists()
        content = d_ignore.read_text(encoding="utf-8")
        assert ".git/" in content
        assert ".venv/" in content
        assert "__pycache__/" in content
        assert "*.db" in content
        assert ".env" in content


class TestEntrypointCLI:
    @patch("uvicorn.run")
    def test_run_api(self, mock_uvicorn_run):
        code = run_api(host="127.0.0.1", port=8080, reload=True, workers=2)
        assert code == 0
        mock_uvicorn_run.assert_called_once_with(
            "src.operator_api.app:app",
            host="127.0.0.1",
            port=8080,
            reload=True,
            workers=2,
        )

    @patch("subprocess.call", return_value=0)
    def test_run_ui(self, mock_subproc):
        code = run_ui(port=8502, host="127.0.0.1")
        assert code == 0
        mock_subproc.assert_called_once()
        args = mock_subproc.call_args[0][0]
        assert "streamlit" in args
        assert "src/app.py" in args
        assert "8502" in args

    @patch("urllib.request.urlopen")
    def test_check_health_success(self, mock_urlopen):
        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.read.return_value = b'{"status": "READY"}'
        mock_urlopen.return_value.__enter__.return_value = mock_resp

        code = check_health("http://test/health/ready")
        assert code == 0

    @patch("urllib.request.urlopen")
    def test_check_health_unready(self, mock_urlopen):
        mock_resp = MagicMock()
        mock_resp.status = 503
        mock_resp.read.return_value = b'{"status": "NOT_READY"}'
        mock_urlopen.return_value.__enter__.return_value = mock_resp

        code = check_health("http://test/health/ready")
        assert code == 1

    @patch("urllib.request.urlopen")
    def test_check_health_http_error(self, mock_urlopen):
        import urllib.error
        fp = io.BytesIO(b'{"error": "down"}')
        mock_urlopen.side_effect = urllib.error.HTTPError(
            url="http://test", code=503, msg="Service Unavailable", hdrs={}, fp=fp
        )
        code = check_health("http://test/health/ready")
        assert code == 1

    @patch("urllib.request.urlopen", side_effect=ConnectionError("Connection refused"))
    def test_check_health_connection_failure(self, _mock_urlopen):
        code = check_health("http://test/health/ready")
        assert code == 2

    @patch("scripts.entrypoint.run_api", return_value=0)
    def test_main_api_command(self, mock_run_api):
        with patch.object(sys, "argv", ["entrypoint.py", "api", "--port", "8005"]):
            code = main()
            assert code == 0
            mock_run_api.assert_called_once()

    @patch("scripts.entrypoint.run_ui", return_value=0)
    def test_main_ui_command(self, mock_run_ui):
        with patch.object(sys, "argv", ["entrypoint.py", "ui", "--port", "8505"]):
            code = main()
            assert code == 0
            mock_run_ui.assert_called_once()

    @patch("scripts.entrypoint.check_health", return_value=0)
    def test_main_health_command(self, mock_check_health):
        with patch.object(sys, "argv", ["entrypoint.py", "health", "--url", "http://localhost:8000"]):
            code = main()
            assert code == 0
            mock_check_health.assert_called_once_with(url="http://localhost:8000")

    def test_main_no_args_shows_help(self):
        with patch.object(sys, "argv", ["entrypoint.py"]):
            code = main()
            assert code == 1

    @patch("uvicorn.run")
    def test_entrypoint_dunder_main(self, mock_uvicorn_run):
        import runpy

        with patch.object(sys, "argv", ["entrypoint.py", "api"]), patch.object(sys, "exit") as mock_exit:
            runpy.run_path("scripts/entrypoint.py", run_name="__main__")
            mock_exit.assert_called_once_with(0)
            mock_uvicorn_run.assert_called_once()
