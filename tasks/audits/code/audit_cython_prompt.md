---
modele: sonnet-4.6
mode: agent
contexte: codebase
produit: audit_cython_alphaedge.md
derniere_revision: 2026-03-25
creation: 2026-03-20 à 15:33
---

#codebase

Tu es un ingénieur Cython senior spécialisé en systèmes
de trading algorithmique haute performance.
Tu réalises un audit EXCLUSIVEMENT centré sur
la couche Cython d'ALPHAEDGE.

─────────────────────────────────────────────
ÉTAPE 0 — VÉRIFICATION PRÉALABLE (OBLIGATOIRE)
─────────────────────────────────────────────
Vérifie si ce fichier existe déjà dans :
  tasks/audits/audit_cython_alphaedge.md

Si trouvé, affiche :
"⚠️ Audit Cython existant détecté :
 Fichier : tasks/audits/audit_cython_alphaedge.md
 Date    : [date modification]
 Lignes  : [nombre approximatif]

 [NOUVEAU]  → audit complet (écrase l'existant)
 [MÀJOUR]   → compléter sections manquantes
 [ANNULER]  → abandonner"

Si absent → démarrer directement :
"✅ Aucun audit Cython existant. Démarrage..."

─────────────────────────────────────────────
PÉRIMÈTRE STRICT
─────────────────────────────────────────────
Tu analyses UNIQUEMENT :
- La cohérence .pyx ↔ _stubs/ ↔ __init__.pyi
- La reproductibilité du build (setup.py, Makefile)
- La validité des stubs utilisés dans les tests
- Les signatures des interfaces publiques

Tu n'analyses PAS la logique stratégique Momentum+Carry,
la sécurité des credentials, ou engine/.

─────────────────────────────────────────────
CONTRAINTES ABSOLUES
─────────────────────────────────────────────
- Analyse les fichiers .pyx comme code source
  de référence — mais NE PAS inférer la logique
  interne (propriétaire)
- Cite fichier:ligne pour chaque écart
- Écris "À VÉRIFIER" sans preuve dans le code
- Les fichiers .c sont des artefacts de compilation
  — ne pas les analyser directement

─────────────────────────────────────────────
BLOC 1 — INVENTAIRE DES MODULES CYTHON
─────────────────────────────────────────────
Modules attendus dans alphaedge/core/ :
  momentum_detector.pyx / .pyd
  risk_manager.pyx / .pyd
  order_manager.pyx / .pyd

Pour chaque module, vérifie :
- .pyx présent ? ✅ / ❌
- .pyd présent (ou .so sur Linux) ? ✅ / ❌
- .c présent (artefact de transpilation) ? ✅ / ❌
- Stub dans _stubs/ présent ? ✅ / ❌
- Stub dans _stubs/ : nom de fichier correspond ? ✅ / ❌

Affiche le tableau complet des 3 modules.

─────────────────────────────────────────────
BLOC 2 — COHÉRENCE DES INTERFACES
─────────────────────────────────────────────
Compare les signatures dans les .pyx
avec les stubs dans alphaedge/core/_stubs/ :

Interfaces à vérifier (depuis CLAUDE.md) :

momentum_detector :
  detect_momentum(bars, fast_period, slow_period,
    adx_period, adx_threshold) → dict | None

risk_manager :
  calculate_position_size(account_equity, risk_pct,
    sl_pips, pair, pip_size, lot_type, min_lots,
    max_lots) → dict
  check_daily_limit(starting_equity, current_equity,
    max_daily_loss_pct, trades_today, max_trades)
    → dict

order_manager :
  create_bracket_order(direction, entry_price,
    stop_loss, take_profit, lot_size, pip_size,
    spread_pips, ...) → dict

Pour chaque fonction :
- Signature stub == signature .pyx ? CONFORME / ÉCART
- Return type annoté dans le stub ?
- Paramètres optionnels documentés ?

─────────────────────────────────────────────
BLOC 3 — __init__.pyi ET __init__.py
─────────────────────────────────────────────
Analyse alphaedge/core/__init__.py,
alphaedge/core/__init__.pyi :

- __init__.py exporte toutes les fonctions
  publiques des 3 modules ?
- __init__.pyi cohérent avec __init__.py ?
- Re-exports typés correctement ?
- Imports depuis _stubs/ en mode fallback
  (si .pyd absent) ?
- Logique de fallback (_stubs/) documentée ?

─────────────────────────────────────────────
BLOC 4 — BUILD ET REPRODUCIBILITÉ
─────────────────────────────────────────────
Analyse setup.py, Makefile :

- setup.py liste les 3 extensions Cython ?
- `make build` produit bien tous les .pyd ?
- `make clean` supprime .pyd/.c/build/ ?
- Cython version fixée dans requirements.txt ?
  (Cython 3.0 attendu — pas de 0.29 ni 3.1)
- language_level=3 défini dans setup.py ?
- annotate=True ou False dans setup.py ?
  (True génère des .html — présents dans .gitignore ?)
- build/ dans .gitignore ?
- Workflow CI (si présent) build avant test ?

─────────────────────────────────────────────
BLOC 5 — UTILISATION DES STUBS DANS LES TESTS
─────────────────────────────────────────────
Analyse alphaedge/tests/,
alphaedge/tests/conftest.py :

- Les tests importent-ils depuis _stubs/ ou
  directement depuis le .pyd compilé ?
- conftest.py : patch/replace les modules Cython
  par les stubs de façon cohérente ?
- Chaque fichier de test cible un module + scénario
  (convention : test_<module>_<scenario>.py) ?
- Tests manquants pour un module Cython ?
- Stubs couvrent-ils les cas de retour None
  (momentum=None, risk_invalid=False) ?

─────────────────────────────────────────────
SORTIE OBLIGATOIRE
─────────────────────────────────────────────
Crée le fichier :
  tasks/audits/audit_cython_alphaedge.md
Crée le dossier tasks/audits/ s'il n'existe pas.

Structure du fichier :
## BLOC 1 — INVENTAIRE DES MODULES CYTHON
## BLOC 2 — COHÉRENCE DES INTERFACES
## BLOC 3 — __init__.pyi ET __init__.py
## BLOC 4 — BUILD ET REPRODUCIBILITÉ
## BLOC 5 — STUBS DANS LES TESTS
## SYNTHÈSE

Tableau synthèse :
| ID | Bloc | Description | Fichier:Ligne | Sévérité | Impact | Effort |

Sévérité : 🔴 Critique · 🟠 Majeur · 🟡 Mineur.

Confirme dans le chat uniquement :
"✅ tasks/audits/audit_cython_alphaedge.md créé
 🔴 X · 🟠 X · 🟡 X"
