import importlib

import pytest

import olist_platform

SUBPACKAGES = ["ingestion", "transform", "analytics", "features", "models", "monitoring", "api"]


def test_version_is_defined():
    assert isinstance(olist_platform.__version__, str)
    assert olist_platform.__version__.count(".") == 2


@pytest.mark.parametrize("name", SUBPACKAGES)
def test_subpackages_are_importable(name):
    module = importlib.import_module(f"olist_platform.{name}")
    assert module.__doc__
