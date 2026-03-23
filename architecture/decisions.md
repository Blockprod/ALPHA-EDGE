# ALPHAEDGE — Architecture Decisions

Enregistrement des décisions architecturales (ADR) du projet.

---

## ADR-001 — Cython pour les modules de détection signal

**Date** : 2026-01
**Statut** : ✅ Accepté

**Contexte** : Les fonctions de détection FCR, gap et engulfing sont appelées sur chaque barre M1 (potentiellement 60 appels/heure par paire). La latence minimise l'écart entre signal et exécution.

**Décision** : Implémenter `fcr_detector`, `gap_detector`, `engulfing_detector`, `risk_manager`, `order_manager` en Cython 3.0 (`.pyx`).

**Conséquences** :
- `make build` obligatoire après tout changement `.pyx`
- Les `.pyd`/`.so` compilés sont le runtime — les `.pyx` seuls ne font rien
- Tests via `_stubs/` (Python pur) pour éviter la dépendance Cython en CI

---

## ADR-002 — Paper trading par défaut (ALPHAEDGE_PAPER=true)

**Date** : 2026-01
**Statut** : ✅ Accepté

**Contexte** : Un bot de trading mal configuré peut causer des pertes réelles sur IBKR dans les secondes suivant le lancement.

**Décision** : `ALPHAEDGE_PAPER=true` est la valeur par défaut dans `.env.example` et dans la logique de connexion. Le port 4002 (paper) est utilisé sauf si `ALPHAEDGE_PAPER=false` est explicitement positionné.

**Conséquences** :
- Jamais de `ALPHAEDGE_PAPER=false` dans un fichier versionné
- Le passage en live nécessite une confirmation explicite de l'utilisateur

---

## ADR-003 — Pipeline all-or-nothing

**Date** : 2026-01
**Statut** : ✅ Accepté

**Contexte** : Chaque étape du pipeline (FCR → gap → engulfing → sizing → ordre) est une condition nécessaire. Un signal partiel ne doit jamais conduire à un ordre.

**Décision** : Chaque fonction de détection retourne `None` / `detected: False` / `is_valid: False` si la condition n'est pas remplie. L'orchestrateur (`signal_pipeline.py`) s'arrête immédiatement à la première valeur négative.

**Conséquences** : Voir le tableau des contrats de retour dans `.claude/context.md`.

---

## ADR-004 — Séparation `engine/` ↔ `core/`

**Date** : 2026-01
**Statut** : ✅ Accepté

**Contexte** : `engine/` contient les boucles async et la connectivité IB (non testables sans Gateway). `core/` contient la logique signal (testable en isolation via stubs).

**Décision** : Dépendance unidirectionnelle `engine/` → `core/` (jamais l'inverse). Coverage exclut `engine/`.

---

## ADR-005 — `zoneinfo` exclusivement pour les timezones

**Date** : 2026-01
**Statut** : ✅ Accepté

**Contexte** : Les sessions NYSE (EST/EDT) et London (UTC) ont des changements DST sur des dates différentes (EU et US ~1 semaine d'écart). Les offsets hardcodés et `pytz` introduisent des bugs DST.

**Décision** : `zoneinfo` exclusivement. `pytz` et offsets UTC hardcodés sont interdits.

**Conséquences** :
- `timezone.py` et `session_manager.py` couverts par des tests de DST boundary
- Ne jamais toucher ces fichiers sans relancer les tests DST edge cases

---

## ADR-006 — Tous les paramètres numériques dans `constants.py`

**Date** : 2026-01
**Statut** : ✅ Accepté

**Contexte** : Paramètres hardcodés dispersés = double maintenance, drift silencieux entre modules.

**Décision** : `alphaedge/config/constants.py` est la source unique de vérité pour tous les paramètres numériques (pip sizes, RR, risk %, session times, IB limits, slippage, spread, etc.).

**Conséquences** : Toute valeur numérique de trading dans le code source est une violation de cette règle.

---

## ADR-007 — `ml_filter.py` archivé en `_experimental/`

**Date** : 2026-03-20
**Statut** : ✅ Accepté

**Contexte** : Le module `ml_filter.py` (LogisticRegression walk-forward) est fonctionnel et testé mais non intégré dans le pipeline live. Son intégration nécessite une validation OOS du Sharpe ratio (baseline : 3.37).

**Décision** : Archivé dans `engine/_experimental/ml_filter.py`. Un shim de compatibilité est maintenu dans `engine/ml_filter.py` pour ne pas casser les imports existants.

**Conséquences** : Toute intégration future nécessite un benchmark OOS avant merge.

---

## ADR-008 — Bandit dans `make qa-strict` (pas dans `make qa`)

**Date** : 2026-03-20
**Statut** : ✅ Accepté

**Contexte** : Bandit produit des faux positifs sur des patterns légitimes (pickle local, urlopen sur URL de config). Les placer dans `make qa` bloquerait les développeurs.

**Décision** : Bandit intégré dans `make qa-strict` uniquement. Les faux positifs connus annotés `# nosec BXX`.
