---
modele: sonnet-4.6
mode: agent
contexte: codebase
produit: PLAN_ACTION_audit_email_alerts_alphaedge_2026-03-25.md
derniere_revision: 2026-03-25
creation: 2026-03-25 à 18:30
---

# PLAN D'ACTION — ALPHAEDGE — 2026-03-25
Sources : `tasks/audits/resultats/audit_email_alerts_alphaedge.md`
Total : 🔴 2 · 🟠 3 · 🟡 3 · Effort estimé : 0.5 jour

---

## PHASE 1 — CRITIQUES 🔴

### [C-01] Appeler `alert_trade_executed()` après fill confirmé
Fichier : `alphaedge/engine/session_lifecycle.py:218` (fin de `_record_fill()`)
Problème : `_record_fill()` enregistre le fill en mémoire et logue `TRADE_ENTRY` via loguru, mais n'envoie aucune alerte. L'opérateur ne sait pas en temps réel qu'un trade a été ouvert.
Correction :
1. Ajouter `alert_trade_executed` aux imports existants depuis `alphaedge.utils.alerting`
2. À la fin de `_record_fill()`, après `self._persist_daily_state()`, ajouter :
   ```python
   asyncio.ensure_future(
       self._s._alert_manager.send_async(
           alert_trade_executed(
               pair=state.pair,
               direction="LONG" if bracket["direction"] == 1 else "SHORT",
               entry_price=bracket["entry_price"],
               lot_size=bracket["units"],
               sl_pips=signal["risk_pips"],
               spread_pips=spread_pips,
           )
       )
   ).add_done_callback(self._on_task_done)
   ```
Validation :
  make qa
  # Attendu : 574 passed, 0 erreurs ruff/mypy
Dépend de : Aucune
Statut : ⏳

---

### [C-02] Appeler `alert_trade_closed()` dans `_on_trade_closed()`
Fichier : `alphaedge/engine/session_lifecycle.py:358` (après `logger.info("TRADE_CLOSE ...")` dans `_reset_position()`)
Problème : `_on_trade_closed()` logue `TRADE_CLOSE` via loguru et écrit dans le CSV, mais n'envoie aucune alerte. L'opérateur ne sait pas en temps réel que la position a été clôturée ni quel en est le résultat (win/loss/pnl).
Correction :
1. Ajouter `alert_trade_closed` aux imports existants depuis `alphaedge.utils.alerting`
2. Dans `_reset_position()`, après le bloc `logger.info("TRADE_CLOSE | ...")` et avant `state.live_record = None`, ajouter :
   ```python
   asyncio.ensure_future(
       self._s._alert_manager.send_async(
           alert_trade_closed(
               pair=pair,
               direction="LONG" if record.direction == 1 else "SHORT",
               exit_price=exit_price,
               pnl_pips=record.pnl_pips,
               pnl_usd=record.pnl_usd,
               outcome=record.outcome,
               duration_s=duration_s if isinstance(duration_s, int) else 0,
           )
       )
   ).add_done_callback(self._on_task_done)
   ```
Validation :
  make qa
  # Attendu : 574 passed, 0 erreurs ruff/mypy
Dépend de : Aucune
Statut : ⏳

---

## PHASE 2 — MAJEURES 🟠

### [C-03] Corriger la sémantique du fill timeout (ligne 153)
Fichier : `alphaedge/engine/session_lifecycle.py:153-160`
Problème : Le fill timeout utilise `AlertEvent.TRADE_EXECUTED` avec `AlertLevel.WARNING`. Sémantique incorrecte : `TRADE_EXECUTED` implique un trade confirmé et ouvert. Un opérateur recevant cette alerte peut croire qu'il a une position ouverte alors que le bracket a été annulé.
Correction : Remplacer `AlertEvent.TRADE_EXECUTED` par `AlertEvent.KILL_SWITCH` n'est pas approprié non plus. Utiliser `AlertEvent.TRADE_EXECUTED` est le code event le plus proche disponible, mais corriger le `title` pour rendre explicite que c'est un échec de fill :
```python
Alert(
    event=AlertEvent.TRADE_EXECUTED,
    level=AlertLevel.WARNING,
    title=f"⏱️ Fill timeout — {state.pair} — NO POSITION OPENED",
    message="Order not filled within 10s. Bracket cancelled. No open position.",
)
```
Validation :
  make qa
  # Attendu : 574 passed, 0 erreurs ruff/mypy
