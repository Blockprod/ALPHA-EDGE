# PLAN D'ACTION — ALPHAEDGE — 2026-03-22
Sources : `tasks/audits/audit_technical_alphaedge.md`
Total : 🔴 1 · 🟠 4 · 🟡 2 · Effort estimé : 3.5 jours

## PHASE 1 — CRITIQUES 🔴

### [C-01] Verrouiller la cohérence paper/live au chargement config
Fichier : alphaedge/config/loader.py:248
Problème : `is_paper` et `port` peuvent diverger car `ALPHAEDGE_PAPER` et `ALPHAEDGE_IB_PORT` sont lus séparément. Un état `is_paper=True` avec port `4001` reste possible, ce qui permet une soumission réelle d'ordres malgré un drapeau paper affiché comme vrai.
Correction :
- Centraliser la résolution paper/live dans `_build_ib_config()`.
- Si `is_paper=True`, forcer les ports live à être rejetés explicitement avec `ValueError` ou correction stricte vers `4002`.
- Si `is_paper=False`, forcer la cohérence vers `4001` ou échouer explicitement.
- Ajouter une validation explicite de couple `(is_paper, port)` dans le chargement config.
- Ajouter un test dédié pour les combinaisons incohérentes paper/live.
Validation :
  make qa
  # Attendu : config incohérente rejetée ou normalisée explicitement, 100% pass
Dépend de : Aucune
Statut : ✅ 2026-03-22

## PHASE 2 — MAJEURES 🟠

### [C-02] Rendre le chemin CLI `--mode live` auto-cohérent et non ambigu
Fichier : alphaedge/engine/strategy.py:313
Problème : Le chemin `--mode live` demande une confirmation interactive mais ne force pas lui-même `config.ib.is_paper = False` ni `port = 4001`. Le comportement final dépend encore des variables d'environnement chargées ensuite.
Correction :
- Après `load_config()`, appliquer explicitement la cohérence du mode CLI.
- Si `args.mode == "live"`, définir `config.ib.is_paper = False` et `config.ib.port = 4001`.
- Si `args.mode == "paper"`, conserver `config.ib.is_paper = True` et `config.ib.port = 4002`.
- Journaliser clairement le mode effectif final après normalisation.
- Ajouter un test ciblé du chemin CLI paper/live sans interaction réelle.
Validation :
  make qa
  # Attendu : mode CLI prioritaire et cohérent, 100% pass
Dépend de : C-01
Statut : ✅ 2026-03-22

### [C-03] Rebrancher durablement le hook de reconnexion après remplacement de l'instance IB
Fichier : alphaedge/engine/broker.py:203
Problème : `_on_disconnect()` remplace `self._ib` par une nouvelle instance `IB()`, mais le hook session `disconnectedEvent += self._lifecycle._on_ib_disconnect` a été branché une seule fois au démarrage sur l'ancienne instance. Les déconnexions ultérieures peuvent ne plus remonter au niveau stratégie.
Correction :
- Déplacer ou réappliquer le branchement de `disconnectedEvent` de façon sûre après toute recréation de `IB()`.
- Garantir que l'instance IB courante possède toujours les hooks broker + session.
- Ajouter un test qui simule une seconde déconnexion après reconnexion et vérifie que le handler session est toujours appelé.
Validation :
  make qa
  # Attendu : reconnect multi-cycle couvert, 100% pass
Dépend de : Aucune
Statut : ✅ 2026-03-22

### [C-04] Passer le contrôle de marge en fail-closed
Fichier : alphaedge/engine/broker.py:318
Problème : `_check_margin()` retourne `True` si `accountSummary()` échoue. En cas d'incident IB sur le résumé de compte, `place_bracket_order()` peut continuer vers `placeOrder()` sans validation de marge.
Correction :
- Changer le comportement d'exception de `_check_margin()` pour bloquer la soumission (`False`) au lieu de l'autoriser.
- Différencier éventuellement `paper` et `live` si nécessaire, mais ne jamais autoriser silencieusement la soumission quand la vérification a échoué.
- Ajouter un test vérifiant que `place_bracket_order()` retourne `[]` quand la lecture marge échoue.
Validation :
  make qa
  # Attendu : aucune soumission en cas d'échec margin check, 100% pass
Dépend de : C-01
Statut : ✅ 2026-03-22

### [C-05] Ajouter une couverture de tests dédiée à la séparation paper/live
Fichier : alphaedge/tests/:À ESTIMER
Problème : Aucun test dédié ne couvre la cohérence `ALPHAEDGE_PAPER`/port, ni le chemin CLI `--mode live`, ni la protection contre les états incohérents.
Correction :
- Créer un fichier de tests dédié, par exemple `alphaedge/tests/test_paper_live_separation.py`.
- Couvrir les cas :
  - `ALPHAEDGE_PAPER=true` + port `4002` → OK
  - `ALPHAEDGE_PAPER=true` + port `4001` → rejet ou normalisation explicite
  - `--mode live` → force `is_paper=False` et port `4001`
  - `--mode paper` → force `is_paper=True` et port `4002`
