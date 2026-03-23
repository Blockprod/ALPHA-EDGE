# ============================================================
# PROJECT      : ALPHAEDGE — FCR Forex Trading Bot
# FILE         : Makefile
# DESCRIPTION  : CI-ready QA and build targets
# AUTHOR       : ALPHAEDGE Dev Team
# WORKFLOW     : VSCode + Claude + Copilot Pro + File Engineering
# PYTHON       : 3.11.9
# LAST UPDATED : 2026-03-07
# ============================================================

.PHONY: lint format typecheck pylint bandit test qa qa-strict build all clean web-dashboard

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

# --- Security (Bandit) ---
bandit:
	python -m bandit -r alphaedge/ -ll --exclude alphaedge/tests,alphaedge/core/_stubs

# --- Testing ---
test:
	python -m pytest alphaedge/tests -v --tb=short \
		--cov=alphaedge \
		--cov-report=html:reports/ALPHAEDGE_coverage_report \
		--cov-fail-under=80

# --- Full QA Pipeline ---
qa: lint typecheck test

# --- QA Strict (inclut pylint + bandit) ---
qa-strict: lint typecheck pylint bandit test

# --- Cython Build ---
build:
	python setup.py build_ext --inplace

# --- All: QA + Build ---
all: qa build

# --- Web Dashboard (standalone FastAPI server) ---
web-dashboard:
	.venv\Scripts\python -m uvicorn alphaedge.engine.web_dashboard:app --port 8080

# --- Clean artifacts (cross-platform) ---
clean:
	python -c "import shutil, pathlib; [p.unlink() for p in pathlib.Path('.').rglob('*.pyd')]; [p.unlink() for p in pathlib.Path('.').rglob('*.so')]"
	python -c "import pathlib; [p.unlink() for p in pathlib.Path('alphaedge/core').glob('*.c')]"
	python -c "import shutil, pathlib; [shutil.rmtree(p) for p in pathlib.Path('.').rglob('__pycache__')]"
	python -c "import shutil, pathlib; [shutil.rmtree(p) for p in pathlib.Path('.').rglob('*.egg-info')]"
	python -c "import shutil, pathlib; [shutil.rmtree(d) for d in ['build', 'dist'] if pathlib.Path(d).exists()]"
