# /session-end — Résumé de fin de session

Génère un bilan structuré de la session courante et propose les mises à jour nécessaires.

## 1. Résumé technique

```
📋 Résumé session — <DATE>
─────────────────────────────────────────────
Fichiers modifiés  : <liste fichier:ligne>
Tests avant/après  : <baseline> → <actuel>
Ruff avant/après   : 0 → 0
Corrections        : <liste C-XX terminées>
Blocages           : <liste problèmes non résolus>
─────────────────────────────────────────────
```

## 2. Proposition leçon

Si un pattern notable a émergé pendant la session, générer un candidat d'entrée pour
`tasks/lessons.md` (format identique à `/lessons`).
Afficher — ne pas écrire automatiquement.

## 3. Proposition MAJ docs/ALPHAEDGE_STRUCTURAL_ACTION_PLAN.md

Si des dettes techniques ont été identifiées ou résolues :
- Proposer la suppression des items résolus
- Proposer l'ajout des nouvelles dettes découvertes
Afficher le diff — ne pas écrire automatiquement.

## 4. Vérification finale
```powershell
.\.venv\Scripts\Activate.ps1 ; make qa
```
Confirmer : 610+ tests · 0 Ruff · ALPHAEDGE_PAPER=true intact

## Règles
- Aucune écriture automatique — tout est proposé pour validation
- Commits → l'utilisateur committe lui-même (ne jamais exécuter git push)
