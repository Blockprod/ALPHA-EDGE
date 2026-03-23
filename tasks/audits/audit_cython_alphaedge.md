## BLOC 1 — INVENTAIRE DES MODULES CYTHON

### Constat global

Les 5 modules Cython attendus sont présents dans `alphaedge/core/`, avec leur source `.pyx`, leur artefact `.c`, leur binaire Windows `.cp311-win_amd64.pyd` et leur stub Python homologue dans `alphaedge/core/_stubs/`.

| Module | `.pyx` | `.pyd` | `.c` | Stub `_stubs/` | Nom cohérent |
|--------|--------|--------|------|----------------|--------------|
| `fcr_detector` | ✅ `alphaedge/core/fcr_detector.pyx` | ✅ `alphaedge/core/fcr_detector.cp311-win_amd64.pyd` | ✅ `alphaedge/core/fcr_detector.c` | ✅ `alphaedge/core/_stubs/fcr_detector.py` | ✅ |
| `gap_detector` | ✅ `alphaedge/core/gap_detector.pyx` | ✅ `alphaedge/core/gap_detector.cp311-win_amd64.pyd` | ✅ `alphaedge/core/gap_detector.c` | ✅ `alphaedge/core/_stubs/gap_detector.py` | ✅ |
| `engulfing_detector` | ✅ `alphaedge/core/engulfing_detector.pyx` | ✅ `alphaedge/core/engulfing_detector.cp311-win_amd64.pyd` | ✅ `alphaedge/core/engulfing_detector.c` | ✅ `alphaedge/core/_stubs/engulfing_detector.py` | ✅ |
| `risk_manager` | ✅ `alphaedge/core/risk_manager.pyx` | ✅ `alphaedge/core/risk_manager.cp311-win_amd64.pyd` | ✅ `alphaedge/core/risk_manager.c` | ✅ `alphaedge/core/_stubs/risk_manager.py` | ✅ |
| `order_manager` | ✅ `alphaedge/core/order_manager.pyx` | ✅ `alphaedge/core/order_manager.cp311-win_amd64.pyd` | ✅ `alphaedge/core/order_manager.c` | ✅ `alphaedge/core/_stubs/order_manager.py` | ✅ |

### Évaluation

- Inventaire des 5 modules attendu: conforme.
- Présence des artefacts compilés Windows: conforme sur ce workspace.
- Présence des stubs de secours: conforme.
- Présence des `.c`: conforme comme artefacts de transpilation, sans analyse de leur contenu.

---

## BLOC 2 — COHÉRENCE DES INTERFACES

### Constat positif

Les signatures `.pyx` et `_stubs/` sont alignées pour les fonctions publiques réellement exposées:

| Fonction | `.pyx` | Stub | Signature stub == `.pyx` | Return type annoté dans le stub |
|----------|--------|------|---------------------------|----------------------------------|
| `detect_fcr` | `alphaedge/core/fcr_detector.pyx:91` | `alphaedge/core/_stubs/fcr_detector.py:8` | CONFORME | Oui |
| `detect_fcr_scan` | `alphaedge/core/fcr_detector.pyx:156` | `alphaedge/core/_stubs/fcr_detector.py:31` | CONFORME | Oui |
| `detect_gap` | `alphaedge/core/gap_detector.pyx:137` | `alphaedge/core/_stubs/gap_detector.py:8` | CONFORME | Oui |
| `is_in_gap_zone` | `alphaedge/core/gap_detector.pyx:203` | `alphaedge/core/_stubs/gap_detector.py:57` | CONFORME | Oui |
| `detect_engulfing` | `alphaedge/core/engulfing_detector.pyx:209` | `alphaedge/core/_stubs/engulfing_detector.py:8` | CONFORME | Oui |
| `calculate_position_size` | `alphaedge/core/risk_manager.pyx:129` | `alphaedge/core/_stubs/risk_manager.py:9` | CONFORME | Oui |
| `check_daily_limit` | `alphaedge/core/risk_manager.pyx:199` | `alphaedge/core/_stubs/risk_manager.py:47` | CONFORME | Oui |
| `create_bracket_order` | `alphaedge/core/order_manager.pyx:138` | `alphaedge/core/_stubs/order_manager.py:8` | CONFORME | Oui |

Les fonctions publiques additionnelles exposées par le runtime sont elles aussi cohérentes entre `.pyx` et `_stubs/`:

