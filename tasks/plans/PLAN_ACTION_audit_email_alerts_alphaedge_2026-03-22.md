# PLAN D'ACTION — ALPHAEDGE — 2026-03-22
Sources : `tasks/audits/audit_email_alerts_alphaedge.md`
Total : 🔴 1 · 🟠 5 · 🟡 4 · ⚪ 1 · Effort estimé : ~1.5 jours

---

## PHASE 1 — CRITIQUES 🔴

### [C-01] Connecter AlertManager au pipeline live

Fichier : `alphaedge/config/loader.py` + `alphaedge/engine/strategy.py` + `alphaedge/engine/session_lifecycle.py` + `alphaedge/engine/broker.py`
Problème : `alerting.py` n'est importé que par `test_alerting.py`. `AppConfig` ne contient pas de champ `alerting`. `AlertManager` n'est jamais instancié. Zéro alerte reçue en production quelle que soit la configuration `config.yaml`.
Correction :
  1. Dans `loader.py` : ajouter un champ `alerting: dict[str, object]` dans `AppConfig` et le peupler depuis la section `alerting:` de `config.yaml`.
  2. Dans `strategy.py` : après le chargement de la config, appeler `build_alert_config(config.alerting)` et instancier `AlertManager(alert_config)`. Passer l'instance à `SessionLifecycle` et `Broker` via leurs constructeurs ou méthode `set_alert_manager()`.
  3. Dans `session_lifecycle.py` et `broker.py` : accepter et stocker le paramètre `alert_manager: AlertManager | None`.
Validation :
  ```powershell
  make qa
  # Attendu : 504 tests pass, 0 ruff, 0 pyright
  # Test spécifique : test_alerting.py doit toujours passer
  # Vérifier : `from alphaedge.utils.alerting import AlertManager` présent dans strategy.py
  ```
Dépend de : Aucune
Statut : ✅ 2026-03-22

---

## PHASE 2 — MAJEURES 🟠

### [C-02] Retry avec backoff exponentiel sur Telegram et Discord

Fichier : `alphaedge/utils/alerting.py:193,231`
Problème : `send_telegram()` et `send_discord()` n'effectuent qu'une seule tentative. En cas d'échec réseau temporaire (timeout, API surchargée), la notification est définitivement perdue.
Correction : Entourer l'appel `urlopen` d'une boucle de 3 tentatives maximum avec backoff exponentiel (1s → 2s → 4s). Utiliser `time.sleep()` entre les tentatives. Conserver le comportement non-bloquant (les exceptions sont mangées après le dernier retry). Logger chaque retry avec niveau WARNING.
Exemple de structure :
  ```python
  for attempt in range(1, 4):
      try:
          with urlopen(req, timeout=10) as resp:
              return bool(resp.status == 200)
      except (URLError, OSError) as exc:
          if attempt == 3:
              logger.error(f"Telegram alert failed after 3 attempts: {exc}")
              return False
          logger.warning(f"Telegram alert attempt {attempt} failed, retrying: {exc}")
          time.sleep(2 ** (attempt - 1))
  return False
  ```
Validation :
  ```powershell
  make qa
  # Attendu : 504 tests pass
  # Vérifier : test_alerting.py passe sans modification
  ```
Dépend de : Aucune (modification interne de alerting.py)
Statut : ⏳

### [C-03] Cooldown anti-tempête dans AlertManager

Fichier : `alphaedge/utils/alerting.py:248`
Problème : `AlertManager` n'a aucun cooldown par `AlertEvent`. Si C-01 est résolu et que le pipeline IB entre en retry loop (reconnexion toutes les 5s), `alert_ib_disconnected()` pourrait générer des dizaines de notifications par minute.
Correction : Ajouter un champ `_last_sent: dict[AlertEvent, datetime]` et un paramètre de classe `cooldown_seconds: dict[AlertEvent, int]` avec des valeurs par défaut. Dans `AlertManager.send()`, vérifier que `now - _last_sent[event] >= cooldown_seconds[event]` avant d'envoyer. Si en cooldown, logger DEBUG et retourner sans envoyer.
Valeurs par défaut suggérées :
  - `IB_DISCONNECTED`: 120s (max 1 alerte toutes les 2 minutes)
  - `IB_RECONNECTED`: 60s
  - `KILL_SWITCH`: 300s (une seule fois par session suffira)
  - Tous les autres : 30s par défaut
