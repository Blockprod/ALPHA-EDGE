# Profil utilisateur — AlphaEdge

## Rôle
- Trader indépendant + développeur Python solo
- Expertise : Cython 3.0, IB Gateway, stratégies quantitatives (FCR / Momentum / Carry)
- Timezone : Europe/Paris (CET/CEST — DST-aware)

## Langue
- Français par défaut (sauf code, noms de variables, logs)
- No emoji (sauf si demandé explicitement)

## Style attendu
- Réponses courtes · citer fichier:ligne avant toute modification
- Proposer le diff avant d'agir · ne pas expliquer l'évident
- Senior engineer standards — pas de fix temporaires, causes racines uniquement

## Niveau d'autonomie
| Action | Autonomie |
|--------|-----------|
| Lire / explorer fichiers | OUI — sans demander |
| Modifier fichiers `.py`, `.md`, `.yaml` | OUI — sans demander |
| Exécuter `make qa` / `make test` | OUI — sans demander |
| Modifier architecture / `core/*.pyx` | NON — valider d'abord |
| Commits / `git push` | NON — l'utilisateur committe lui-même |


## Triggers de re-plan
- QA fail > 2 itérations → STOP + re-plan immédiat
- Doute sur le périmètre → poser 1 question max, pas de liste

## Baseline actuelle
- Tests : 610 · Ruff : 0 · Coverage : ≥80% sur config/ utils/ core/
- Broker : IB Gateway · Mode : Paper trading (ALPHAEDGE_PAPER=true)
