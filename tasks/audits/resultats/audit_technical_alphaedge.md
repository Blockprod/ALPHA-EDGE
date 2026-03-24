**Date :** 2026-03-22 à 17:44

## BLOC 1 — SÉCURITÉ CREDENTIALS IB

### Constat positif

- Les credentials IB sont chargés depuis l'environnement via `load_dotenv()` puis `os.getenv(...)` dans [alphaedge/config/loader.py:220](c:/Users/averr/AlphaEdge/alphaedge/config/loader.py#L220), [alphaedge/config/loader.py:248](c:/Users/averr/AlphaEdge/alphaedge/config/loader.py#L248), [alphaedge/config/loader.py:253](c:/Users/averr/AlphaEdge/alphaedge/config/loader.py#L253) et [alphaedge/config/loader.py:257](c:/Users/averr/AlphaEdge/alphaedge/config/loader.py#L257).
- `.env.example` contient bien `ALPHAEDGE_PAPER=true` et avertit explicitement sur le mode live.
- `.gitignore` protège `.env`, `alphaedge/logs/*.log`, `alphaedge/logs/*.txt`, `alphaedge/cache/` et l'état runtime `alphaedge_daily_state.json`.
- Aucune occurrence de `ALPHAEDGE_PAPER=false` n'a été trouvée dans le code Python exécutable inspecté.

### Problèmes

| ID | Description | Fichier:Ligne | Sévérité | Impact | Effort |
|----|-------------|---------------|----------|--------|--------|
| T-01 | `IBConfig` expose `account_id` dans une dataclass sans `__repr__` masqué. Si l'objet config est loggé ou dumpé en debug, l'identifiant de compte peut fuiter en clair. | `alphaedge/config/loader.py:134`, `alphaedge/config/loader.py:140`, `alphaedge/config/loader.py:257` | 🟡 | Fuite potentielle d'identifiant IB dans logs/debug dumps | XS |

### Évaluation

