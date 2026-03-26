---
modele: sonnet-4.6
mode: agent
contexte: codebase
produit: PLAN_ACTION_audit_ai_best_practices_alphaedge_2026-03-26.md
derniere_revision: 2026-03-26
creation: 2026-03-26 à 00:00
---

# PLAN D'ACTION — AI BEST PRACTICES — ALPHAEDGE — 2026-03-26
Sources : `tasks/audits/resultats/audit_ai_best_practices_alphaedge.md`
Total : 🔴 3 · 🟠 3 · 🟡 3 · Effort estimé : ~13h

---

## PHASE 1 — CRITIQUES 🔴

### [C-01] Créer `.claude/settings.json` avec hooks système
**Finding :** GAP-01
**Fichier cible :** `.claude/settings.json` (à créer)
**Problème :** Les Hard Stops de `CLAUDE.md`/`.claude/rules.md` sont déclaratifs. Un agent
peut les ignorer. Aucun mécanisme déterministe ne bloque `make build` sans `.pyx` modifié,
ni ne lance `ruff check` automatiquement après chaque écriture.
**Correction :**
1. Créer `.claude/settings.json` avec :
   - `permissions.allow` : `make qa`, `make test`, `make build`
   - `permissions.deny` : `git push --force`, `rm -rf *`
   - `PostToolUse.Write` → lancer `ruff check $FILE`
   - `PreCommit` → lancer `scripts/pre_commit_guard.py`
   - `SessionStart` → afficher le compte de tests baseline
   - `env.MAX_THINKING_TOKENS` : 15000
   - `env.CLAUDE_AUTOCOMPACT_PCT_OVERRIDE` : 60

2. Créer `scripts/pre_commit_guard.py` qui vérifie :
   - Pas de `ALPHAEDGE_PAPER=false` dans les fichiers stagés
   - Pas de `# type: ignore` dans les fichiers stagés
   - Pas de `.env` dans les fichiers stagés

**Validation :**
```powershell
# Vérifier que le fichier est bien formé JSON
python -c "import json; json.load(open('.claude/settings.json')); print('JSON OK')"
# Vérifier que le guard script s'exécute sans erreur sur le repo courant
python scripts/pre_commit_guard.py
make qa
# Attendu : 610+ tests pass · 0 Ruff
```
**Dépend de :** Aucune
**Statut :** ✅ 2026-03-26

---

### [C-02] Créer `.claude/commands/` avec 6 slash commands
**Finding :** GAP-02
**Fichier cible :** `.claude/commands/` (dossier à créer + 6 fichiers)
**Problème :** Les prompts de workflows sont passifs dans `tasks/`. Aucun répertoire
`.claude/commands/`. L'invocation d'un workflow standard nécessite 2 minutes de navigation.
**Correction :**
Créer les 6 fichiers suivants dans `.claude/commands/` :

1. `qa.md` — Lance `make qa`, affiche le résumé pass/fail + liste les erreurs si FAIL
2. `audit.md` — Pipeline A→B→C complet : lit le skill `audit-workflow`, guide l'agent
   étape par étape (prompt audit → résultat → plan → exécution)
3. `backtest.md` — Lance le backtest avec les params actuels via skill `run-backtest`
4. `fix.md` — Pipeline P1→P5 (SCAN → PLAN → FIX → VERIFY → FINAL QA) en lisant
   les 5 prompts de `tasks/audits/fix_errors/`
5. `lessons.md` — Affiche `tasks/lessons.md` + propose une nouvelle entrée à valider
6. `session-end.md` — Génère résumé de session (fichiers modifiés, tests avant/après,
   leçon proposée) + propose mise à jour `docs/ALPHAEDGE_STRUCTURAL_ACTION_PLAN.md`

**Validation :**
```powershell
# Vérifier que les 6 fichiers sont présents
Get-ChildItem .claude/commands/ | Select-Object Name
# Attendu : 6 fichiers .md
```
**Dépend de :** Aucune
**Statut :** ✅ 2026-03-26

---

### [C-03] Créer `.claude/about-me.md`
**Finding :** GAP-03
**Fichier cible :** `.claude/about-me.md` (à créer)
**Problème :** L'agent doit lire 340 lignes de `CLAUDE.md` pour inférer le profil
utilisateur. Le style de communication, le niveau d'autonomie et la langue ne sont pas
déclarés explicitement dans un fichier dédié.
**Correction :**
Créer `.claude/about-me.md` avec les sections :
- **Rôle :** trader indépendant + développeur Python solo · expertise Cython / IB Gateway
- **Timezone :** Europe/Paris (CET/CEST) — DST-aware
- **Style attendu :** réponses courtes · citer fichier:ligne · français sauf code · no emoji
- **Niveau d'autonomie :**
  - Modifications fichiers → OUI sans demander
  - Exécution `make qa` → OUI sans demander
  - Modifications architecture → NON: valider d'abord
  - Commits / push → NON: l'utilisateur committe lui-même
