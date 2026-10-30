import importlib

import pytest

pytestmark = pytest.mark.week1


def test_package_imports():
    assert importlib.import_module("analytics_agent")
    assert importlib.import_module("analytics_agent.agents.graph")
