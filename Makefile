# ============================================================
# PROJECT      : ALPHAEDGE — FCR Forex Trading Bot
# FILE         : Makefile
# DESCRIPTION  : CI-ready QA and build targets
# AUTHOR       : ALPHAEDGE Dev Team
# WORKFLOW     : VSCode + Claude + Copilot Pro + File Engineering
# PYTHON       : 3.11.9
# LAST UPDATED : 2026-03-07
# ============================================================

.PHONY: lint format typecheck pylint test qa qa-strict build all clean

# --- Linting + Formatting (Ruff) ---
lint:
	python -m ruff check alphaedge/ --config pyproject.toml

format:
	python -m ruff format alphaedge/

# --- Type Checking (Pyright / Pylance) ---
typecheck:
	python -m pyright alphaedge/

# --- Pylint ---
pylint:
	python -m pylint alphaedge/

# --- Testing ---
test:
	python -m pytest alphaedge/tests -v --tb=short \
		--cov=alphaedge \
		--cov-report=html:reports/ALPHAEDGE_coverage_report \
		--cov-fail-under=80

# --- Full QA Pipeline ---
qa: lint typecheck test

# --- QA Strict (inclut pylint) ---
qa-strict: lint typecheck pylint test

# --- Cython Build ---
build:
	python setup.py build_ext --inplace

# --- All: QA + Build ---
all: qa build

# --- Clean artifacts (cross-platform) ---
clean:
	python -c "import shutil, pathlib; [p.unlink() for p in pathlib.Path('.').rglob('*.pyd')]; [p.unlink() for p in pathlib.Path('.').rglob('*.so')]"
	python -c "import shutil, pathlib; [shutil.rmtree(p) for p in pathlib.Path('.').rglob('__pycache__')]"
	python -c "import shutil, pathlib; [shutil.rmtree(p) for p in pathlib.Path('.').rglob('*.egg-info')]"
	python -c "import shutil, pathlib; [shutil.rmtree(d) for d in ['build', 'dist'] if pathlib.Path(d).exists()]"