- `check_pair_limit`: `alphaedge/core/risk_manager.pyx:281` / `alphaedge/core/_stubs/risk_manager.py:74`
- `apply_slippage_buffer`: `alphaedge/core/risk_manager.pyx:326` / `alphaedge/core/_stubs/risk_manager.py:98`
- `lots_to_units`: `alphaedge/core/order_manager.pyx:239` / `alphaedge/core/_stubs/order_manager.py:89`

### Problèmes

| ID | Description | Fichier:Ligne | Sévérité | Impact | Effort |
|----|-------------|---------------|----------|--------|--------|
| C-01 | Contrat public documenté incohérent pour `is_in_gap_zone`: `CLAUDE.md` documente 3 paramètres (`price, gap_high, gap_low`), alors que le runtime et le stub exigent 5 paramètres (`tolerance_pips`, `pip_size` en plus). | `CLAUDE.md:314` ; `alphaedge/core/gap_detector.pyx:203` ; `alphaedge/core/_stubs/gap_detector.py:57` ; `alphaedge/tests/test_gap_detector_zone.py:24` | 🟠 | Un appelant qui suit le contrat documenté casse à l'exécution | S |
| C-02 | Contrats de sortie documentés incohérents pour plusieurs API publiques. `detect_engulfing` est documenté avec `{direction, entry, stop_loss, take_profit, rr_ratio}`, mais le runtime expose `signal`, `entry_price`, `risk_pips`, `reward_pips`. `check_daily_limit` est documenté avec `{halt_trading, daily_pnl_pct, trades_remaining, reason}`, mais le runtime expose `limit_breached`, `can_trade`, `daily_pnl`, `max_trades`. `calculate_position_size` accepte aussi un paramètre optionnel `exchange_rate` non documenté dans `CLAUDE.md`. | `CLAUDE.md:327` ; `CLAUDE.md:335` ; `CLAUDE.md:342` ; `alphaedge/core/engulfing_detector.pyx:209` ; `alphaedge/core/engulfing_detector.pyx:217` ; `alphaedge/core/_stubs/engulfing_detector.py:8` ; `alphaedge/core/_stubs/engulfing_detector.py:16` ; `alphaedge/tests/test_engulfing_detector_bearish.py:42` ; `alphaedge/core/risk_manager.pyx:129` ; `alphaedge/core/_stubs/risk_manager.py:18` ; `alphaedge/core/risk_manager.pyx:199` ; `alphaedge/tests/test_risk_manager_daily.py:32` | 🟠 | La doc d'interface ne correspond plus au comportement réel validé par les tests | M |

### Évaluation

- Signature stub == signature `.pyx`: oui pour les fonctions auditées.
- Types de retour annotés dans les stubs: oui.
- Paramètres optionnels documentés: partiellement seulement. `min_body_ratio`, `max_wick_ratio` et `exchange_rate` existent en code mais ne figurent pas dans le contrat public résumé de `CLAUDE.md`.

---

## BLOC 3 — __init__.pyi ET __init__.py

### Constat positif

- Le fallback runtime compilé → stub est explicite dans `alphaedge/core/__init__.py` via `_load_core_module()` et `importlib.import_module(...)` sur le module compilé puis le stub en `except ImportError`: `alphaedge/core/__init__.py:21`, `alphaedge/core/__init__.py:24`, `alphaedge/core/__init__.py:26`.
- Les 5 modules publics sont bien re-exportés par `alphaedge/core/__init__.py`: `alphaedge/core/__init__.py:29` à `alphaedge/core/__init__.py:33`.
- `alphaedge/core/__init__.pyi` est cohérent avec cette surface publique et pointe explicitement vers les stubs pour l'analyse statique: `alphaedge/core/__init__.pyi:3`, `alphaedge/core/__init__.pyi:7` à `alphaedge/core/__init__.pyi:11`.
- La logique de fallback est documentée dans la docstring de package et dans la note Pyright du `.pyi`.

### Point d'attention

`alphaedge.core` ne re-exporte pas les fonctions individuellement; il re-exporte les 5 namespaces de modules. Ce n'est pas un bug dans l'état actuel du repo, car les tests et le code consomment bien `from alphaedge.core import gap_detector as gap_mod` plutôt que `from alphaedge.core import detect_gap`. Références: `alphaedge/core/__init__.py:29` à `alphaedge/core/__init__.py:33`, `alphaedge/tests/test_gap_detector_zone.py:16`, `alphaedge/tests/test_fcr_detector_detect.py:19`.

### Évaluation

- `__init__.py` exporte toutes les fonctions publiques des 5 modules: indirectement seulement, via objets modules.
- `__init__.pyi` cohérent avec `__init__.py`: oui.
- Re-exports typés correctement: oui, via `_stubs`.
- Imports fallback `_stubs/` si `.pyd` absent: oui.
- Fallback documenté: oui.

