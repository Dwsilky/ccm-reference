"""The finding bus — one interface, two implementations (ADR-001).

Everything upstream emits validated ASFF dicts; everything downstream
(router/) consumes from a Bus. LocalBus and SecurityHubBus are
interchangeable above this seam, which is what keeps development free and
the demo runnable without AWS credentials.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Protocol

from normalizer.asff import validate

# BatchImportFindings accepts at most 100 findings per call.
IMPORT_BATCH = 100


class Bus(Protocol):
    def publish(self, findings: list[dict]) -> int: ...


class LocalBus:
    """Append findings to a JSONL file — the dev/demo Security Hub.

    JSONL rather than one growing JSON array: appends are atomic-ish, partial
    writes corrupt one line instead of the whole store, and the router can
    stream it without loading history into memory.
    """

    def __init__(self, path: str | Path = "evidence/findings.jsonl"):
        self.path = Path(path)

    def publish(self, findings: list[dict]) -> int:
        for finding in findings:
            validate(finding)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8", newline="\n") as fh:
            for finding in findings:
                fh.write(json.dumps(finding, separators=(",", ":")) + "\n")
        return len(findings)

    def read_all(self) -> list[dict]:
        if not self.path.exists():
            return []
        with self.path.open(encoding="utf-8") as fh:
            return [json.loads(line) for line in fh if line.strip()]


class SecurityHubBus:
    """Publish to real Security Hub via BatchImportFindings.

    The API reports partial failure (FailedCount + per-finding reasons) with
    a 200 — checking only the status code would silently drop findings, so
    any FailedFindings raise.
    """

    def __init__(self, session):
        self.client = session.client("securityhub")

    def publish(self, findings: list[dict]) -> int:
        for finding in findings:
            validate(finding)

        imported = 0
        for i in range(0, len(findings), IMPORT_BATCH):
            batch = findings[i : i + IMPORT_BATCH]
            response = self.client.batch_import_findings(Findings=batch)
            if response.get("FailedCount"):
                failed = response.get("FailedFindings", [])
                raise RuntimeError(
                    f"Security Hub rejected {response['FailedCount']} finding(s): "
                    + "; ".join(f"{f.get('Id')}: {f.get('ErrorMessage')}" for f in failed[:5])
                )
            imported += response.get("SuccessCount", len(batch))
        return imported
