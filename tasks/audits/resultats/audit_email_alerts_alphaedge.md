---
modele: sonnet-4.6
mode: agent
contexte: codebase
produit: audit_email_alerts_alphaedge.md
derniere_revision: 2026-03-25
creation: 2026-03-25 à 18:00
---

# AUDIT EMAIL & ALERTES — ALPHAEDGE
> **Date** : 2026-03-25 à 18:00
> **Prompt source** : `tasks/audits/code/audit_email_alerts_prompt.md`
> **Scope** : Système d'envoi (Telegram/Discord) · couverture événements · sécurité contenu · protection tempêtes · intégration pipeline IB Gateway

---

## BLOC 1 — SYSTÈME D'ENVOI

### 1.1 Canaux d'envoi

**Fichier principal** : `alphaedge/utils/alerting.py`

| Canal | Implémentation | Statut |
|-------|---------------|--------|
| Telegram | `send_telegram()` via Bot API HTTPS | ✅ Présent |
| Discord | `send_discord()` via webhook HTTPS | ✅ Présent |
| Email / SMTP | Absent | N/A — non requis |

### 1.2 Retry avec backoff

**Résultat** : ✅ CONFORME

`send_telegram()` et `send_discord()` tentent 3 fois avec backoff exponentiel (`time.sleep(2 ** attempt)`). Après 3 échecs, `logger.error()` est appelé et la fonction retourne `False` — aucune exception propagée.

### 1.3 Cooldown anti-tempête

**Résultat** : ✅ CONFORME

`AlertManager` contient `_COOLDOWN_SECONDS` avec des valeurs différenciées :
- `IB_DISCONNECTED` : 120 s
- `IB_RECONNECTED` : 60 s
- `KILL_SWITCH` : 300 s
- Défaut : 30 s

En cas de retry loop IB, `alert_ib_disconnected()` ne sera envoyé qu'une fois toutes les 2 minutes maximum.

### 1.4 Transport SMTP / TLS

**Résultat** : N/A — SMTP non utilisé. HTTPS exclusivement (Telegram Bot API + Discord webhook).

### 1.5 URLs webhooks depuis config / `.env`

**Résultat** : ✅ CONFORME

`build_alert_config()` lit exclusivement depuis le dict de configuration (`config.yaml`) et `os.environ` pour `ALPHAEDGE_PAPER`. Aucun token, aucune URL, aucun webhook hardcodé dans le code source.

`config.yaml` (ligne 135) confirme : `bot_token: ""`, `webhook_url: ""` — vides par défaut, jamais peuplés sans intervention explicite.

### 1.6 Échecs d'envoi — non-blocking

**Résultat** : ✅ CONFORME

`send_telegram()` et `send_discord()` catchent `(URLError, OSError)` et retournent `False`. `AlertManager.send()` logue un warning mais ne raise pas. `send_async()` isole l'appel dans un thread pool via `loop.run_in_executor()`. Une notification échouée n'impacte jamais le bot.

### 1.7 Mode paper / live

**Résultat** : ✅ CONFORME

`AlertManager` préfixe tous les titres de `[PAPER]` lorsque `paper_mode=True` (lu depuis `ALPHAEDGE_PAPER`). Aucune confusion possible entre environnement de test et Live sur mobile.

### 1.8 Mode async

**Résultat** : ✅ CONFORME

`AlertManager.send_async()` utilise `loop.run_in_executor(None, self.send, alert)` pour ne jamais bloquer la boucle asyncio principale du bot.

---

## BLOC 2 — COUVERTURE DES ÉVÉNEMENTS

> **Contexte actuel** : `AlertManager` est instancié dans `AlphaEdgeSession` et exposé via `self._s._alert_manager`. `session_lifecycle.py` importe `Alert`, `AlertEvent`, `AlertLevel`, `alert_ib_disconnected`, `alert_kill_switch`. Les 7 autres builders de `alerting.py` ne sont **jamais importés ni appelés**.

### 2.1 Événements d'erreurs système

| Événement | `AlertEvent` défini | Appelé en production | Site d'appel | Verdict |
|-----------|--------------------|--------------------|-------------|---------|
| IB Gateway déconnecté | ✅ `IB_DISCONNECTED` | ✅ Oui | `session_lifecycle.py:378` | ✅ |
| IB Gateway reconnecté | ✅ `IB_RECONNECTED` | ❌ **Non** | — | 🟠 |
| IB Reconnexion échouée | ✅ `IB_DISCONNECTED` (CRITICAL) | ✅ Oui (ad-hoc) | `session_lifecycle.py:409` | ⚠️ |
| Kill-switch / daily loss | ✅ `KILL_SWITCH` | ✅ Oui | `session_lifecycle.py:711` | ✅ |