Dépend de : Aucune
Statut : ⏳

---

### [C-04] Appeler `alert_ib_reconnected()` après reconnexion réussie
Fichier : `alphaedge/engine/session_lifecycle.py:396` (après `logger.info("ALPHAEDGE: Real-time feeds re-subscribed after reconnect")`)
Problème : Après une reconnexion IB réussie, `_handle_reconnection()` logue `INFO` mais n'envoie pas d'alerte. L'opérateur qui a reçu l'alerte `IB_DISCONNECTED` ne sait pas que le système s'est auto-rétabli.
Correction :
1. Ajouter `alert_ib_reconnected` aux imports existants depuis `alphaedge.utils.alerting`
2. Après `logger.info("ALPHAEDGE: Real-time feeds re-subscribed after reconnect")`, ajouter :
   ```python
   asyncio.ensure_future(
       self._s._alert_manager.send_async(alert_ib_reconnected())
   ).add_done_callback(self._on_task_done)
   ```
Validation :
  make qa
  # Attendu : 574 passed, 0 erreurs ruff/mypy
Dépend de : Aucune
Statut : ⏳

---

### [C-05] Appeler `alert_session_end_open()` / `alert_session_end_clean()` dans `_handle_session_end()`
Fichier : `alphaedge/engine/session_lifecycle.py` — méthode `_handle_session_end()`
Problème : `_handle_session_end()` détecte les positions ouvertes et logue des warnings mais n'envoie aucune alerte. Une fin de session avec position ouverte est un événement critique qui doit notifier l'opérateur sur mobile.
Correction :
1. Ajouter `alert_session_end_open`, `alert_session_end_clean` aux imports depuis `alphaedge.utils.alerting`
2. Après la boucle `for pos in positions` et la gestion `action`, ajouter :
   ```python
   if open_count > 0:
       action = self._s._config.trading.session_end_action
       asyncio.ensure_future(
           self._s._alert_manager.send_async(
               alert_session_end_open(
                   open_count=open_count,
                   action=action,
               )
           )
       ).add_done_callback(self._on_task_done)
   else:
       asyncio.ensure_future(
           self._s._alert_manager.send_async(
               alert_session_end_clean(
                   trades_today=self._s._global_trades_today,
                   pairs=list(self._s._config.trading.pairs),
               )
           )
       ).add_done_callback(self._on_task_done)
   ```
Validation :
  make qa
  # Attendu : 574 passed, 0 erreurs ruff/mypy
Dépend de : Aucune
Statut : ⏳

---

## PHASE 3 — MINEURES 🟡

### [C-06] Appeler `alert_signal_detected()` à la détection d'un signal valide
Fichier : `alphaedge/engine/session_lifecycle.py` — méthode `_execute_signal()` ou site d'appel dans la boucle principale
Problème : Aucune alerte n'est envoyée quand un signal est détecté et validé (avant exécution). L'opérateur n'a aucune visibilité sur les signaux identifiés — utile en paper trading pour valider la logique.
Correction :
1. Ajouter `alert_signal_detected` aux imports depuis `alphaedge.utils.alerting`
2. Au début de `_execute_signal()`, après la récupération du `pip_size` et confirmation du signal valide, ajouter :
   ```python
   asyncio.ensure_future(
       self._s._alert_manager.send_async(
           alert_signal_detected(
               pair=state.pair,
               direction="LONG" if signal.get("direction") == 1 else "SHORT",
               entry_price=signal.get("entry_price", 0.0),
           )
       )
   ).add_done_callback(self._on_task_done)
   ```
Validation :
  make qa
  # Attendu : 574 passed, 0 erreurs ruff/mypy
Dépend de : Aucune
Statut : ⏳

---

### [C-07] Appeler `alert_daily_summary()` à la fin de session
Fichier : `alphaedge/engine/session_lifecycle.py` — méthode `_handle_session_end()` (fin, après la boucle SUMMARY)
Problème : Pas de résumé journalier envoyé sur mobile. L'opérateur doit ouvrir les logs pour connaître le bilan (trades/wins/losses/PnL).
Correction :
1. Ajouter `alert_daily_summary` aux imports depuis `alphaedge.utils.alerting`
2. À la fin de `_handle_session_end()`, avant le `except`, calculer et envoyer :
   ```python
   total_pnl = sum(
       s.live_record.pnl_usd
       for s in self._s._states.values()
       if s.live_record and s.live_record.pnl_usd is not None
   )
   asyncio.ensure_future(
       self._s._alert_manager.send_async(
           alert_daily_summary(
               trades_today=self._s._global_trades_today,
               total_pnl_usd=total_pnl,
           )
       )
   ).add_done_callback(self._on_task_done)
   ```
