"""Typed access to mappings/controls.yaml — the single source of truth.

Everything that needs control metadata (adapters, router, matrix generator)
reads this one file. The moment a second copy of "what severity is CCM-07"
exists, the copies will disagree during an audit.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import yaml

CATALOG_PATH = Path(__file__).resolve().parents[1] / "mappings" / "controls.yaml"


@dataclass(frozen=True)
class Control:
    id: str
    name: str
    bucket: str  # machine | attestable | judgment
    csf: str
    nist_800_53: tuple[str, ...]
    severity: str  # ASFF label applied when the control fails
    method: str
    source: str
    status: str
    prowler_checks: tuple[str, ...] = ()


@lru_cache(maxsize=1)
def load_catalog() -> dict[str, Control]:
    raw = yaml.safe_load(CATALOG_PATH.read_text(encoding="utf-8"))
    catalog = {}
    for entry in raw["controls"]:
        control = Control(
            id=entry["id"],
            name=entry["name"],
            bucket=entry["bucket"],
            csf=entry["csf"],
            nist_800_53=tuple(entry["nist_800_53"]),
            severity=entry["severity"],
            method=entry["method"],
            source=entry["source"],
            status=entry["status"],
            prowler_checks=tuple(entry.get("prowler_checks", [])),
        )
        catalog[control.id] = control
    return catalog


@lru_cache(maxsize=1)
def by_prowler_check() -> dict[str, Control]:
    """Reverse index: Prowler event_code -> control."""
    return {
        check: control
        for control in load_catalog().values()
        for check in control.prowler_checks
    }