> **Note ligne 409** : La reconnexion échouée utilise un `Alert` ad-hoc avec `AlertEvent.IB_DISCONNECTED` plutôt que `AlertEvent.IB_RECONNECTED`. Sémantiquement correct (c'est une déconnexion fatale), mais utiliser un event dédié `IB_RECONNECTION_FAILED` manque à la liste — mineur.

### 2.2 Événements trade

| Événement | `AlertEvent` défini | Builder défini | Appelé en production | Verdict |
|-----------|--------------------|--------------|--------------------|---------|
| Trade exécuté (fill confirmé) | ✅ `TRADE_EXECUTED` | ✅ `alert_trade_executed()` | ❌ **Non** (`_record_fill()` log seulement) | 🔴 |
| Fill timeout (10 s) | ✅ `TRADE_EXECUTED` | N/A (ad-hoc) | ✅ `session_lifecycle.py:153` | ⚠️ |
| Trade clôturé (SL/TP fill) | ✅ `TRADE_CLOSED` | ✅ `alert_trade_closed()` | ❌ **Non** (`_on_trade_closed()` log seulement) | 🔴 |
| Signal détecté | ✅ `SIGNAL_DETECTED` | ✅ `alert_signal_detected()` | ❌ **Non** | 🟡 |

> **Note ligne 153** : Le fill timeout utilise `AlertEvent.TRADE_EXECUTED` avec `AlertLevel.WARNING`. Sémantique incorrecte — TRADE_EXECUTED implique un trade confirmé, pas un échec de fill. L'opérateur recevant cette alerte peut croire qu'un trade est ouvert alors que la position a été annulée.

### 2.3 Événements session

| Événement | `AlertEvent` défini | Builder défini | Appelé en production | Verdict |
|-----------|--------------------|--------------|--------------------|---------|
| Fin de session — position ouverte | ✅ `SESSION_END_OPEN` | ✅ `alert_session_end_open()` | ❌ **Non** (`_handle_session_end()` log seulement) | 🟠 |
| Fin de session — clean | ✅ `SESSION_END_CLEAN` | ✅ `alert_session_end_clean()` | ❌ **Non** | 🟠 |
| Résumé journalier | ✅ `DAILY_SUMMARY` | ✅ `alert_daily_summary()` | ❌ **Non** | 🟡 |

---

## BLOC 3 — QUALITÉ DU CONTENU

### 3.1 Informations dans les messages

| Builder | Champs inclus | Verdict |
|---------|--------------|---------|
| `alert_trade_executed()` | pair, direction, entry_price, lot_size, sl_pips, spread_pips | ✅ Complet |
| `alert_trade_closed()` | pair, direction, exit_price, pnl_pips, pnl_usd, outcome, duration | ✅ Complet |
| `alert_kill_switch()` | reason, daily_pnl_pct, traceback (500 chars tronqués) | ✅ Complet |
| `alert_ib_disconnected()` | timestamp, message fixe | ✅ Suffisant |
| `alert_session_end_open()` | pair, open_count, action | ✅ Complet |
| `alert_session_end_clean()` | trades_today, pairs | ✅ Complet |
| `alert_daily_summary()` | trades_today, wins, losses, total_pnl_usd | ✅ Complet |

### 3.2 Sécurité du contenu

**Résultat** : ✅ CONFORME

- Aucun token, credential, ou valeur de compte IB dans les messages d'alerte.
- PnL en USD et en pips seulement — pas de solde de compte absolu.
- `alert_kill_switch()` tronque le traceback à 500 caractères pour éviter la fuite de chemins de fichiers.

### 3.3 Format des alertes

**Résultat** : ✅ CONFORME

- Horodatages ISO 8601 UTC inclus dans chaque `Alert`.
- Formatage Telegram (texte plain) et Discord (embed JSON) séparés via `format_telegram()` / `format_discord()`.
- Tous les floats arrondis à 1-2 décimales dans les builders.

---

## BLOC 4 — CAS MANQUANTS / EDGE CASES

### 4.1 Silence sur événements opérationnels non-critiques

| Événement | Localisation | Comportement actuel |
|-----------|-------------|---------------------|
| Max trades/session atteint | `session_lifecycle.py:530, 629` | `return` silencieux, log DEBUG absent |
| Spread trop élevé | `session_lifecycle.py:655` | Log `INFO` seulement |
| Spread spike (position ouverte) | `session_lifecycle.py:669-689` | Log `WARNING` seulement |

Ces événements ne justifient pas d'alerte (`🟡`) mais le silence complet (max trades) est notable.

### 4.2 Exception handling

**Résultat** : ✅ CONFORME

Aucun `except: pass` trouvé. Tous les blocs `except Exception` dans `session_lifecycle.py` appellent `logger.exception()`. `send_telegram()` et `send_discord()` catchent explicitement `(URLError, OSError)`.

### 4.3 Cascade d'alertes IB

**Résultat** : ✅ PROTÉGÉ

Cooldown `IB_DISCONNECTED` = 120 s mitigue toute cascade de pacing violations IB. Même en retry loop, l'opérateur ne reçoit au plus qu'une alerte toutes les 2 minutes.

### 4.4 `config.yaml` — événements configurés

Les 9 événements sont listés dans `config.yaml` (lignes 143-152) sous `alerting.events`. Cependant, 5 d'entre eux (`trade_executed`, `trade_closed`, `session_end_open_position`, `session_end_clean`, `ib_reconnected`) ne sont **jamais déclenchés** malgré leur présence dans la config — la config est en avance sur l'implémentation.

---

## SYNTHÈSE

### Tableau synthèse

| ID | Bloc | Description | Fichier:Ligne | Sévérité | Impact | Effort |
|----|------|-------------|--------------|----------|--------|--------|
| E-01 | 2 | `alert_trade_executed()` jamais appelé — fill confirmé sans notification | `session_lifecycle.py:200-221` | 🔴 Critique | Trader aveugle à l'ouverture d'une position en temps réel | ~30 min |
| E-02 | 2 | `alert_trade_closed()` jamais appelé — SL/TP fill sans notification | `session_lifecycle.py:348-360` | 🔴 Critique | Trader aveugle à la clôture d'une position (résultat inconnu) | ~30 min |
| M-01 | 2 | `alert_ib_reconnected()` jamais appelé après reconnexion réussie | `session_lifecycle.py:396` | 🟠 Majeur | Opérateur ne sait pas si le système s'est auto-rétabli | ~15 min |
| M-02 | 2 | `alert_session_end_open/clean()` jamais appelés — fin de session silencieuse | `session_lifecycle.py:_handle_session_end` | 🟠 Majeur | Position ouverte en fin de session invisible sur mobile | ~30 min |
| M-03 | 2 | Fill timeout ligne 153 utilise `AlertEvent.TRADE_EXECUTED` (sémantique incorrecte) | `session_lifecycle.py:153` | 🟠 Majeur | Opérateur croit qu'un trade est ouvert alors que la position est annulée | ~15 min |
| N-01 | 2 | `alert_signal_detected()` jamais appelé | `session_lifecycle.py` — aucun site | 🟡 Mineur | Visibilité opérationnelle manquante (nice-to-have) | ~30 min |
| N-02 | 2 | `alert_daily_summary()` jamais appelé — pas de résumé de fin de journée | `session_lifecycle.py:_handle_session_end` | 🟡 Mineur | Bilan journalier absent sur mobile | ~30 min |
| N-03 | 4 | Max trades/session atteint — silence total (pas même un log INFO) | `session_lifecycle.py:530, 629` | 🟡 Mineur | Opérateur ne comprend pas pourquoi plus aucun trade n'est pris | ~15 min |

**Sévérité** : 🔴 Critique · 🟠 Majeur · 🟡 Mineur

### Bilan global

Le système d'envoi lui-même est **solide** : retry/backoff, cooldown, non-blocking, async, paper prefix, URLs depuis config. Les problèmes de la version FCR archivée (AlertManager mort, pas de retry, pas de cooldown) sont tous résolus.

Le déficit actuel est uniquement de **couverture** : 5 builders sur 9 définis dans `alerting.py` ne sont jamais appelés depuis `session_lifecycle.py`, malgré leur présence dans `config.yaml`. Les deux cas critiques (trade ouvert, trade clôturé) privent l'opérateur de visibilité temps réel sur l'activité de trading.
