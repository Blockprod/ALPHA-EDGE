# ============================================================
# PROJECT      : ALPHAEDGE — FCR Forex Trading Bot
# FILE         : Makefile
# DESCRIPTION  : CI-ready QA and build targets
# AUTHOR       : ALPHAEDGE Dev Team
# WORKFLOW     : VSCode + Claude + Copilot Pro + File Engineering
# PYTHON       : 3.11.9
# LAST UPDATED : 2026-03-07
# ============================================================

.PHONY: lint format typecheck pylint bandit test bench qa qa-strict build all clean web-dashboard install-hooks

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

# --- Latency Benchmark ---
bench:
	python -m pytest alphaedge/tests/ -k "latency" -q --tb=short

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

# --- Install Git hooks ---
install-hooks:
	cp .github/hooks/pre-commit .git/hooks/pre-commit
	python -c "import os, stat; p='.git/hooks/pre-commit'; os.chmod(p, os.stat(p).st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)"
	@echo "✅ pre-commit hook installed"
	python -c "import shutil, pathlib; [p.unlink() for p in pathlib.Path('.').rglob('*.pyd')]; [p.unlink() for p in pathlib.Path('.').rglob('*.so')]"
	# WARNING: removes Cython-generated .c files. After clean, 'make build' requires
	# Cython to be installed (pip install Cython==3.0.10) to regenerate them.
	python -c "import pathlib; [p.unlink() for p in pathlib.Path('alphaedge/core').glob('*.c')]"
	python -c "import shutil, pathlib; [shutil.rmtree(p) for p in pathlib.Path('.').rglob('__pycache__')]"
	python -c "import shutil, pathlib; [shutil.rmtree(p) for p in pathlib.Path('.').rglob('*.egg-info')]"
	python -c "import shutil, pathlib; [shutil.rmtree(d) for d in ['build', 'dist'] if pathlib.Path(d).exists()]"
