import pytest


@pytest.fixture(autouse=True)
def fresh_save(tmp_path, monkeypatch):
    """Every test starts with no saved progress and never touches the real save file."""
    monkeypatch.setenv("VOID_SIEGE_SAVE_DIR", str(tmp_path))
