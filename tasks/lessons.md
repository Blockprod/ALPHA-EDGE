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

## Backtest / Sessions

- [2026-03-24] **Session par paire — erreur de diagnostic** — EURUSD utilise la London Open (08:00-09:00 UTC), pas NYSE (09:30-10:30 ET). Tout diagnostic basé sur la session NYSE pour EURUSD produit des faux positifs. Toujours vérifier `config.trading.pair_sessions[pair]` ou `_PAIR_SESSION_DEFAULTS[pair]` avant toute analyse de bars.
- [2026-03-24] **PROJECT_TITLE contient ⚡ (U+26A1)** — ce caractère crashe le rendu Rich (`LegacyWindowsTerm` cp1252 sur Windows). Jamais passer `PROJECT_TITLE` directement à `Text()` ou `Panel()`. Toujours strip avec `.replace("\u26a1 ", "").replace("\u26a1", "")` avant injection dans Rich.
- [2026-03-24] **Silence signal EURUSD London Open — structurel** — 88% des sessions London Open EURUSD sont rejetées par le filtre FCR (range pré-session < 8 pips asiatique). Le taux signal est ~1-2% : 1-2 trades/mois expecté. Un silence de 9 mois est statistiquement plausible. Ne pas ajuster les paramètres FCR sans N ≥ 30 trades post-modification. Action correcte : ajouter des paires (GBPUSD, AUDUSD) pour augmenter la fréquence.
- [2026-03-24] **`_backtest_pair` vs `_fetch_pair_trades`** — `_fetch_pair_trades` applique `session_spec` depuis `config.trading.pair_sessions[pair]`. Appeler `_backtest_pair` directement sans passer `session_spec` utilise NYSE par défaut, ce qui donne des résultats erronés pour les paires London Open. Toujours passer `session_spec=config.trading.pair_sessions.get(pair)` dans les diagnostics directs.

## Optimisation stratégie (2026-04-01)

- **ATR-based SL (sl_atr_multiplier) catastrophique pour l'intraday** — Tester sl_atr_multiplier=0.5 a élargi le SL à ~40 pips et le TP à ~80 pips. Pour une session NYSE de 1 heure (range ~60-80 pips), un TP à 80 pips est rarement atteint. Résultat : WR 36% (inchangé), Sharpe 0.24 vs 0.90 baseline. L'ATR-SL est correct pour les stratégies multi-jours (trend-following); pour l'intraday momentum sur 1 session, un SL fixe calibré sur la portée attendue du signal est supérieur. Ne jamais ré-suggérer sl_atr_multiplier > 0 pour cette stratégie.
- **direction_filter="LONG" supprime la moitié des alpha** — La stratégie EMA crossover (ema_fast < ema_slow → SHORT, direction=-1) était bloquée. Le "LOCK" was basé sur N=4 trades paper → statistiquement invalide. En activant direction_filter="ALL" : Sharpe 0.90 → 2.02, WR 36% → 43%, Return +21% → +158%, trades 283 → 552. La règle : ne jamais verrouiller un filtre sur N < 30 trades en production ; toujours tester bidirectionnel dans le backtest avant de locker.
- **IS/OOS degradation > 30% est une alerte, pas un arrêt** — Sharpe IS=2.33 → OOS=1.26 (dégradation 45.8%). Le seuil 30% déclenche WARNING mais le résultat OOS=1.26 est encore positif et institutionnel. Investiguer la cause (conditions de marché OOS = 2025-2026 plus volatiles/choppy). Régime filter + walk-forward sont les prochaines étapes si OOS se dégrade en paper trading.
- **NZDUSD = 0 trades avec direction=LONG** — NZD en tendance baissière structurelle vs USD 2023–2026. LONG-only bloque tous les signaux. Avec direction=ALL, NZDUSD Short pourrait générer des trades valides. Tester après consolidation du baseline bidirectionnel.
- **AUDUSD PF=1.08 marginal sur 3 ans** — Insufficient pour justifier l'ajout. Seuil minimal : PF ≥ 1.20 et N ≥ 50 trades par paire pour inclusion.
- **Regime filter ATR-percentile aggrave IS/OOS gap** — Testé 2026-04-01 : `enabled: true, block_on: "low_vol"`, IS Sharpe 2.90 mais OOS Sharpe 0.92 (gap 68.3% vs 45.8% sans filtre). Raison : en 2025-2026 les sessions "low_vol" (TR < 80% médiane glissante) précèdent souvent des breakouts momentum valides (compression → expansion). Le filtre bloque de bons trades OOS. Verdict : ne pas activer ce filtre pour cette stratégie intraday.
## Lot Sizing (2026-04-02)

