# AUDIT EMAIL & ALERTES — ALPHAEDGE
> **Date** : 2026-03-22 à 16:20
> **Prompt source** : `tasks/prompts/audit_email_alerts_prompt.md`
> **Scope** : Système d'envoi (Telegram/Discord) · couverture événements · sécurité contenu · protection tempêtes · intégration pipeline IB Gateway

---

## BLOC 1 — SYSTÈME D'ENVOI

### 1.1 Canaux d'envoi

**Fichier principal** : `alphaedge/utils/alerting.py`

| Canal | Implémentation | Statut |
|-------|---------------|--------|
| Telegram | `send_telegram()` via Bot API + `urlopen` (sync) | ✅ Présent |
| Discord | `send_discord()` via webhook + `urlopen` (sync) | ✅ Présent |
| Email / SMTP | Absent | ❌ Non implémenté |

### 1.2 Retry avec backoff

**Résultat** : ❌ ABSENT

`send_telegram()` (ligne 193) et `send_discord()` (ligne 231) ne font qu'une seule tentative. En cas d'échec réseau temporaire (timeout réseau, API Telegram surchargée), la notification est perdue sans aucun retry.

```python
# alerting.py:193 — aucun retry
try:
    with urlopen(req, timeout=10) as resp:
        return bool(resp.status == 200)
except (URLError, OSError) as exc:
    logger.error(f"Telegram alert failed: {exc}")
    return False
```

### 1.3 Cooldown anti-tempête

**Résultat** : ❌ ABSENT

`AlertManager` (lignes 248–330) ne contient aucun mécanisme de déduplication ni de cooldown par `AlertEvent`. En cas de retry loop IB qui déclenche des dizaines de déconnexions par minute, `alert_ib_disconnected()` pourrait être envoyé en boucle.

Aucun champ `_last_sent: dict[AlertEvent, datetime]`, aucun `_cooldown_seconds`, aucun `_dedup_cache`.

### 1.4 Transport SMTP / TLS

**Résultat** : N/A — Email non implémenté.
Le système n'utilise pas SMTP. Telegram et Discord sont les seuls canaux. Pas de risque SSL direct.

### 1.5 URLs webhooks depuis config / .env

**Résultat** : ✅ CONFORME

`TelegramConfig.bot_token` et `DiscordConfig.webhook_url` sont des champs vides par défaut, remplis depuis `config.yaml` via `build_alert_config()` (ligne 450). Le fichier `config.yaml` (lignes 141–147) confirme : `bot_token: ""`, `webhook_url: ""` — jamais hardcodés.

Aucune URL ni token hardcodé trouvé dans le code source.

### 1.6 Échecs d'envoi — non-blocking

**Résultat** : ✅ CONFORME

`send_telegram()` et `send_discord()` capturent `(URLError, OSError)` et retournent `False` sans propager l'exception. `AlertManager.send()` logue un warning mais ne raise pas. Le bot continue de fonctionner même si toutes les notifications échouent.

### 1.7 Mode async

**Résultat** : ✅ PRÉSENT

`AlertManager.send_async()` (ligne 318) utilise `loop.run_in_executor(None, self.send, alert)` pour ne pas bloquer la boucle asyncio principale.

---

## BLOC 2 — COUVERTURE DES ÉVÉNEMENTS