Validation :
  ```powershell
  make qa
  # Attendu : 504 tests pass
  ```
Dépend de : Aucune (modification interne de alerting.py)
Statut : ⏳

### [C-04] Alerter lors du déclenchement du kill switch (daily loss)

Fichier : `alphaedge/engine/session_lifecycle.py:522`
Problème : `_check_daily_loss_shutdown()` logue un warning via loguru et déclenche le shutdown, mais n'envoie aucune alerte externe. Le trader n'est pas notifié que le bot s'est arrêté pour protection du capital.
Correction : Après le `logger.warning(...)` et avant (ou après) `self._shutdown_requested = True`, appeler :
  ```python
  if self._alert_manager is not None:
      await self._alert_manager.send_async(
          alert_kill_switch(pair=state.pair, reason=result["reason"], daily_pnl_pct=result["daily_pnl_pct"]),
          loop=asyncio.get_event_loop(),
      )
  ```
Validation :
  ```powershell
  make qa
  # Attendu : 504 tests pass
  # Vérifier : le daily loss limit test existant ne régresse pas
  ```
Dépend de : C-01
Statut : ⏳

### [C-05] Alerter lors de la déconnexion IB Gateway

Fichier : `alphaedge/engine/session_lifecycle.py:234` + `alphaedge/engine/broker.py:234`
Problème : `_on_ib_disconnect()` logue `logger.critical(...)` uniquement. Les erreurs 1100/1101/1102 dans `broker.py:234` sont identiques — loguru only.
Correction : Dans `session_lifecycle.py:_on_ib_disconnect()`, après le `logger.critical(...)` :
  ```python
  if self._alert_manager is not None:
      asyncio.create_task(
          self._alert_manager.send_async(
              alert_ib_disconnected(pair=state.pair if state else "N/A"),
              loop=asyncio.get_event_loop(),
          )
      )
  ```
  Dans `broker.py` : idem pour les erreurs 1100-1102 dans `_on_ib_error()`.
Validation :
  ```powershell
  make qa
  # Attendu : 504 tests pass
  ```
Dépend de : C-01
Statut : ⏳

### [C-07] Alerter lors de l'échec de reconnexion IB

Fichier : `alphaedge/engine/session_lifecycle.py:254`
Problème : `_handle_reconnection()` logue `logger.critical("Reconnection FAILED")` et déclenche un shutdown silencieux. Des positions ouvertes peuvent exister.
Correction : Après le `logger.critical(...)` de reconnexion échouée, appeler `alert_ib_disconnected()` avec un message spécifique "Reconnection FAILED after 3 attempts — manual intervention required".
Validation :
  ```powershell
  make qa
  # Attendu : 504 tests pass
  ```
Dépend de : C-01
Statut : ⏳

---

## PHASE 3 — MINEURES 🟡

### [C-06] Alerter lors du timeout fill (> 10 s)

Fichier : `alphaedge/engine/session_lifecycle.py:133`
Problème : `_submit_and_await_fill()` logue `logger.error("Parent order not filled within 10s")` et retourne `None`. L'ordre est annulé sans notification externe.
Correction : Dans le bloc `except TimeoutError`, après `logger.error(...)` :
  ```python
  if self._alert_manager is not None:
      asyncio.create_task(
          self._alert_manager.send_async(
              Alert(
                  event=AlertEvent.TRADE_EXECUTED,
                  level=AlertLevel.WARNING,
                  title=f"⏱️ Fill timeout — {pair}",
                  message=f"Order not filled within 10s. Cancelled.",
              ),
              loop=asyncio.get_event_loop(),
          )
      )
  ```
  Note : Si un `AlertEvent.FILL_TIMEOUT` dédié est souhaitable, l'ajouter à l'enum `AlertEvent` dans `alerting.py`.