Validation :
  make qa
  # Attendu : 574 passed, 0 erreurs ruff/mypy
Dépend de : C-05 (même méthode — appliquer après C-05)
Statut : ⏳

---

### [C-08] Ajouter un log INFO quand max_trades_per_session est atteint
Fichier : `alphaedge/engine/session_lifecycle.py:530, 629`
Problème : Quand le quota de trades journalier est atteint, la fonction retourne silencieusement sans aucun log. L'opérateur ne sait pas pourquoi plus aucun trade n'est pris.
Correction : Ajouter un log `INFO` (une seule fois, pas à chaque bar) avant chaque `return` :
```python
if (
    self._s._global_trades_today
    >= self._s._config.trading.max_trades_per_session
):
    logger.info(
        "ALPHAEDGE: Max trades/session reached ({}) — skipping {}",
        self._s._global_trades_today,
        pair,
    )
    return
```
> Note : Il faudra vérifier que ce log n'est pas émis à chaque bar pour éviter le spam. Utiliser un flag `_max_trades_logged` par paire si nécessaire.
Validation :
  make qa
  # Attendu : 574 passed, 0 erreurs ruff/mypy
Dépend de : Aucune
Statut : ⏳

---

## SÉQUENCE D'EXÉCUTION

```
C-01  # alert_trade_executed — critique — aucune dépendance
C-02  # alert_trade_closed — critique — aucune dépendance
C-03  # fill timeout sémantique — majeur — aucune dépendance
C-04  # alert_ib_reconnected — majeur — aucune dépendance
C-05  # alert_session_end — majeur — aucune dépendance
C-06  # alert_signal_detected — mineur — aucune dépendance
C-07  # alert_daily_summary — mineur — après C-05 (même méthode)
C-08  # log max_trades — mineur — aucune dépendance

→ make qa   # une seule fois après toutes les corrections
# Attendu : 574 passed · 0 ruff · 0 mypy
```

> Aucun fichier `.pyx` n'est modifié dans ce plan — `make build` n'est pas requis.

---

## CRITÈRES PASSAGE EN PRODUCTION

- [ ] Zéro 🔴 ouvert
- [ ] `make qa` : 100% pass (lint + mypy + pytest ≥80%)
- [ ] Zéro credential dans les logs loguru
- [ ] `ALPHAEDGE_PAPER=true` intact dans `.env.example`
- [ ] Bracket order `is_valid` vérifié avant envoi IB
- [ ] `check_daily_limit()` appelé chaque cycle
- [ ] Paper trading validé 5 sessions NYSE minimum

---

## TABLEAU DE SUIVI

| ID | Titre | Sévérité | Fichier | Effort | Statut | Date |
|----|-------|----------|---------|--------|--------|------|
| C-01 | `alert_trade_executed()` après fill | 🔴 Critique | `session_lifecycle.py:218` | 30 min | ✅ | 2026-03-25 |
| C-02 | `alert_trade_closed()` dans `_on_trade_closed` | 🔴 Critique | `session_lifecycle.py:358` | 30 min | ✅ | 2026-03-25 |
| C-03 | Fill timeout — corriger titre alerte | 🟠 Majeur | `session_lifecycle.py:153` | 15 min | ✅ | 2026-03-25 |
| C-04 | `alert_ib_reconnected()` après reconnexion | 🟠 Majeur | `session_lifecycle.py:396` | 15 min | ✅ | 2026-03-25 |
| C-05 | `alert_session_end_open/clean()` fin de session | 🟠 Majeur | `session_lifecycle.py:_handle_session_end` | 30 min | ✅ | 2026-03-25 |
| C-06 | `alert_signal_detected()` à chaque signal | 🟡 Mineur | `session_lifecycle.py:_execute_signal` | 30 min | ✅ | 2026-03-25 |
| C-07 | `alert_daily_summary()` fin de session | 🟡 Mineur | `session_lifecycle.py:_handle_session_end` | 30 min | ✅ | 2026-03-25 |
| C-08 | Log DEBUG max_trades/session atteint | 🟡 Mineur | `session_lifecycle.py:530, 629` | 15 min | ✅ | 2026-03-25 |
