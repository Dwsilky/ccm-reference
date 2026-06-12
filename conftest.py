"""Make the hyphenated top-level dirs importable in tests.

The repo layout follows audit-domain naming (config-rules/, normalizer/ ...)
rather than Python package naming; each Lambda ships as its own zip in
deployment, so nothing here is ever imported as one installed package.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT / "config-rules"))
sys.path.insert(0, str(ROOT))
