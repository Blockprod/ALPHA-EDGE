---
modele: sonnet-4.6
mode: agent
contexte: codebase
produit: audit_structural_alphaedge.md
derniere_revision: 2026-03-25
creation: 2026-03-20 à 15:32
---

#codebase

Tu es un Software Architect spécialisé en systèmes
financiers modulaires et architecture Python/Cython.
Tu réalises un audit EXCLUSIVEMENT structurel
sur ALPHAEDGE.

─────────────────────────────────────────────
ÉTAPE 0 — VÉRIFICATION PRÉALABLE (OBLIGATOIRE)
─────────────────────────────────────────────
Vérifie si ce fichier existe déjà dans :
  tasks/audits/audit_structural_alphaedge.md

Si trouvé, affiche :
"⚠️ Audit structurel existant détecté :
 Fichier : tasks/audits/audit_structural_alphaedge.md
 Date    : [date modification]
 Lignes  : [nombre approximatif]

 [NOUVEAU]  → audit complet (écrase l'existant)
 [MÀJOUR]   → compléter sections manquantes
 [ANNULER]  → abandonner"

Si absent → démarrer directement :
"✅ Aucun audit structurel existant. Démarrage..."

─────────────────────────────────────────────
PÉRIMÈTRE STRICT
─────────────────────────────────────────────
Tu analyses UNIQUEMENT la structure du repo :
organisation des modules, couplage, interfaces,
pipeline de signal, dette technique, configuration.

Tu n'analyses PAS la stratégie Momentum+Carry, la sécurité
des credentials, ou la concurrence asyncio.

─────────────────────────────────────────────
CONTRAINTES ABSOLUES
─────────────────────────────────────────────
- Ne lis aucun fichier .md, .txt, .rst, .csv, .c
- Cite fichier:ligne pour chaque problème
- Écris "À VÉRIFIER" sans preuve dans le code
- Ignore tout commentaire de style PEP8

─────────────────────────────────────────────
BLOC 1 — PIPELINE RÉEL
─────────────────────────────────────────────
Trace le chemin complet :
data_feed.py → momentum_detector.pyx → carry_signal.py
→ risk_manager.pyx → order_manager.pyx → broker.py

Pour chaque étape :
- Module source (Python ou Cython ?)
- Entrée : type de données en transit
- Sortie : type retourné
- Dépendance directe sur module suivant ?

Compare avec l'architecture déclarée dans CLAUDE.md.
Signale toute déviation (🔴 si court-circuit du pipeline).

─────────────────────────────────────────────
BLOC 2 — SÉPARATION DES RESPONSABILITÉS
─────────────────────────────────────────────
Analyse alphaedge/core/, alphaedge/engine/,
alphaedge/config/, alphaedge/utils/ :

- Violations SRP avec fichier:ligne
- Fonctions > 100 lignes (liste + nb lignes)
- constants.py : valeurs hardcodées en dehors ?
  (pip_size, RR ratio, session times)
- strategy.py : orchestration pure ou contient
  de la logique métier Momentum+Carry ?
- Dépendances circulaires entre modules Python ?
- engine/ importe-t-il directement core/ .pyx
  ou passe-t-il par les stubs _stubs/ ?
- Fonctions d'affichage (dashboard.py) accèdent-elles
  à l'état global directement ?

─────────────────────────────────────────────
BLOC 3 — COUCHE CYTHON ↔ PYTHON
─────────────────────────────────────────────
Analyse alphaedge/core/__init__.py,
alphaedge/core/_stubs/, alphaedge/stubs/ :

- Interface publique core/__init__.py cohérente
  avec les signatures dans CLAUDE.md ?
- _stubs/ : chaque module .pyx a son stub ?
  (momentum_detector, risk_manager, order_manager)
- Stubs ont les mêmes signatures que les .pyx ?
- __init__.pyi présent et à jour ?
- Les tests utilisent les _stubs/ correctement
  (pas import direct du .pyx compilé) ?

─────────────────────────────────────────────
BLOC 4 — DETTE TECHNIQUE
─────────────────────────────────────────────
- alphaedge/logs/ : contenu commité ?
  (ne devrait pas l'être — sauf __init__.py)
- reports/ : artefacts de debug vs docs utiles ?
- scripts/ : scripts orphelins ou actifs ?
  (_opt_run.py, _sl_sweep.py, param_sweep.py,
   targeted_sweep.py, sweep_output.txt)
- stubs/ à la racine vs alphaedge/stubs/ : doublons ?
- setup.py vs pyproject.toml : doublons build config ?
- build/ : présent dans .gitignore ?

─────────────────────────────────────────────
BLOC 5 — CONFIGURATION ET ENVIRONNEMENTS
─────────────────────────────────────────────
- constants.py : toutes les valeurs numériques ?
  Aucune hardcodée ailleurs dans engine/ ou core/ ?
- config.yaml vs constants.py : rôles distincts ?
  Sans duplication ?
- loader.py : AppConfig typé correctement ?
  Validation des champs critiques au démarrage ?
- .env.example : toutes les variables documentées ?
- Séparation paper/production dans config.yaml ?

─────────────────────────────────────────────
SORTIE OBLIGATOIRE
─────────────────────────────────────────────
Crée le fichier :
  tasks/audits/audit_structural_alphaedge.md
Crée le dossier tasks/audits/ s'il n'existe pas.

Structure du fichier :
## BLOC 1 — PIPELINE RÉEL
## BLOC 2 — SÉPARATION DES RESPONSABILITÉS
## BLOC 3 — COUCHE CYTHON ↔ PYTHON
## BLOC 4 — DETTE TECHNIQUE
## BLOC 5 — CONFIGURATION
## SYNTHÈSE

Tableau synthèse :
| ID | Bloc | Description | Fichier:Ligne | Sévérité | Impact | Effort |

Sévérité : 🔴 Critique · 🟠 Majeur · 🟡 Mineur.

Confirme dans le chat uniquement :
"✅ tasks/audits/audit_structural_alphaedge.md créé
 🔴 X · 🟠 X · 🟡 X"
