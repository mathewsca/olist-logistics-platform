import shutil
from pathlib import Path

import pytest

FIXTURE_LANDING_DIR = Path(__file__).parent / "fixtures" / "landing"


@pytest.fixture
def landing_dir(tmp_path: Path) -> Path:
    """A writable copy of the fixture CSVs, so tests can break files without side effects."""
    target = tmp_path / "landing"
    shutil.copytree(FIXTURE_LANDING_DIR, target)
    return target
