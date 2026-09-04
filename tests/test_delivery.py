import tomllib
from pathlib import Path

import yaml


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_project_exposes_repopilot_commands() -> None:
    payload = tomllib.loads(
        (PROJECT_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    )

    assert payload["project"]["name"] == "repopilot-agent"
    assert payload["project"]["scripts"] == {
        "repopilot": "repopilot.main:main",
        "repopilot-eval": "repopilot.eval_cli:main",
        "repopilot-benchmark": "repopilot.benchmark_cli:main",
        "repopilot-compare": "repopilot.benchmark_compare_cli:main",
    }


def test_docker_delivery_uses_non_root_user_and_healthcheck() -> None:
    dockerfile = (PROJECT_ROOT / "Dockerfile").read_text(encoding="utf-8")
    compose = yaml.safe_load(
        (PROJECT_ROOT / "compose.yaml").read_text(encoding="utf-8")
    )

    assert "ghcr.io/astral-sh/uv:0.11.16" in dockerfile
    assert "USER repopilot" in dockerfile
    assert "HEALTHCHECK" in dockerfile
    assert '"streamlit", "run", "app.py"' in dockerfile
    assert "OPENAI_API_KEY=" not in dockerfile
    assert set(compose["services"]) == {"dashboard", "agent"}
    assert compose["services"]["dashboard"]["ports"] == ["8501:8501"]