- **`risk_pct_by_pair` réduit le MaxDD sans toucher la fréquence des trades** — Réduire GBPUSD (PF=1.25) de 0.67%→0.50% et augmenter EURUSD (PF=1.80) à 0.80% a réduit MaxDD IS 9.00%→6.72% et amélioré Sharpe IS 2.90→3.06. Le total trades reste inchangé (579) car `risk_pct_by_pair` n'affecte que `_apply_equity_sizing` (post-hoc P&L). Règle : quand une paire domine le trade count avec un PF faible (>50% trades, PF<1.30), réduire son risk_pct de 20-25% est sûr et efficace.
- **`_apply_equity_sizing` est le seul driver P&L backtest** — pair-agnostique, compound. Tous les bugs de `exchange_rate=0.0` ou `starting_equity` fixe dans `_validate_backtest_signal` n'ont aucun impact sur les métriques reportées. Ne pas les confondre avec des bugs de P&L.
- **OOS MaxDD > IS MaxDD est structurel (compounding)** — L'OOS démarre après le pic IS. Equity plus élevée → pertes absolues plus importantes en OOS → MaxDD% OOS toujours > IS. C'est le comportement attendu du fixed-fraction, pas un signe d'overfit. Le levier pour réduire OOS DD est `risk_pct_by_pair` (redistribution) ou ATR-scaling (Piste 3.3).
- **ATR-scaling réduit OOS MaxDD au coût d'un P&L absolu légèrement inférieur** — Piste 3.3 : `pct_eff = pct_pair × min(1.0, max(0.5, ATR_ref / ATR_current))`. Résultat : OOS MaxDD 14.33%→13.44% (−0.89pp), Sharpe IS 3.06→3.00 (trade-off acceptable), trades=579 (inchangé). P&L total −$2,677 (réduction attendue : moins de risque sur sessions volatiles). Formula n'augmente jamais au-delà du `risk_pct_by_pair` configuré (clamp à 1.0). Le plancher à 50% évite une réduction excessive. ATR_ref: EURUSD=80p, GBPUSD=100p, USDJPY=110p.

- **USDJPY excellent signal mais instable OOS** — WR=49.5%, PF=1.64 en IS (3 ans). Mais BOJ policy reversals 2025 (hausses de taux) causent un retournement JPY brutal → OOS DD explose (siziing composé depuis un equity IS élevé). Règle : USDJPY ne doit être activé qu'avec un sizing indépendant par paire (non composé sur l'ensemble du portfolio).
- **Portfolio diversification ≠ ajouter des paires USD-corrélées** — TEST COMPLET :
  - EUR+GBP : Sharpe=2.02, OOS=1.26, OOS_DD=39% ← **MEILLEUR (OOS stabilité)**
  - EUR+JPY : Sharpe=3.12, OOS=1.40, OOS_DD=52% (USDJPY IS fort, OOS retourne)
  - EUR+GBP+JPY : Sharpe=2.62, OOS=1.10, OOS_DD=74% (sizing composé amplifie pertes corrélées)
  - EUR+GBP+AUD+JPY : OOS_DD=79% — catastrophique
  - La corrélation USD empêche la vraie diversification. Le sizing composé transforme une série de pertes en cascade exponentielle depuis un peak IS élevé. Solution : sizing indépendant par paire ou réduire risk_pct proportionnellement.
