from pathlib import Path

from streamlit.testing.v1 import AppTest


def test_dashboard_renders_four_working_tabs() -> None:
    project_root = Path(__file__).resolve().parents[1]
    app = AppTest.from_file(str(project_root / "app.py"))

    app.run(timeout=20)

    assert len(app.exception) == 0
    assert len(app.tabs) == 4