- Vérifier aussi que les logs de démarrage reflètent le mode effectif final.
Validation :
  make qa
  # Attendu : scénarios paper/live couverts, 100% pass
Dépend de : C-01, C-02
Statut : ✅ 2026-03-22

## PHASE 3 — MINEURES 🟡

### [C-06] Masquer `account_id` dans la représentation de `IBConfig`
Fichier : alphaedge/config/loader.py:134
Problème : `IBConfig` est une dataclass standard dont `repr` expose `account_id` si l'objet est loggé ou affiché en debug.
Correction :
- Masquer `account_id` dans la dataclass, par exemple `field(repr=False)`.
- Si nécessaire, ajouter une représentation sûre dédiée qui conserve les champs non sensibles (`host`, `port`, `is_paper`).
- Ajouter un test simple qui vérifie que `repr(IBConfig(...))` ne contient pas l'account ID.
Validation :
  make qa
  # Attendu : aucune fuite d'account_id dans repr, 100% pass
Dépend de : Aucune
Statut : ✅ 2026-03-22

### [C-07] Renforcer la validation du state persistant au chargement
Fichier : alphaedge/utils/state_persistence.py:68
Problème : `load_daily_state()` valide le parse JSON et la date, mais accepte encore un JSON sémantiquement incohérent tant qu'il peut être injecté dans `DailyState(**data)`.
Correction :
- Ajouter une validation stricte du schéma chargé : types, bornes minimales, valeurs attendues.
- Vérifier explicitement `trades_today >= 0`, `starting_equity >= 0`, `open_pairs` liste de chaînes, `shutdown_triggered` bool.
- Rejeter et logger les états mal formés avant instanciation.
- Ajouter un test dédié avec JSON valide mais types incohérents.
Validation :
  make qa
  # Attendu : états mal formés ignorés proprement, 100% pass
Dépend de : Aucune
Statut : ✅ 2026-03-22

## SÉQUENCE D'EXÉCUTION
1. C-01 — verrou cohérence `is_paper`/port dans `loader.py`
2. C-02 — normalisation explicite du mode CLI dans `strategy.py`
3. C-05 — tests dédiés paper/live pour verrouiller C-01 et C-02
4. C-03 — rebinding durable des hooks `disconnectedEvent`
5. C-04 — fail-closed sur `_check_margin()`
6. C-06 — masquage `account_id` dans `repr`
7. C-07 — validation stricte du state persistant

Toujours `make build` avant `make qa` si `.pyx` touché.
Ici, aucun `.pyx` n'est ciblé dans ce plan.

## CRITÈRES PASSAGE EN PRODUCTION
- [ ] Zéro 🔴 ouvert
- [ ] make qa : 100% pass (lint + mypy + pytest ≥80%)
- [ ] Zéro credential dans les logs loguru
- [ ] ALPHAEDGE_PAPER=true intact dans .env.example
- [ ] Bracket order is_valid vérifié avant envoi IB
- [ ] check_daily_limit() appelé chaque cycle
- [ ] Paper trading validé 5 sessions NYSE minimum

## TABLEAU DE SUIVI
| ID | Titre | Sévérité | Fichier | Effort | Statut | Date |
|----|-------|----------|---------|--------|--------|------|
| C-01 | Verrou cohérence paper/live config | 🔴 | alphaedge/config/loader.py | 0.75 jour | ✅ | 2026-03-22 |
| C-02 | Normaliser explicitement le mode CLI | 🟠 | alphaedge/engine/strategy.py | 0.5 jour | ✅ | 2026-03-22 |
| C-03 | Rebrancher durablement les hooks disconnect | 🟠 | alphaedge/engine/broker.py ; alphaedge/engine/strategy.py | 0.75 jour | ✅ | 2026-03-22 |
| C-04 | Passer le margin check en fail-closed | 🟠 | alphaedge/engine/broker.py | 0.5 jour | ✅ | 2026-03-22 |
| C-05 | Ajouter les tests paper/live manquants | 🟠 | alphaedge/tests/test_paper_live_separation.py | 0.5 jour | ✅ | 2026-03-22 |
| C-06 | Masquer account_id dans repr IBConfig | 🟡 | alphaedge/config/loader.py | 0.25 jour | ✅ | 2026-03-22 |
| C-07 | Valider strictement le state JSON chargé | 🟡 | alphaedge/utils/state_persistence.py | 0.25 jour | ✅ | 2026-03-22 |
