import copy
import json
from pathlib import Path
from typing import Any

import pytest

EXAMPLES = Path(__file__).resolve().parent.parent / "examples"


def _load(name: str) -> dict[str, Any]:
    return json.loads((EXAMPLES / name).read_text())


@pytest.fixture
def incremental_request() -> dict[str, Any]:
    return copy.deepcopy(_load("etl_request_incremental.json"))


@pytest.fixture
def full_refresh_request() -> dict[str, Any]:
    return copy.deepcopy(_load("etl_request_full_refresh.json"))
