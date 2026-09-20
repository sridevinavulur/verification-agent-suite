from __future__ import annotations

from pathlib import Path

import pytest

from protocol_contract_agent.io_utils import load_manifest, load_request

ROOT = Path(__file__).resolve().parents[1]
EXAMPLES = ROOT / "examples"


@pytest.fixture
def examples_dir() -> Path:
    return EXAMPLES


def _pair(name: str):
    req = load_request(EXAMPLES / "specs" / f"{name}.json")
    man = load_manifest(EXAMPLES / "rtl_manifests" / f"{name}.json")
    return req, man


@pytest.fixture
def valid_ready_pair():
    return _pair("valid_ready")


@pytest.fixture
def req_grant_pair():
    return _pair("req_grant")


@pytest.fixture
def fifo_pair():
    return _pair("fifo")


@pytest.fixture
def interrupt_pair():
    return _pair("interrupt")


@pytest.fixture
def credit_pair():
    return _pair("credit")


ALL_NAMES = ["valid_ready", "req_grant", "fifo", "interrupt", "credit"]
