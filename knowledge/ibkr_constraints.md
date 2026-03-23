# ALPHAEDGE — IB Gateway Constraints

Contraintes opérationnelles Interactive Brokers extraites du code source.

---

## Ports de connexion

| Mode | Port | Constante |
|------|------|-----------|
| Paper Trading (IB Gateway) | **4002** | `IB_PAPER_PORT` |
| Live Trading (IB Gateway) | **4001** | `IB_LIVE_PORT` |
| Paper Trading (TWS) | 7497 | — |
| Live Trading (TWS) | 7496 | — |

**Par défaut ALPHAEDGE** : port 4002 (paper). `ALPHAEDGE_PAPER=true` dans `.env`.

---

## Rate Limiting

| Limite | Valeur | Implémentation ALPHAEDGE |
|--------|--------|--------------------------|
| Hard cap IB | 50 req/s | Token bucket à 45 req/s sustained |
| Burst max | ~10 req | `IB_TOKEN_BUCKET_BURST = 10` |
| Requests historiques simultanés | ~3 | `IB_MAX_CONCURRENT_HIST_REQUESTS = 3` |

**Mécanisme** : `RequestThrottler` (token-bucket) dans `broker.py`. La pénalité de pacing vide le bucket (`throttler.penalise()`) sur réception du code 162.

---

## Timeouts

| Opération | Timeout | Constante |
|-----------|---------|-----------|
| Connexion / ordre | 15 s | `IB_TIMEOUT_SECONDS` |
| Données historiques | 60 s | `IB_HIST_TIMEOUT_SECONDS` |
| Fill verification | 10 s | `asyncio.wait_for` dans `session_lifecycle.py` |

---

## Codes d'erreur IB

### Codes informatifs (non-erreurs) — DEBUG seulement

| Code(s) | Signification |
|---------|--------------|
| 2100–2176 | Data farm connectivity (HMDS, HFARM, SFARM) · pacing lifted |

### Codes à traiter

| Code | Signification | Action ALPHAEDGE |
|------|--------------|-----------------|
| **162** | Request timeout / pacing violation | DEBUG + `throttler.penalise()` |
| **200** | No security definition found | ERROR log |
| **321** | Server validation error | ERROR log |
| **504** | Not connected to IB | CRITICAL log |
| **1100** | Connectivity lost | CRITICAL log |
| **1101** | Connectivity restored (data lost) | CRITICAL log |
| **1102** | Connectivity restored (data ok) | CRITICAL log |

---

## Types d'ordres disponibles (Forex IDEALPRO)

| Ordre | Classe ib_insync | Usage ALPHAEDGE |
|-------|-----------------|----------------|
| Market | `MarketOrder` | Entrée en cas de slippage acceptable |
| Limit | `LimitOrder` | Entrée préférée (bracket) |
| Stop | `StopOrder` | Stop-loss du bracket |

**Bracket order** : entry (Limit) + SL (Stop) + TP (Limit) construits par `order_manager.pyx`.

---

## Idempotence Client Order IDs

Les `orderId` IB sont gérés par ib_insync (`reqIds()`). ALPHAEDGE ne gère pas manuellement les IDs — c'est délégué à ib_insync pour éviter les doublons.

---

## Circuit Breaker

Après `IB_CIRCUIT_BREAKER_MAX_FAILURES = 5` échecs de connexion consécutifs, le circuit s'ouvre et arrête les tentatives. Réinitialisation manuelle requise.

---

## Exchange

Toutes les paires Forex passent par **IDEALPRO** (exchange IBKR pour Forex).
Constructeur : `build_forex_contract(pair)` dans `broker.py`.