Validation :
  ```powershell
  make qa
  # Attendu : 504 tests pass
  ```
Dépend de : C-01
Statut : ⏳

### [C-08] Ajouter lot_size au contenu de alert_trade_executed

Fichier : `alphaedge/utils/alerting.py:336`
Problème : `alert_trade_executed()` construit un message avec `entry_price`, `stop_loss`, `take_profit` mais pas `lot_size`. Pour une vérification manuelle rapide sur mobile, la taille de position est indispensable.
Correction : Ajouter un paramètre `lot_size: float` à la signature de `alert_trade_executed()` et l'inclure dans le message formaté.
Validation :
  ```powershell
  make qa
  # Attendu : 504 tests pass
  # Vérifier : test_alerting.py passe avec le paramètre ajouté
  ```
Dépend de : Aucune
Statut : ⏳

### [C-09] Ajouter le code erreur IB à alert_ib_disconnected

Fichier : `alphaedge/utils/alerting.py:395`
Problème : `alert_ib_disconnected()` génère un message générique sans code d'erreur IB ni contexte. Impossible de diagnostiquer la cause sans ouvrir les logs.
Correction : Ajouter un paramètre optionnel `error_code: int | None = None` et `error_msg: str | None = None` à `alert_ib_disconnected()`. Si fournis, les inclure dans le message.
Validation :
  ```powershell
  make qa
  # Attendu : 504 tests pass
  ```
Dépend de : Aucune
Statut : ⏳

### [C-10] Préfixe [PAPER] / [LIVE] dans les alertes

Fichier : `alphaedge/utils/alerting.py:96` + `alphaedge/utils/alerting.py` (AlertConfig ou AlertManager)
Problème : `AlertConfig` et `AlertManager` n'ont aucune connaissance du mode `ALPHAEDGE_PAPER`. Les alertes paper et live sont identiques, source de confusion critique sur mobile.
Correction : Ajouter un champ `paper_mode: bool = True` à `AlertConfig`. Dans `AlertManager.send()`, préfixer automatiquement le titre de chaque alerte avec `[PAPER]` si `paper_mode=True`. Alimenter ce champ depuis `os.environ.get("ALPHAEDGE_PAPER", "true").lower() == "true"` dans `build_alert_config()`.
Validation :
  ```powershell
  make qa
  # Attendu : 504 tests pass
  # Vérifier : aucun test_alerting.py n'utilise de titre hardcodé sans [PAPER]
  ```
Dépend de : Aucune
Statut : ⏳

### [C-11] Support traceback optionnel dans les alertes d'erreur

Fichier : `alphaedge/utils/alerting.py` (tous les builders d'alerte d'erreur)
Problème : Aucun builder d'alerte n'accepte `exc_info` ou `traceback_str`. Les alertes critiques ne permettent pas de diagnostiquer la cause sans accéder aux logs loguru.
Correction : Ajouter un paramètre optionnel `traceback_str: str | None = None` aux builders `alert_ib_disconnected()` et `alert_kill_switch()`. Si fourni, l'appender comme bloc de code (troncation à 500 chars) à la fin du message.
Validation :
  ```powershell
  make qa
  # Attendu : 504 tests pass
  ```
Dépend de : Aucune
Statut : ⏳

---

## SÉQUENCE D'EXÉCUTION

