# Convenience targets. On Windows without make, run the underlying commands
# directly (they are listed in README.md > Running locally).

PY := .venv/Scripts/python.exe
ifeq ($(OS),)
PY := .venv/bin/python
endif

.PHONY: venv test lint matrix demo

venv:
	python -m venv .venv
	$(PY) -m pip install -r requirements-dev.txt

test:
	$(PY) -m pytest

lint:
	$(PY) -m ruff check .

matrix:
	$(PY) scripts/gen_matrix.py

# Full local loop: seed mock AWS state -> evaluate -> normalize -> route.
# Dry-run tickets by default; `python scripts/demo.py --live` files real issues.
demo:
	$(PY) scripts/demo.py
