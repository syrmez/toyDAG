from __future__ import annotations

import time
from typing import Any

import requests


def get_json(url: str, params: dict[str, Any] | None = None) -> Any:
    r = requests.get(url, params=params, timeout=30, headers={"User-Agent": "toyDAG/0.1"})
    r.raise_for_status()
    time.sleep(0.2)  # ponytail: blunt public-API rate limit; replace with per-exchange limits if needed.
    return r.json()
