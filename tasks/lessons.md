# ALPHAEDGE — AI Lessons Learned
**Créé le :** 2026-03-12 à 12:34

> Updated after every user correction. Review at session start.
> Format: `[date] [file/module] — mistake → correct pattern`

---

## Cython

- Always run `make build` after **any** `.pyx` edit. The `.pyd`/`.so` is the runtime — the `.pyx` alone does nothing.

## Config / YAML

- `excluded_days`, `usd_correlation_filter`, `fcr_range_cv_max` were tested and ELIMINATED. Do not re-suggest them.
- Baseline locked: EURUSD+USDJPY, RR=2.0, risk_pct=3.0, Sharpe=3.37.

## File Organisation

- Outputs (csv, png, coverage) → `reports/`
- Documentation (.md audits, roadmap) → `docs/`
- Launcher scripts (.bat, .ps1) → `scripts/`
- Temporary sweep files → `scripts/` (not root)

## Windows Task Scheduler

- Use `.bat` + `schtasks /create /xml` pattern (not PowerShell `Register-ScheduledTask` — fails silently with UAC).
- Auto-elevate with `net session >nul 2>&1` check.
- Cleanup `%TEMP%\*.xml` after `schtasks /create`.

## Architecture

- AlphaEdge is event-driven (IB push via `reqRealTimeBars`). No polling/scheduling needed. Do not suggest `schedule.every(...)`.
- `asyncio.sleep(1.0)` in `get_live_spread` / `get_mid_price` is intentional (IB data arrival wait). Not a latency bug for M1 strategy.
- `max_lot_size` in config is unused in backtest (kept for call-site compatibility). Changing it has no effect on backtest results.

## Workflow

- [2026-03-22] `tasks/prompts/audit_modernize_python_syntax_prompt.md` — do not drive the pass from folder inventory alone; start each modernization step from visible `PROBLEMS`/`get_errors`, then open only the implicated files and apply targeted fixes.
- [2026-03-22] **Paramètres de fonctions orphelins** — ni Pyright ni `ruff check` (config standard) ne détectent les paramètres de fonctions non utilisés dans le corps. Seul `ruff check --select ARG` les remonte. La règle "zéro orphelin" du prompt doit TOUJOURS inclure un pass `--select ARG` explicite, en plus de `get_errors`. Ne jamais se fier à `ruff check` seul pour déclarer un fichier propre.
- [2026-03-22] **Alignement stubs↔Cython** — après toute correction d'un `_stubs/*.py`, vérifier que la signature (nom, ordre des paramètres, clés du dict retourné) est identique au `.pyx` correspondant dans `alphaedge/core/`. Un stub qui diverge du Cython est une bombe silencieuse au moment du chargement du module compilé.
- [2026-03-23] **`_param` renaming et API publique** — renommer un paramètre en `_param` pour supprimer ARG01 est VALIDE uniquement pour des fonctions PRIVÉES (helpers internes). Pour les fonctions PUBLIQUES qui sont parties d'une API (ex: `check_pair_limit`), garder le nom exact du paramètre Cython (`pair`), et connecter `pair` à un usage naturel (ex: `if not pair: raise ValueError(...)`) pour satisfaire ARG01 sans casser les appels par mot-clé.
- [2026-03-23] **`_param` préfixé et angle mort de ruff** — `ruff --select ARG` ignore silencieusement les paramètres `_param` (convention Python "intentionnellement inutilisé"). Pylance remonte `"_param" is not accessed` comme WARNING, non comme ERROR, donc `get_errors` peut le manquer. Règle d'or : même un paramètre `_`-préfixé doit être connecté à un usage naturel. Workflow obligatoire après le pass ARG : grepper les fichiers pour `def .*\b_[a-z]` et vérifier manuellement que chaque occurrence est utilisée dans le corps de la fonction.