> ⚠️ **Découverte critique** : `alerting.py` est importé UNIQUEMENT par `tests/test_alerting.py`.
> **Aucun module engine (`strategy.py`, `session_lifecycle.py`, `broker.py`) n'importe ni n'instancie `AlertManager`.**
> Tout ce qui suit est donc la couverture du MODULE (ce qu'il PEUT faire), pas ce qu'il FAIT en production.

### 2.1 Événements d'erreurs système

| Événement | `AlertEvent` défini | Appelé en production | Verdict |
|-----------|--------------------|--------------------|---------|
| Exception critique non gérée dans le pipeline | ❌ Non défini | ❌ | NON COUVERT |
| Échec sauvegarde DailyState / JSON | ❌ Non défini | ❌ | NON COUVERT |
| Échec connexion IB Gateway (1100-1102) | `IB_DISCONNECTED` ✅ | ❌ non appelé | NON COUVERT |
| Données de marché manquantes M1/M5 | ❌ Non défini | ❌ | NON COUVERT |
| Erreur réseau prolongée / déconnexion IB | `IB_DISCONNECTED` ✅ | ❌ non appelé | NON COUVERT |
| Circuit breaker IB (RequestThrottler) | ❌ Non défini | ❌ | NON COUVERT |
| Timeout fill (> 10 s) | ❌ Non défini | ❌ | NON COUVERT |

**Fichiers concernés** :
- `session_lifecycle.py:234` — `logger.critical("ALPHAEDGE: IB Gateway DISCONNECTED")` → loguru only, aucune alerte
- `session_lifecycle.py:133` — `logger.error("ALPHAEDGE: Parent order not filled within 10s")` → loguru only
- `broker.py:234` — `logger.critical(f"ALPHAEDGE IB CONNECTION: code={errorCode}")` → loguru only

### 2.2 Événements de trading

| Événement | `AlertEvent` défini | Appelé en production | Verdict |
|-----------|--------------------|--------------------|---------|
| Bracket order soumis (prix, SL, TP, lot_size) | `TRADE_EXECUTED` ✅ | ❌ non appelé | NON COUVERT |
| Fill confirmé (prix réel, slippage, PnL) | `TRADE_EXECUTED` ✅ (partiel) | ❌ non appelé | NON COUVERT |
| Ordre bloqué (spread, daily limit, is_valid=False) | ❌ Non défini | ❌ | NON COUVERT |
| Ordre échoué (rejet IB, erreur 321/200) | ❌ Non défini | ❌ | NON COUVERT |
| Stop-loss déclenché | `TRADE_CLOSED` ✅ | ❌ non appelé | NON COUVERT |
| Take-profit atteint | `TRADE_CLOSED` ✅ | ❌ non appelé | NON COUVERT |
| Position ouverte sans confirmation fill | ❌ Non défini | ❌ | NON COUVERT |

**Fichier concerné** :
- `session_lifecycle.py:222` — `logger.info("ALPHAEDGE: Position closed for {pair}")` → loguru only
- `session_lifecycle.py:125` — `logger.error("ALPHAEDGE: Bracket order returned empty")` → loguru only

### 2.3 Événements de protection du capital

| Événement | `AlertEvent` défini | Appelé en production | Verdict |
|-----------|--------------------|--------------------|---------|
| Daily loss limit atteint (halt_trading=True) | `KILL_SWITCH` ✅ | ❌ non appelé | NON COUVERT |
| Max trades per session atteint | ❌ Non défini | ❌ | NON COUVERT |
| Spread trop élevé | ❌ Non défini | ❌ | NON COUVERT |
| calculate_position_size → is_valid=False | ❌ Non défini | ❌ | NON COUVERT |
| ALPHAEDGE_PAPER=false détecté | ❌ Non défini | ❌ | NON COUVERT |

**Fichier concerné** :
- `session_lifecycle.py:512` — `_check_daily_loss_shutdown()` → `logger.warning` + shutdown, aucune alerte

---

## BLOC 3 — QUALITÉ DU CONTENU

### 3.1 Richesse des informations

**Résultat** : ⚠️ PARTIEL

`alert_trade_executed()` (ligne 336) inclut `entry_price`, `stop_loss`, `take_profit` — mais **pas** `lot_size`, `direction` dans le message (seulement dans le titre), ni horodatage explicite (ajouté par `__post_init__` — ✅).

`alert_kill_switch()` (ligne 381) inclut `reason` et `daily_pnl_pct` — bon niveau de détail.
`alert_ib_disconnected()` (ligne 395) ne contient que le message générique — pas d'erreur code, pas de timestamp dernier heartbeat.

### 3.2 Traceback dans les alertes d'erreur

**Résultat** : ❌ ABSENT

Aucun builder d'alerte n'accepte ou ne transmet un `traceback` ou `exc_info`. Les alertes d'erreur (IB_DISCONNECTED, KILL_SWITCH) contiennent des messages génériques sans détail technique.

### 3.3 Credentials IB dans le contenu

**Résultat** : ✅ CONFORME

Aucun `account_id`, `bot_token`, `webhook_url`, ni aucun secret n'est inclus dans le corps des messages construits par les fonctions `alert_*()`. Le `bot_token` est uniquement dans l'URL de requête, jamais dans le payload.

### 3.4 Distinction critique vs informatif

**Résultat** : ✅ CONFORME

`AlertLevel` (ligne 30) définit `INFO / WARNING / CRITICAL` avec emoji distinct (`ℹ️ / ⚠️ / 🚨`). Les titres incluent le level dans le format Discord (couleur embed). La distinction est lisible immédiatement.

### 3.5 Horodatages UTC

**Résultat** : ✅ CONFORME

`Alert.__post_init__()` (ligne 63) génère `datetime.now(tz=UTC).strftime("%Y-%m-%d %H:%M:%S UTC")` — UTC strict, sans offset local.

---

## BLOC 4 — CAS MANQUANTS ET RISQUES

### 4.1 Erreurs swallowées silencieusement

**Résultat** : ⚠️ RISQUE IDENTIFIÉ

`session_lifecycle.py:512` — `_check_daily_loss_shutdown()` :
```python
except Exception:
    logger.exception("ALPHAEDGE daily-loss check failed")
    continue  # ← l'échec est logué mais aucune alerte externe
```
Si la vérification du daily loss échoue silencieusement, le bot continue à trader sans protection. Aucune alerte externe n'est envoyée.

`session_lifecycle.py:195-200` — `_execute_signal()` :
```python
except Exception:
    logger.exception(f"ALPHAEDGE _execute_signal failed: {state.pair}")
    return False  # ← logué, mais pas alerté
```

### 4.2 Événements loggés sans alerte

**Résultat** : ❌ NON COUVERT (systémique)

**Tous** les événements critiques dans le pipeline live (`session_lifecycle.py`, `broker.py`, `strategy.py`) sont loggés via `loguru` uniquement. Aucune intégration `AlertManager.send()` n'existe dans ces modules.

Exemples concrets :
- `broker.py:127` — `logger.critical(...)` sur connexion échouée → loguru only
- `broker.py:192` — `logger.error("reconnection failed")` → loguru only
- `session_lifecycle.py:254` — `logger.critical("Reconnection FAILED")` → loguru only

### 4.3 Cascade d'alertes en cas de retry loop

**Résultat** : ❌ RISQUE THÉORIQUE (mais non actuel)

Le module `alerting.py` n'a aucun cooldown. Si `AlertManager` était branché sur le pipeline (ce qui n'est pas le cas actuellement), un retry loop IB pacing pourrait générer des dizaines d'alertes `IB_DISCONNECTED` par minute.