- **Triggers de re-plan :** si QA fail > 2 itérations → STOP + re-plan

**Validation :** Vérification manuelle du contenu — pas de `make qa` requis.
**Dépend de :** Aucune
**Statut :** ✅ 2026-03-26

---

## PHASE 2 — MAJEURES 🟠

### [C-04] Créer `.mcp.json` avec GitHub MCP
**Finding :** GAP-04
**Fichier cible :** `.mcp.json` (à créer)
**Problème :** Aucun serveur MCP configuré. L'agent ne peut pas créer de PRs, lire
les diffs GitHub ni interagir avec les issues depuis le pipeline d'agent.
**Correction :**
1. Vérifier que `npx` est disponible (`node --version`)
2. Créer `.mcp.json` à la racine :
   ```json
   {
     "mcpServers": {
       "github": {
         "type": "stdio",
         "command": "npx",
         "args": ["-y", "@anthropic/mcp-github"],
         "env": {"GITHUB_TOKEN": "${GITHUB_TOKEN}"}
       }
     }
   }
   ```
3. Ajouter `GITHUB_TOKEN` dans `.env.example` (valeur vide, commentée)
4. Vérifier que `.mcp.json` est dans `.gitignore` si GITHUB_TOKEN est inline
   (ou utiliser la référence `${GITHUB_TOKEN}` via env — préférable)

**Validation :**
```powershell
# Test de connexion MCP
python -c "import json; j=json.load(open('.mcp.json')); print('MCP config OK:', list(j['mcpServers'].keys()))"
```
**Dépend de :** `GITHUB_TOKEN` dans l'env local
**Statut :** ✅ 2026-03-26

---

### [C-05] Créer `alphaedge/cache/sessions.jsonl` + `audit_index.json`
**Finding :** GAP-05
**Fichier cible :** `alphaedge/cache/sessions.jsonl` + `alphaedge/cache/audit_index.json`
**Problème :** La mémoire du projet est entièrement file-based et non queryable. Impossible
de tracker l'évolution du nombre de tests, des corrections ou des patterns récurrents entre
sessions.
**Correction :**
1. Créer `alphaedge/cache/sessions.jsonl` — format une ligne JSON par session :
   ```json
   {"date": "2026-03-26", "tests": 610, "ruff": 0, "pyright": 0, "fixes": 7, "blockers": 0, "notes": "C-01 à C-07 terminés"}
   ```
2. Créer `alphaedge/cache/audit_index.json` — index de tous les audits complétés :
   ```json
   [
     {"id": "master", "date": "2026-03-27", "findings": {"rouge": 0, "orange": 2, "jaune": 5}, "corrections": 7, "statut": "complet"},
     ...
   ]
   ```
3. Ajouter `alphaedge/cache/*.jsonl` et `alphaedge/cache/*.json` dans `.gitignore`
   (données runtime, pas committées)
4. Remplir `audit_index.json` avec les 13 audits déjà réalisés

**Validation :**
```powershell
python -c "
import json
lines = open('alphaedge/cache/sessions.jsonl').readlines()
print(f'Sessions: {len(lines)}')
idx = json.load(open('alphaedge/cache/audit_index.json'))
print(f'Audits indexés: {len(idx)}')
"
make qa
# Attendu : 610+ tests pass · 0 Ruff
```
**Dépend de :** Aucune
**Statut :** ✅ 2026-03-26

---

### [C-06] Créer `make bench` + `test_pipeline_latency.py`
**Finding :** GAP-06
**Fichier cible :** `Makefile` (modifier) + `alphaedge/tests/test_pipeline_latency.py` (créer)
**Problème :** La latence du pipeline signal → order n'est pas mesurée ni contractualisée.
Une régression de performance post-refactoring n'est pas détectée par `make qa`.
**Correction :**
1. Ajouter dans `Makefile` :
   ```makefile
   bench:
       python -m pytest alphaedge/tests/ -k "latency" -q --tb=short
   ```
2. Créer `alphaedge/tests/test_pipeline_latency.py` avec :
   - Un test qui mesure le temps d'exécution du cycle `detect_momentum → calculate_position_size → create_bracket_order` via les stubs `_stubs/`
   - Seuil : < 100ms (assertion via `time.perf_counter`)
   - Convention : `test_<module>_<scenario>.py` → `test_pipeline_latency_signal_to_order.py`