---

## BLOC 4 — BUILD ET REPRODUCIBILITÉ

### Constat positif

- `setup.py` liste bien les 5 extensions Cython: `setup.py:32`, `setup.py:36`, `setup.py:40`, `setup.py:44`, `setup.py:48`.
- `language_level=3` est défini: `setup.py:63`.
- Les directives `boundscheck=False`, `wraparound=False`, `cdivision=True` sont explicitement fixées: `setup.py:64` à `setup.py:66`.
- `make build` compile via `python setup.py build_ext --inplace`: `Makefile:46` à `Makefile:47`.
- `build/`, `dist/`, `*.egg-info/`, `*.pyd` et `*.c` sont bien ignorés dans `.gitignore`: `.gitignore:13`, `.gitignore:21` à `.gitignore:24`.
- La version de Cython est fixée à `3.0.10`, conforme au cadre attendu: `requirements.txt:13`.
- `annotate` n'est pas renseigné dans `cythonize(...)`; le comportement effectif est donc l'absence d'annotation HTML, soit l'équivalent pratique de `False` dans cette configuration.

### Problèmes

| ID | Description | Fichier:Ligne | Sévérité | Impact | Effort |
|----|-------------|---------------|----------|--------|--------|
| C-03 | `make clean` supprime les `.pyd`, `.so`, `__pycache__`, `*.egg-info`, `build/` et `dist/`, mais ne supprime pas les `.c` générés. Le prompt de workflow attend explicitement un nettoyage `.pyd/.c/build/`. | `Makefile:57` à `Makefile:61` ; `.gitignore:24` | 🟡 | Rebuild moins propre, risque d'artefacts C générés obsolètes dans le workspace | XS |
| C-04 | La CI ne construit jamais explicitement les extensions Cython avant Pytest. Le workflow installe les dépendances puis lance Ruff, Pyright et Pytest sans `make build` ni `python setup.py build_ext --inplace`. | `.github/workflows/ci.yml:15` à `.github/workflows/ci.yml:38` | 🟠 | La CI peut valider uniquement le chemin stub sur Linux alors qu'un poste dev Windows exécute les `.pyd` compilés | S |

### Évaluation

- `setup.py` liste les 5 extensions: oui.
- `make build` produit les `.pyd`: oui sur ce workspace Windows, et la commande cible est correcte.
- `make clean` supprime `.pyd/.c/build/`: non, les `.c` ne sont pas nettoyés.
- Version Cython fixée: oui, `3.0.10`.
- `language_level=3`: oui.
- `annotate=True` ou `False`: non explicitement déclaré, comportement implicite équivalent à `False`.
- `build/` dans `.gitignore`: oui.
- CI build avant test: non.

---

## BLOC 5 — STUBS DANS LES TESTS

### Constat positif

- Les tests des modules Cython suivent bien la convention `test_<module>_<scenario>.py`: `test_fcr_detector_detect.py`, `test_gap_detector_zone.py`, `test_engulfing_detector_bearish.py`, `test_risk_manager_daily.py`, `test_order_manager_bracket.py`.
- Aucun test n'importe directement `alphaedge.core._stubs.*`; il n'y a pas non plus d'import direct des binaires `.pyd`. Les imports passent par le wrapper de package `alphaedge.core`: `alphaedge/tests/test_fcr_detector_detect.py:19`, `alphaedge/tests/test_gap_detector_zone.py:16`, `alphaedge/tests/test_engulfing_detector_bearish.py:18`, `alphaedge/tests/test_risk_manager_daily.py:16`, `alphaedge/tests/test_order_manager_bracket.py:16`.
- Les cas de retour `None` sont couverts pour les chemins FCR et engulfing: `alphaedge/tests/test_fcr_detector_detect.py:69`, `alphaedge/tests/test_fcr_detector_detect.py:82`, `alphaedge/tests/test_fcr_detector_scan.py:120`, `alphaedge/tests/test_engulfing_detector_bearish.py:116`, `alphaedge/tests/test_engulfing_detector_bullish.py:90`, `alphaedge/tests/test_engulfing_detector_quality.py:76`, `alphaedge/tests/test_engulfing_detector_volume.py:74`.
- Les cas négatifs du gap detector sont couverts: `alphaedge/tests/test_gap_detector_empty.py:44`, `alphaedge/tests/test_gap_detector_spike.py:57`, `alphaedge/tests/test_gap_detector_zone.py:44`.