### 4.4 Non-blocking en cas d'échec d'envoi

**Résultat** : ✅ CONFORME (voir Bloc 1.6)

### 4.5 Alertes en mode paper vs live

**Résultat** : ❌ ABSENT de la logique

`AlertConfig` et `AlertManager` n'ont aucune connaissance du mode `ALPHAEDGE_PAPER`. Les alertes (si envoyées) seraient identiques en paper et en live — pas de préfixe `[PAPER]` ni de filtrage par mode.

---

## SYNTHÈSE

### Tableau complet des problèmes

| ID | Bloc | Description | Fichier:Ligne | Sévérité | Impact | Effort |
|----|------|-------------|--------------|----------|--------|--------|
| A-01 | 2 | `AlertManager` non connecté au pipeline live | `strategy.py`, `session_lifecycle.py`, `broker.py` — aucune importation | **P0** | Zéro alerte reçue en production, quelle que soit la configuration | ~3h |
| A-02 | 1 | Aucun retry avec backoff sur Telegram/Discord | `alerting.py:193,231` | **P1** | Alertes perdues sur erreur réseau temporaire | ~1h |
| A-03 | 1 | Aucun cooldown anti-tempête dans `AlertManager` | `alerting.py:248` | **P1** | Cascade possible si A-01 résolu et retry loop IB | ~1h |
| A-04 | 2 | `_check_daily_loss_shutdown()` échoue silencieusement | `session_lifecycle.py:512` | **P1** | Bot continue à trader sans protection capital | ~30min |
| A-05 | 3 | `alert_ib_disconnected()` sans code erreur ni contexte | `alerting.py:395` | **P2** | Diagnostic impossible sans ouvrir les logs | ~15min |
| A-06 | 3 | `alert_trade_executed()` sans `lot_size` dans le message | `alerting.py:336` | **P2** | Information incomplète pour vérification manuelle | ~15min |
| A-07 | 4 | Pas de préfixe `[PAPER]` / `[LIVE]` dans les alertes | `alerting.py:96` | **P2** | Confusion paper vs live sur mobile | ~30min |
| A-08 | 2 | Timeout fill (10 s) non alerté | `session_lifecycle.py:133` | **P2** | Ordre annulé sans notification externe | ~30min |
| A-09 | 2 | Daily loss limit breach non alerté | `session_lifecycle.py:522` | **P1** | Shutdown silencieux sans notification trader | ~30min |
| A-10 | 3 | Aucun traceback dans les alertes d'erreur | `alerting.py` — tous les builders | **P3** | Diagnostic dépend des logs loguru uniquement | ~1h |
| A-11 | 2 | Reconnexion IB échouée non alertée | `session_lifecycle.py:254` | **P1** | Shutdown silencieux → perte de trades sans notification | ~30min |