- **Credentials IB uniquement depuis env ?** Oui en pratique, avec fallback YAML pour `host`, `port`, `client_id`, `account_id` via [alphaedge/config/loader.py:248](c:/Users/averr/AlphaEdge/alphaedge/config/loader.py#L248) à [alphaedge/config/loader.py:257](c:/Users/averr/AlphaEdge/alphaedge/config/loader.py#L257).
- **`ALPHAEDGE_PAPER=true` présent dans `.env.example` ?** Oui.
- **`.gitignore` protège `.env`, `*.log`, `alphaedge/logs/` ?** Oui.
- **Fragment de credential dans les logs loguru ?** Non prouvé dans le code inspecté; les logs de connexion n'impriment que `host`, `port`, `paper` via [alphaedge/engine/broker.py:152](c:/Users/averr/AlphaEdge/alphaedge/engine/broker.py#L152).
- **`Config.__repr__` masque les données sensibles ?** Non. Aucune méthode dédiée; la dataclass standard garde `account_id` visible.

---

## BLOC 2 — SÉPARATION PAPER / LIVE

### Constat positif

- Le mode paper par défaut est bien dérivé de `ALPHAEDGE_PAPER` dans [alphaedge/config/loader.py:248](c:/Users/averr/AlphaEdge/alphaedge/config/loader.py#L248).
- Le CLI affiche un avertissement explicite avant `--mode live` dans [alphaedge/engine/strategy.py:313](c:/Users/averr/AlphaEdge/alphaedge/engine/strategy.py#L313).
- En mode `--mode paper`, le code force `config.ib.is_paper = True` et `config.ib.port = 4002` dans [alphaedge/engine/strategy.py:330](c:/Users/averr/AlphaEdge/alphaedge/engine/strategy.py#L330) à [alphaedge/engine/strategy.py:332](c:/Users/averr/AlphaEdge/alphaedge/engine/strategy.py#L332).

### Problèmes

| ID | Description | Fichier:Ligne | Sévérité | Impact | Effort |
|----|-------------|---------------|----------|--------|--------|
| T-02 | La séparation paper/live est contournable: `is_paper` vient de `ALPHAEDGE_PAPER`, mais `port` peut être surchargé indépendamment via `ALPHAEDGE_IB_PORT`. Le code accepte donc un état incohérent `is_paper=True` + `port=4001`, puis `placeOrder()` soumet de vrais ordres sans garde supplémentaire. | `alphaedge/config/loader.py:248`, `alphaedge/config/loader.py:249`, `alphaedge/config/loader.py:253`, `alphaedge/engine/broker.py:140`, `alphaedge/engine/broker.py:305`, `alphaedge/engine/broker.py:346` | 🔴 | Risque de soumission réelle à IB malgré un drapeau paper affiché comme vrai | M |
| T-03 | Le mode `live` du CLI n'impose pas lui-même `config.ib.is_paper = False` ni `port = 4001`. Il dépend encore des variables d'environnement chargées juste avant. Le chemin `--mode live` est donc ambigu et non auto-cohérent. | `alphaedge/engine/strategy.py:313`, `alphaedge/engine/strategy.py:330`, `alphaedge/config/loader.py:248`, `alphaedge/config/loader.py:253` | 🟠 | Comportement non déterministe entre intention CLI et configuration réellement utilisée | S |

### Évaluation

- **Branche paper vs live clairement séparée et non contournable ?** Non.
- **`ALPHAEDGE_PAPER` lu au démarrage uniquement ?** Oui, dans `load_config()`, mais la cohérence avec le port n'est pas verrouillée.
- **En mode paper, aucun ordre réel soumis à IB ?** Non garanti par le code; la sécurité dépend du port réellement configuré, pas d'un garde-fou dans `OrderExecutor`.
- **Logs indiquent clairement PAPER ou LIVE au démarrage ?** Partiellement. Le log affiche `(paper={self._config.is_paper})` dans [alphaedge/engine/broker.py:152](c:/Users/averr/AlphaEdge/alphaedge/engine/broker.py#L152), mais ce booléen peut être incohérent avec le port réel.
- **Test couvrant le basculement paper/live ?** Non trouvé. La recherche dans `alphaedge/tests/**` ne montre que des fixtures `IBConfig(is_paper=True)` comme [alphaedge/tests/test_fill_verification.py:67](c:/Users/averr/AlphaEdge/alphaedge/tests/test_fill_verification.py#L67) ou [alphaedge/tests/test_reconnect.py:29](c:/Users/averr/AlphaEdge/alphaedge/tests/test_reconnect.py#L29), sans scénario dédié live/paper.

---

## BLOC 3 — ROBUSTESSE IB GATEWAY

### Constat positif

- Circuit breaker présent dans [alphaedge/engine/broker.py:95](c:/Users/averr/AlphaEdge/alphaedge/engine/broker.py#L95) et ouvert à [alphaedge/engine/broker.py:128](c:/Users/averr/AlphaEdge/alphaedge/engine/broker.py#L128).
- Reconnexion avec backoff exponentiel dans `BrokerConnection.reconnect()`.
- Les erreurs IB sont loggées par code dans [alphaedge/engine/broker.py:220](c:/Users/averr/AlphaEdge/alphaedge/engine/broker.py#L220) à [alphaedge/engine/broker.py:236](c:/Users/averr/AlphaEdge/alphaedge/engine/broker.py#L236).
- `reqHistoricalDataAsync` a un timeout explicite dans [alphaedge/engine/data_feed.py:244](c:/Users/averr/AlphaEdge/alphaedge/engine/data_feed.py#L244), avec retry chunké (`max_retries = 3`, `retry_delay = 60.0`) dans [alphaedge/engine/data_feed.py:379](c:/Users/averr/AlphaEdge/alphaedge/engine/data_feed.py#L379) et [alphaedge/engine/data_feed.py:382](c:/Users/averr/AlphaEdge/alphaedge/engine/data_feed.py#L382).
- La vérification de fill est implémentée avant mise à jour d'état local dans `SessionLifecycle._submit_and_await_fill()` et couverte par [alphaedge/tests/test_fill_verification.py:161](c:/Users/averr/AlphaEdge/alphaedge/tests/test_fill_verification.py#L161) et [alphaedge/tests/test_fill_verification.py:199](c:/Users/averr/AlphaEdge/alphaedge/tests/test_fill_verification.py#L199).

### Problèmes

| ID | Description | Fichier:Ligne | Sévérité | Impact | Effort |
|----|-------------|---------------|----------|--------|--------|
| T-04 | Après une déconnexion, `BrokerConnection._on_disconnect()` remplace `self._ib` par une nouvelle instance `IB()`. Le hook `SessionLifecycle._on_ib_disconnect` est branché une seule fois au démarrage sur l'ancienne instance. Après reconnexion, les futures déconnexions ne sont plus garanties de déclencher l'alerte/reconnexion au niveau stratégie. | `alphaedge/engine/strategy.py:176`, `alphaedge/engine/broker.py:147`, `alphaedge/engine/broker.py:203` | 🟠 | Première reconnexion gérée, mais déconnexions suivantes potentiellement silencieuses côté session | M |
| T-05 | Le contrôle de marge est en fail-open: si `accountSummary()` échoue, `_check_margin()` journalise l'erreur puis retourne `True`, laissant `place_bracket_order()` continuer la soumission d'ordre. | `alphaedge/engine/broker.py:318`, `alphaedge/engine/broker.py:342`, `alphaedge/engine/broker.py:346`, `alphaedge/engine/broker.py:305` | 🟠 | Un incident IB sur le résumé de compte peut laisser passer une soumission non validée | S |

### Évaluation

- **Reconnexion automatique si IB Gateway déconnecte ?** Oui pour le premier événement, via [alphaedge/engine/strategy.py:176](c:/Users/averr/AlphaEdge/alphaedge/engine/strategy.py#L176) et [alphaedge/engine/session_lifecycle.py:267](c:/Users/averr/AlphaEdge/alphaedge/engine/session_lifecycle.py#L267), mais la durabilité de ce câblage après remplacement de `self._ib` est fragile.
- **`reqHistoricalData` timeout + retry ?** Oui.
- **`placeOrder` fill vérifié avant MAJ état local ?** Oui, puis tests présents.
- **Erreur IB loggée et non swallowée ?** Oui, à plusieurs niveaux. Les `except Exception` observés utilisent `logger.exception(...)`; pas de swallow silencieux prouvé.
- **Circuit breaker sur erreurs répétées IB ?** Oui.
- **Bare except ?** Non vu sur les chemins critiques audités; uniquement `except Exception` avec logging explicite.

---

## BLOC 4 — PERSISTANCE ET RÉCUPÉRATION

### Constat positif

- Écriture atomique `.tmp → os.replace()` dans [alphaedge/utils/state_persistence.py:48](c:/Users/averr/AlphaEdge/alphaedge/utils/state_persistence.py#L48).
- Le redémarrage refuse de reprendre si `shutdown_triggered` est vrai pour la journée courante dans [alphaedge/engine/session_lifecycle.py:732](c:/Users/averr/AlphaEdge/alphaedge/engine/session_lifecycle.py#L732) à [alphaedge/engine/session_lifecycle.py:736](c:/Users/averr/AlphaEdge/alphaedge/engine/session_lifecycle.py#L736).
- Réconciliation des positions ouvertes au démarrage et après reconnexion dans [alphaedge/engine/session_lifecycle.py:294](c:/Users/averr/AlphaEdge/alphaedge/engine/session_lifecycle.py#L294) et [alphaedge/engine/session_lifecycle.py:768](c:/Users/averr/AlphaEdge/alphaedge/engine/session_lifecycle.py#L768).
- Vérification des ordres orphelins après reconnexion dans [alphaedge/engine/session_lifecycle.py:326](c:/Users/averr/AlphaEdge/alphaedge/engine/session_lifecycle.py#L326).
- La persistance est couverte par [alphaedge/tests/test_daily_state_persistence.py:129](c:/Users/averr/AlphaEdge/alphaedge/tests/test_daily_state_persistence.py#L129).

### Problèmes

| ID | Description | Fichier:Ligne | Sévérité | Impact | Effort |
|----|-------------|---------------|----------|--------|--------|
| T-06 | Le rechargement du state valide le JSON et la date, mais ne valide pas le schéma métier ni les types effectifs avant `DailyState(**data)`. Un fichier JSON bien formé mais sémantiquement incohérent peut être accepté silencieusement. | `alphaedge/utils/state_persistence.py:68`, `alphaedge/utils/state_persistence.py:69`, `alphaedge/utils/state_persistence.py:74` | 🟡 | Restauration d'un état local incohérent sans garde-fou fort | S |

### Évaluation

- **Écriture daily state atomique ?** Oui.
- **Intégrité vérifiée au rechargement ?** Partiellement seulement: parse JSON + date du jour + quelques exceptions, pas de validation de schéma complète.
- **Réconciliation positions ouvertes au redémarrage ?** Oui.
- **Position ouverte sur IB absente du state local alertée/corrigée ?** Oui, via logs de réconciliation dans [alphaedge/engine/session_lifecycle.py:309](c:/Users/averr/AlphaEdge/alphaedge/engine/session_lifecycle.py#L309) et suivants.
- **`halt_trading` persisté entre redémarrages ?** Oui, sous la forme `shutdown_triggered` persisté à [alphaedge/engine/session_lifecycle.py:634](c:/Users/averr/AlphaEdge/alphaedge/engine/session_lifecycle.py#L634) puis rechargé à [alphaedge/engine/session_lifecycle.py:733](c:/Users/averr/AlphaEdge/alphaedge/engine/session_lifecycle.py#L733).

---

## BLOC 5 — COUVERTURE DES TESTS

### Couverture existante

- Fill verification: [alphaedge/tests/test_fill_verification.py:161](c:/Users/averr/AlphaEdge/alphaedge/tests/test_fill_verification.py#L161), [alphaedge/tests/test_fill_verification.py:199](c:/Users/averr/AlphaEdge/alphaedge/tests/test_fill_verification.py#L199)
- Daily state persistence: [alphaedge/tests/test_daily_state_persistence.py:129](c:/Users/averr/AlphaEdge/alphaedge/tests/test_daily_state_persistence.py#L129)
- Alerting: [alphaedge/tests/test_alerting.py:45](c:/Users/averr/AlphaEdge/alphaedge/tests/test_alerting.py#L45)
- Dependency injection: [alphaedge/tests/test_dependency_injection.py:50](c:/Users/averr/AlphaEdge/alphaedge/tests/test_dependency_injection.py#L50)
- Reconnect: [alphaedge/tests/test_reconnect.py:70](c:/Users/averr/AlphaEdge/alphaedge/tests/test_reconnect.py#L70), [alphaedge/tests/test_reconnect.py:103](c:/Users/averr/AlphaEdge/alphaedge/tests/test_reconnect.py#L103), [alphaedge/tests/test_reconnect.py:166](c:/Users/averr/AlphaEdge/alphaedge/tests/test_reconnect.py#L166)

### Problèmes

| ID | Description | Fichier:Ligne | Sévérité | Impact | Effort |
|----|-------------|---------------|----------|--------|--------|
| T-07 | Aucun test dédié ne couvre la séparation paper/live réelle: pas de scénario `ALPHAEDGE_PAPER=true` + port live, pas de test du chemin CLI `--mode live`, et la recherche dans les tests ne montre que des fixtures `IBConfig(is_paper=True)`. | `alphaedge/engine/strategy.py:313`, `alphaedge/engine/strategy.py:330`, `alphaedge/tests/test_fill_verification.py:67`, `alphaedge/tests/test_reconnect.py:29` | 🟠 | Le défaut critique T-02 peut rester non détecté par la suite | S |

### Évaluation

- **Test paper/live séparation présent ?** Non.
- **Test fill_verification présent ?** Oui.
- **Test daily_state_persistence présent ?** Oui.
- **Test alerting présent ?** Oui.
- **Test dependency injection présent ?** Oui.
- **Scénarios manquants à risque critique ?** Oui: cohérence `is_paper`/`port`, chemin `--mode live`, second disconnect après reconnexion.

---

## SYNTHÈSE

### Verdict global

Le socle technique est sérieux sur la journalisation, les retries historiques, la persistance atomique et la vérification de fill. En revanche, la **séparation paper/live n'est pas blindée au niveau code**: elle repose trop sur la cohérence externe entre variable d'environnement et port IB. Le deuxième risque structurel est la **perte potentielle du hook de reconnexion** après remplacement de l'instance `IB()` lors d'une déconnexion.

### Tableau synthèse

| ID | Bloc | Description | Fichier:Ligne | Sévérité | Impact | Effort |
|----|------|-------------|---------------|----------|--------|--------|
| T-02 | BLOC 2 | `is_paper` et `port` peuvent diverger; aucun garde avant `placeOrder()` | `alphaedge/config/loader.py:248,249,253` ; `alphaedge/engine/broker.py:305,346` | 🔴 | Ordres réels possibles alors que le drapeau paper reste vrai | M |
| T-03 | BLOC 2 | Chemin CLI `--mode live` non auto-cohérent, dépend encore de l'env | `alphaedge/engine/strategy.py:313,330,331,332` ; `alphaedge/config/loader.py:248,253` | 🟠 | Ambiguïté opérationnelle paper/live | S |
| T-04 | BLOC 3 | Hook de session sur `disconnectedEvent` potentiellement perdu après `self._ib = IB()` | `alphaedge/engine/strategy.py:176` ; `alphaedge/engine/broker.py:147,203` | 🟠 | Déconnexions ultérieures possiblement non traitées | M |
| T-05 | BLOC 3 | Contrôle de marge fail-open en cas d'erreur IB | `alphaedge/engine/broker.py:318,342,346` | 🟠 | Soumission d'ordre malgré échec de vérification de marge | S |
| T-01 | BLOC 1 | `IBConfig` n'a pas de `__repr__` masqué pour `account_id` | `alphaedge/config/loader.py:134,140,257` | 🟡 | Fuite d'identifiant si log/debug direct du config | XS |
| T-06 | BLOC 4 | Validation de state persisté limitée au parse JSON + date | `alphaedge/utils/state_persistence.py:68,69,74` | 🟡 | Restauration d'état local incohérent possible | S |
| T-07 | BLOC 5 | Absence de tests dédiés paper/live et second disconnect | `alphaedge/engine/strategy.py:313,330` ; `alphaedge/tests/test_fill_verification.py:67` ; `alphaedge/tests/test_reconnect.py:29` | 🟠 | Régression critique non détectée | S |