### Problèmes

| ID | Description | Fichier:Ligne | Sévérité | Impact | Effort |
|----|-------------|---------------|----------|--------|--------|
| C-05 | Les tests n'imposent pas de manière cohérente l'utilisation des stubs. Ils importent `alphaedge.core`, et `alphaedge/core/__init__.py` charge d'abord le module compilé s'il est présent. Comme `conftest.py` ne monkeypatche ni `sys.modules` ni `alphaedge.core`, le jeu de tests exécuté dépend de l'état des artefacts compilés dans le workspace. | `alphaedge/core/__init__.py:21` à `alphaedge/core/__init__.py:26` ; `alphaedge/tests/conftest.py:1` à `alphaedge/tests/conftest.py:220` ; `alphaedge/tests/test_fcr_detector_detect.py:19` ; `alphaedge/tests/test_gap_detector_zone.py:16` | 🟠 | Résultats de tests non strictement reproductibles entre environnements avec et sans `.pyd` | M |
| C-06 | La fonction publique `check_pair_limit` est exposée par `risk_manager.pyx`, mais elle n'a pas de test unitaire direct sur son implémentation Cython/stub. Le test multi-pair remplace au contraire `check_pair_limit` par une fonction locale mockée. | `alphaedge/core/risk_manager.pyx:281` ; `alphaedge/core/_stubs/risk_manager.py:74` ; `alphaedge/tests/test_race_condition_multi_pair.py:54` | 🟡 | Régression possible sur une API publique non couverte directement | XS |

### Évaluation

- Les tests importent depuis `_stubs/` ou directement depuis le `.pyd` compilé: ni l'un ni l'autre directement; ils importent via `alphaedge.core`.
- `conftest.py` remplace les modules Cython par les stubs: non.
- Convention `test_<module>_<scenario>.py`: globalement respectée sur la couche Cython.
- Tests manquants pour un module Cython: pas au niveau module, mais oui pour l'API publique `check_pair_limit`.
- Couverture des retours `None`: oui pour FCR et engulfing.

---

## SYNTHÈSE

### Verdict global

La couche Cython est saine sur sa structure: les 5 modules attendus sont présents, les stubs sont alignés avec les `.pyx`, le fallback runtime est clair, et `setup.py`/`Makefile` couvrent bien le cycle de compilation local. En revanche, la reproductibilité inter-environnements n'est pas totalement verrouillée: la CI ne construit pas explicitement les extensions, `make clean` ne purge pas les `.c`, et la suite de tests ne force pas un mode stub déterministe. Le point le plus important reste la dérive entre les contrats publics documentés dans `CLAUDE.md` et les interfaces réellement validées par les tests.

### Tableau synthèse

| ID | Bloc | Description | Fichier:Ligne | Sévérité | Impact | Effort |
|----|------|-------------|---------------|----------|--------|--------|
| C-01 | BLOC 2 | `is_in_gap_zone` documenté à 3 paramètres, implémenté à 5 | `CLAUDE.md:314` ; `alphaedge/core/gap_detector.pyx:203` ; `alphaedge/core/_stubs/gap_detector.py:57` | 🟠 | Appelants conformes à la doc cassent à l'exécution | S |
| C-02 | BLOC 2 | Dérive de contrat pour `detect_engulfing`, `check_daily_limit` et paramètre optionnel `exchange_rate` non documenté | `CLAUDE.md:327,335,342` ; `alphaedge/core/engulfing_detector.pyx:209,217` ; `alphaedge/core/risk_manager.pyx:129,199` | 🟠 | Documentation d'API en retard par rapport au runtime testé | M |
| C-04 | BLOC 4 | La CI ne build pas les extensions Cython avant Pytest | `.github/workflows/ci.yml:15-38` | 🟠 | Validation CI possiblement limitée au chemin stub | S |
| C-05 | BLOC 5 | Les tests dépendent de la présence locale des `.pyd` via `alphaedge.core` | `alphaedge/core/__init__.py:21-26` ; `alphaedge/tests/conftest.py:1-220` | 🟠 | Exécution non strictement déterministe entre environnements | M |
| C-03 | BLOC 4 | `make clean` ne supprime pas les `.c` générés | `Makefile:57-61` | 🟡 | Nettoyage incomplet du workspace de build | XS |
| C-06 | BLOC 5 | `check_pair_limit` n'a pas de test unitaire direct | `alphaedge/core/risk_manager.pyx:281` ; `alphaedge/tests/test_race_condition_multi_pair.py:54` | 🟡 | Régression silencieuse possible sur une API publique | XS |