---

### Événements NON COUVERTS par criticité financière

1. **Daily loss limit breached** — le bot s'arrête silencieusement (`session_lifecycle.py:522`). Le trader ne sait pas que le capital est en danger.
2. **Reconnexion IB échouée après 3 essais** — shutdown silencieux (`session_lifecycle.py:254`), positions ouvertes potentielles.
3. **Timeout fill (10 s)** — ordre annulé sans notification (`session_lifecycle.py:133`), le trader croit peut-être que l'ordre est passé.
4. **Bracket order soumis / fill confirmé** — aucune confirmation externe du trade.
5. **Stop-loss / Take-profit déclenché** — position fermée sans notification.
6. **Spread trop élevé** — signal bloqué silencieusement.
7. **`_check_daily_loss_shutdown()` itself fails** — protection désactivée silencieusement.

---

### Top 3 risques immédiats

1. **🔴 A-01 — `AlertManager` jamais instancié en production** : L'intégralité du système d'alertes (`alerting.py`, 480 lignes) est du code mort en production. Le trader ne reçoit aucune notification, quelle que soit la configuration dans `config.yaml`. Conséquence directe : un daily loss limit breach, une déconnexion IB, un ordre annulé passent tous inaperçus.

2. **🔴 A-09 + A-11 — Shutdown silencieux sans alerte** : Deux scénarios critiques déclenchent `self._s._shutdown_requested = True` + loguru uniquement, sans aucune notification externe. Si le trader n'est pas devant ses logs, il ne sait pas que le bot s'est arrêté.

3. **🟠 A-03 — Absence de cooldown** : Dès qu'A-01 sera résolu, le risque de tempête d'alertes sur retry loop IB sera immédiat. À traiter en même temps que A-01.

---

### Points forts à conserver

- ✅ Architecture `AlertManager` propre avec canaux découplés (Telegram + Discord indépendants)
- ✅ `send_async()` via `run_in_executor` — non-blocking, adapté à asyncio
- ✅ Format Telegram HTML et Discord embeds avec couleurs par niveau
- ✅ `AlertEvent` enum — liste exhaustive des événements (9 types), extensible
- ✅ `_is_event_enabled()` — filtrage par événement configurable via `config.yaml`
- ✅ Aucun credential dans le contenu des messages
- ✅ Horodatages UTC stricts (`datetime.now(tz=UTC)`)
- ✅ `build_alert_config()` — constructeur propre depuis YAML, sans valeurs hardcodées
- ✅ `TelegramConfig.enabled` / `DiscordConfig.enabled` — désactivation granulaire par canal
