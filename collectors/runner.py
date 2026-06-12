"""Shared CLI plumbing: collector result -> normalizer -> local bus.

Collectors stay pure (return the contract dict); this is the only place a
collector touches the pipeline. `python -m collectors.<name>` from the repo
root runs one collection and lands the finding on the LocalBus.
"""

from __future__ import annotations

import os

from normalizer.adapters import from_collector
from normalizer.bus import LocalBus

# The local pipeline has no AWS account; deploy/ sets CCM_ACCOUNT_ID for real
# runs. A recognizable dummy beats a plausible-looking fake account.
LOCAL_ACCOUNT = "000000000000"


def publish(result: dict, bus=None) -> dict:
    finding = from_collector(result, account_id=os.environ.get("CCM_ACCOUNT_ID", LOCAL_ACCOUNT))
    (bus or LocalBus()).publish([finding])
    return finding