```
C-01  → Connecter AlertManager au pipeline          [P0 — bloquant pour C-04/C-05/C-06/C-07]
  ├── C-02  → Retry backoff Telegram/Discord         [P1 — indépendant, faire en même temps]
  └── C-03  → Cooldown anti-tempête                  [P1 — indépendant, faire en même temps]

C-04  → alert_kill_switch dans _check_daily_loss    [P1 — dépend de C-01]
C-05  → alert_ib_disconnected dans _on_ib_disconnect [P1 — dépend de C-01]
C-07  → alert reconnexion IB échouée               [P1 — dépend de C-01]

C-08  → lot_size dans alert_trade_executed          [P2 — indépendant]
C-09  → error_code dans alert_ib_disconnected       [P2 — indépendant, avant C-05 idéalement]
C-10  → préfixe [PAPER]/[LIVE]                      [P2 — indépendant]

C-06  → alerte timeout fill                         [P2 — dépend de C-01]

C-11  → traceback optionnel                         [P3 — en dernier]
```

> ⚠️ Aucun fichier `.pyx` n'est modifié dans ce plan — `make build` n'est pas requis.

---

## CRITÈRES PASSAGE EN PRODUCTION

- [ ] Zéro 🔴 ouvert
- [ ] `make qa` : 100% pass (lint + mypy + pytest ≥ 80%)
- [ ] Zéro credential dans les logs loguru
- [ ] `ALPHAEDGE_PAPER=true` intact dans `.env.example`
- [ ] Bracket order `is_valid` vérifié avant envoi IB
- [ ] `check_daily_limit()` appelé chaque cycle
- [ ] `AlertManager` instancié dans `strategy.py` et passé aux composants dépendants
- [ ] `alert_kill_switch()` appelé dans `_check_daily_loss_shutdown()` avant shutdown
- [ ] `alert_ib_disconnected()` appelé dans `_on_ib_disconnect()` et `_on_ib_error()` (codes 1100-1102)
- [ ] Alertes confirmées reçues sur Telegram/Discord en mode paper (test end-to-end)
- [ ] Paper trading validé 5 sessions NYSE minimum sans alerte parasite

---

## TABLEAU DE SUIVI

| ID | Titre | Sévérité | Fichier principal | Effort | Statut | Date |
|----|-------|----------|-------------------|--------|--------|------|
| C-01 | Connecter AlertManager au pipeline live | 🔴 P0 | `strategy.py` + `session_lifecycle.py` + `broker.py` + `loader.py` | ~3h | ✅ 2026-03-22 | — |
| C-02 | Retry backoff Telegram/Discord | 🟠 P1 | `alerting.py:193,231` | ~1h | ✅ 2026-03-22 | — |
| C-03 | Cooldown anti-tempête AlertManager | 🟠 P1 | `alerting.py:248` | ~1h | ✅ 2026-03-22 | — |
| C-04 | alert_kill_switch dans daily loss shutdown | 🟠 P1 | `session_lifecycle.py:522` | ~30min | ✅ 2026-03-22 | — |
| C-05 | alert_ib_disconnected dans déconnexion IB | 🟠 P1 | `session_lifecycle.py:234` + `broker.py:234` | ~30min | ✅ 2026-03-22 | — |
| C-07 | Alerte reconnexion IB échouée | 🟠 P1 | `session_lifecycle.py:254` | ~30min | ✅ 2026-03-22 | — |
| C-06 | Alerte timeout fill (10s) | 🟡 P2 | `session_lifecycle.py:133` | ~30min | ✅ 2026-03-22 | — |
| C-08 | lot_size dans alert_trade_executed | 🟡 P2 | `alerting.py:336` | ~15min | ✅ 2026-03-22 | — |
| C-09 | error_code dans alert_ib_disconnected | 🟡 P2 | `alerting.py:395` | ~15min | ✅ 2026-03-22 | — |
| C-10 | Préfixe [PAPER]/[LIVE] dans les alertes | 🟡 P2 | `alerting.py:96` | ~30min | ✅ 2026-03-22 | — |
| C-11 | Traceback optionnel dans alertes d'erreur | ⚪ P3 | `alerting.py` (builders) | ~1h | ✅ 2026-03-22 | — |
