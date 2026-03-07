# ============================================================
# PROJECT      : ALPHAEDGE — FCR Forex Trading Bot
# FILE         : Makefile
# DESCRIPTION  : CI-ready QA and build targets
# AUTHOR       : ALPHAEDGE Dev Team
# WORKFLOW     : VSCode + Claude + Copilot Pro + File Engineering
# PYTHON       : 3.11.9
# LAST UPDATED : 2026-03-07
# ============================================================

.PHONY: format lint typecheck test qa build all clean

# --- Formatting ---
format:
	python -m black alphaedge/

# --- Linting ---
lint:
	python -m ruff check alphaedge/ --config pyproject.toml
	python -m pylint alphaedge/ --rcfile=.pylintrc

# --- Type Checking ---
typecheck:
	python -m mypy alphaedge/ --config-file mypy.ini

# --- Testing ---
test:
	python -m pytest alphaedge/tests -v --tb=short \
		--cov=alphaedge \
		--cov-report=html:ALPHAEDGE_coverage_report.html \
		--cov-fail-under=80

# --- Full QA Pipeline ---
qa: format lint typecheck test

# --- Cython Build ---
build:
	python setup.py build_ext --inplace

# --- All: QA + Build ---
all: qa build

# --- Clean artifacts ---
clean:
	find . -type f -name "*.so" -delete 2>/dev/null || del /s /q *.pyd 2>nul
	find . -type f -name "*.pyd" -delete 2>/dev/null || echo "clean done"
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || echo "clean done"
	find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || echo "clean done"
	rm -rf build/ dist/ 2>/dev/null || rmdir /s /q build dist 2>nul
