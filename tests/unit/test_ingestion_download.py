import shutil
from pathlib import Path

import pytest

from olist_platform.ingestion.download import download_dataset, missing_files
from olist_platform.ingestion.sources import KAGGLE_DATASET, SOURCES
from tests.conftest import FIXTURE_LANDING_DIR


class FakeKaggle:
    """Stands in for KaggleApi: 'downloads' by copying the fixture CSVs."""

    def __init__(self, files_to_write=None, fail_after_writing=False):
        self.calls = []
        self.files_to_write = files_to_write
        self.fail_after_writing = fail_after_writing

    def dataset_download_files(self, dataset, path=None, force=False, quiet=True, unzip=False):
        self.calls.append({"dataset": dataset, "force": force, "unzip": unzip})
        for source in SOURCES:
            if self.files_to_write is None or source.file_name in self.files_to_write:
                shutil.copy(FIXTURE_LANDING_DIR / source.file_name, Path(path) / source.file_name)
        if self.fail_after_writing:
            raise ConnectionError("connection dropped mid-download")


def test_skips_download_when_all_files_exist(landing_dir: Path):
    client = FakeKaggle()
    assert download_dataset(landing_dir, client_factory=lambda: client) is False
    assert client.calls == []


def test_downloads_when_a_file_is_missing(landing_dir: Path):
    (landing_dir / SOURCES[0].file_name).unlink()
    client = FakeKaggle()

    assert download_dataset(landing_dir, client_factory=lambda: client) is True
    assert client.calls == [{"dataset": KAGGLE_DATASET, "force": True, "unzip": True}]
    assert missing_files(landing_dir) == []
    assert not (landing_dir / ".download").exists()


def test_downloads_into_new_directory(tmp_path: Path):
    target = tmp_path / "does" / "not" / "exist"
    assert download_dataset(target, client_factory=FakeKaggle) is True
    assert missing_files(target) == []


def test_force_downloads_even_when_complete(landing_dir: Path):
    client = FakeKaggle()
    assert download_dataset(landing_dir, client_factory=lambda: client, force=True) is True
    assert len(client.calls) == 1


def test_fails_when_download_does_not_produce_every_file(tmp_path: Path):
    client = FakeKaggle(files_to_write={SOURCES[0].file_name})
    with pytest.raises(FileNotFoundError, match="files are missing"):
        download_dataset(tmp_path, client_factory=lambda: client)


def test_interrupted_download_leaves_landing_dir_untouched(tmp_path: Path):
    client = FakeKaggle(fail_after_writing=True)
    with pytest.raises(ConnectionError):
        download_dataset(tmp_path, client_factory=lambda: client)
    assert sorted(p.name for p in tmp_path.iterdir()) == []