**Validation :**
```powershell
make bench
# Attendu : 1+ tests pass · latence < 100ms confirmée
make qa
# Attendu : 610+ tests pass · 0 Ruff (le nouveau test s'y ajoute)
```
**Dépend de :** Aucune
**Statut :** ✅ 2026-03-26

---

## PHASE 3 — MINEURES 🟡

### [C-07] Créer `feature_schema.py` + test contrat ML
**Finding :** GAP-07
**Fichier cible :** `alphaedge/engine/feature_schema.py` (créer) + `alphaedge/tests/test_ml_filter_schema.py` (créer)
**Problème :** `ml_filter.py` et `regime_filter.py` produisent des features sans schéma
explicite. Régression silencieuse possible si une feature change de type ou disparaît.
**Correction :**
1. Créer `alphaedge/engine/feature_schema.py` avec un `TypedDict` documentant les features
   ML attendues en entrée et en sortie du `MLFilter`
2. Créer `alphaedge/tests/test_ml_filter_schema.py` qui instancie le filtre avec des
   données mock et vérifie que le output respecte le schéma TypedDict

**Validation :**
```powershell
make qa
# Attendu : 611+ tests pass · 0 Ruff
```
**Dépend de :** Aucune
**Statut :** ✅ 2026-03-26

---

### [C-08] Ajouter ADR-009 + `test_regime_filter_contract.py`
**Finding :** GAP-08
**Fichier cible :** `architecture/decisions.md` (modifier) + `alphaedge/tests/test_regime_filter_contract.py` (créer)
**Problème :** `engine/regime_filter.py` n'a pas de spec comportementale ni d'ADR.
Peut être modifié sans contrat de régression. Son rôle dans le pipeline n'est pas documenté.
**Correction :**
1. Ajouter ADR-009 dans `architecture/decisions.md` :
   - Titre : "Regime Classifier — rôle et contrat dans le pipeline"
   - Décision : le regime classifier est un module de filtrage obligatoire entre le signal
     momentum et la décision d'entrée ; il peut retourner BULL / BEAR / SIDEWAYS / UNKNOWN
   - Conséquences : tout trade en régime UNKNOWN est bloqué par défaut
2. Créer `alphaedge/tests/test_regime_filter_contract.py` avec les 4 cas limites

**Validation :**
```powershell
make qa
# Attendu : 612+ tests pass · 0 Ruff
```
**Dépend de :** Aucune
**Statut :** ✅ 2026-03-26

---

### [C-09] Hook SessionEnd → auto-update `lessons.md`
**Finding :** GAP-09
**Fichier cible :** `.claude/settings.json` (modifier — ajouter hook SessionEnd)
**Problème :** `tasks/lessons.md` est mis à jour manuellement. Les leçons ne sont pas
capturées si l'utilisateur oublie de les demander en fin de session.
**Correction :**
Ajouter dans `.claude/settings.json` un `SessionEnd` hook qui :
1. Liste les fichiers modifiés pendant la session
2. Génère un candidat d'entrée `lessons.md` basé sur les corrections appliquées
3. Affiche le candidat en fin de session pour validation manuelle (pas d'écriture auto)

**Validation :** Test manuel — vérifier qu'en fin de session, un candidat leçon est proposé.
**Dépend de :** C-01 (`.claude/settings.json` doit exister)
**Statut :** ✅ 2026-03-26

---

## SÉQUENCE D'EXÉCUTION

```
C-03  → immédiat, 20 min (zéro dépendance, impact immédiat)
C-02  → immédiat, 1h (zéro dépendance, impact immédiat)
C-01  → après C-02, 2h (hooks — inclut SessionEnd si C-09 concurrent)
C-09  → concurrent avec C-01 (même fichier settings.json)
C-04  → après C-01, 1h (nécessite node/npx)
C-05  → parallèle avec C-04, 1h (indépendant)
C-06  → après C-05, 2h (latency test — utilise les stubs existants)
C-07  → après C-06, 3h (feature schema — lit ml_filter.py d'abord)
C-08  → parallèle avec C-07, 2h (ADR + test régime)
```

**Ordre recommandé :**
1. C-03 — about-me.md (20 min, impact immédiat sur calibrage agent)
2. C-02 — slash commands (1h, impact immédiat sur friction)
3. C-01 + C-09 — settings.json avec tous les hooks (2h)
4. C-05 — memory queryable (1h, indépendant)
5. C-04 — MCP GitHub (1h, requiert node)
6. C-06 — latency benchmark (2h)
7. C-07 — feature schema (3h)
8. C-08 — regime classifier contrat (2h)

> ⚠️ Aucun `.pyx` modifié dans ce plan — `make build` non requis.
> ⚠️ C-04 requiert `node` + `npx` installés et un `GITHUB_TOKEN` valide dans l'env local.
