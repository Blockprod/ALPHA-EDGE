---
modele: sonnet-4.6
mode: agent
contexte: codebase
produit: tasks/audits/AUDIT_LATENCE_ALPHAEDGE.md
derniere_revision: 2026-03-25
creation: 2026-03-23 à 20:08
usage: audit latence institutionnel avant mise en production live
---

#codebase

Tu es un Senior Low-Latency Engineer spécialisé en systèmes
de trading algorithmique institutionnel (HFT, prop trading,
market making). Tu as une expérience concrète en optimisation
de latence sur des stacks Python/Cython/asyncio connectés à des
brokers institutionnels (IBKR, FIX protocol).

─────────────────────────────────────────────
ÉTAPE 0 — VÉRIFICATION PRÉALABLE
─────────────────────────────────────────────
Vérifie si ce fichier existe déjà :
  tasks/audits/AUDIT_LATENCE_ALPHAEDGE.md

Si trouvé :
"⚠️ Audit latence existant détecté :
 Fichier : tasks/audits/AUDIT_LATENCE_ALPHAEDGE.md
 Date    : [date modification]
 Lignes  : [nombre approximatif]

 [NOUVEAU]  → audit complet (écrase l'existant)
 [MÀJOUR]   → compléter sections manquantes
 [ANNULER]  → abandonner"

Si absent → démarrer directement :
"✅ Aucun audit latence existant. Démarrage..."

─────────────────────────────────────────────
MISSION
─────────────────────────────────────────────
Réaliser un audit EXCLUSIVEMENT centré sur
la latence du système ALPHAEDGE.

L'objectif n'est pas la performance générique —
c'est d'identifier chaque milliseconde perdue
dans le pipeline de trading qui peut impacter
la qualité d'exécution et le slippage réel.

─────────────────────────────────────────────
PÉRIMÈTRE STRICT
─────────────────────────────────────────────
Tu analyses UNIQUEMENT :
- Le chemin critique signal → ordre → confirmation
- Les goulots d'étranglement dans le pipeline asyncio
- L'utilisation réelle des modules Cython vs stubs Python
- La latence des appels IBKR (TWS/Gateway)
- La starvation de l'event loop asyncio
- Les I/O synchrones dans des chemins critiques
- La qualité et la fraîcheur des données de marché

Tu n'analyses PAS :
- La validité statistique des signaux
- La sécurité des credentials
- L'organisation des modules
- La couverture des tests

─────────────────────────────────────────────
CONTRAINTES ABSOLUES
─────────────────────────────────────────────
- Ne lis aucun fichier .md, .txt, .rst existant
- Cite fichier:ligne pour chaque problème
- Mesure ou estime chaque latence en millisecondes
- Distingue latence MESURABLE (code) vs ESTIMÉE (archi)
- Écris "À MESURER EN PRODUCTION" si non quantifiable
  depuis le code statique
- Classe chaque problème :
  🔴 Critique (>10ms sur le chemin critique)
  🟠 Majeur (1-10ms ou latence non déterministe)
  🟡 Mineur (<1ms ou hors chemin critique)

─────────────────────────────────────────────
BLOC 1 — CARTOGRAPHIE DU CHEMIN CRITIQUE
─────────────────────────────────────────────
Trace le chemin complet de bout en bout :

1.1 Pipeline signal → ordre
    - Identifie chaque étape depuis la réception
      des données de marché jusqu'à l'envoi de l'ordre
    - Pour chaque étape : module concerné + fichier:ligne
    - Estime le coût en millisecondes de chaque étape
    - Identifie les étapes séquentielles vs parallèles

1.2 Chemin critique identifié
    - Quelle est la séquence d'appels la plus longue
      entre données reçues et ordre envoyé ?
    - Y a-t-il des appels bloquants sur ce chemin ?
    - Y a-t-il des locks, semaphores ou wait() ?

1.3 Latence totale estimée
    Produit un tableau :
```
    ÉTAPE              | MODULE               | LATENCE EST.
    -------------------|----------------------|-------------
    Réception données  | data_feed.py:XX      | ~X ms
    Aggregation M1     | data_feed.py:XX      | ~X ms
    Détection signal   | signal_pipeline.py:XX| ~X ms
    Validation risque  | risk_manager.pyx:XX  | ~X ms
    Envoi ordre IBKR   | broker.py:XX         | ~X ms
    Confirmation fill  | session_lifecycle:XX | ~X ms
    TOTAL              |                      | ~X ms
```

Livrable : schéma textuel du chemin critique
avec latence estimée par étape.

─────────────────────────────────────────────
BLOC 2 — CYTHON VS STUBS : RISQUE DE LATENCE CACHÉ
─────────────────────────────────────────────
C'est le risque de latence le plus dangereux
sur ALPHAEDGE — invisible en développement,
catastrophique en production.

2.1 Détection du fallback Python en production
    - Comment les modules Cython sont-ils chargés ?
      (import conditionnel, try/except, flag ?)
    - Si le `.pyd` Cython n'est pas disponible,
      le bot bascule-t-il silencieusement sur les stubs ?
    - Y a-t-il un log CRITIQUE ou une alerte si
      un stub Python est utilisé à la place du Cython ?
    - Le chemin de fallback est-il sur le chemin critique ?

2.2 Quantification de l'impact latence Cython vs stub
    Pour chaque module Cython critique :
    - `momentum_detector.pyx` : gain estimé vs stub Python
    - `risk_manager.pyx` : gain estimé vs stub Python
    - `order_manager.pyx` : gain estimé vs stub Python

2.3 Vérification du flag CYTHON_AVAILABLE
    - Le flag de disponibilité Cython est-il vérifié
      au démarrage avec une alerte explicite ?
    - Est-il loggé en CRITICAL si Cython est absent ?
    - Le bot devrait-il refuser de démarrer sans Cython
      en mode production ?

Livrable : tableau CYTHON ACTIF / STUB ACTIF / AMBIGU
pour chaque module, avec impact latence estimé.

─────────────────────────────────────────────
BLOC 3 — LATENCE DES APPELS IBKR
─────────────────────────────────────────────
3.1 Architecture de connexion IBKR
    - TWS ou IBGateway ? Connexion locale ou distante ?
    - Le client IBKR tourne-t-il dans l'event loop asyncio
      ou dans un thread séparé (ib_insync utilise les deux) ?
    - Les callbacks IBKR sont-ils traités dans l'event loop
      principal ou dispatchés vers une queue asynchrone ?

3.2 Appels bloquants sur le chemin critique
    - Y a-t-il des appels IBKR synchrones
      (reqContractDetails, reqMktData, reqPositions)
      sur le chemin critique de génération de signal ?
    - Ces appels ont-ils un timeout configuré ?
    - Y a-t-il des `await asyncio.sleep(X)` fixes
      introduits pour attendre une réponse IBKR
      (ex : reqMktData → sleep → lire résultat) ?
      Ces sleeps hardcodés sont particulièrement
      coûteux : cherche-les exhaustivement.
    - Que se passe-t-il si IBKR ne répond pas
      dans les délais attendus ?

3.3 Latence d'envoi d'ordre
    - Comment l'ordre est-il construit et envoyé ?
      (placeOrder, bracketOrder, etc.)
    - Y a-t-il une validation pré-envoi qui ajoute
      de la latence (filtres, checks de risque) ?
    - La confirmation de fill est-elle attendue
      avant de continuer le cycle ?

3.4 Rate limiting IBKR
    - Le token bucket IBKR (45 req/s configuré dans
      constants.py via IB_MAX_REQUESTS_PER_SECOND)
      introduit-il des pauses sur le chemin critique ?
    - Y a-t-il un mécanisme de priorité pour les
      ordres vs les requêtes de données ?
    - Le semaphore sur les requêtes historiques
      (IB_MAX_CONCURRENT_HIST_REQUESTS) peut-il bloquer
      le chemin critique si les 3 slots sont occupés ?

Livrable : liste des appels IBKR bloquants avec
latence estimée et fichier:ligne.

─────────────────────────────────────────────
BLOC 4 — EVENT LOOP ASYNCIO ET STARVATION
─────────────────────────────────────────────
⚠️ ALPHAEDGE est entièrement asyncio (zéro thread manuel).
Le risque n'est PAS la contention du GIL Python —
c'est la STARVATION DE L'EVENT LOOP : un callback
trop long bloque tout le cycle, retardant les autres
coroutines en attente.

4.1 Callbacks sur l'event loop
    - `_on_new_m1_bar()` est le callback central de
      réception des données. Quelle est sa durée estimée ?
      Appelle-t-il directement du code Cython bloquant
      (sans await), ou dispatche-t-il une coroutine ?
    - Y a-t-il d'autres callbacks ib_insync susceptibles
      de bloquer l'event loop (barUpdateEvent, etc.) ?

4.2 Sections synchrones sur l'event loop
    - Y a-t-il des calculs CPU-intensifs appelés
      DIRECTEMENT (sans `asyncio.run_in_executor`)
      dans une coroutine sur le chemin critique ?
      Les appels Cython sont synchrones et bloquent
      l'event loop pendant leur durée — est-ce acceptable
      au vu de leur temps d'exécution estimé ?
    - Des fichiers de config ou de state sont-ils
      lus/écrits de manière synchrone dans une coroutine ?

4.3 Trade lock contention
    - `asyncio.Lock` sur `_atomic_check_and_execute()` :
      si 2 signaux arrivent sur des paires différentes
      simultanément, l'un bloque l'autre.
      Ce cas est-il possible en pratique (multi-pair) ?
      La section protégée par le lock est-elle minimisée ?

4.4 Cadence de la boucle principale
    - La boucle `while is_session_active()` avec
      `await asyncio.sleep(1.0)` cadence-t-elle
      des actions critiques ? Peut-elle retarder
      la détection d'un signal jusqu'à 1s ?
    - Les risk checks (5s position ouverte, 30s idle)
      sont-ils calculés via compteur dans cette boucle ?

─────────────────────────────────────────────
BLOC 5 — I/O SYNCHRONES SUR LE CHEMIN CRITIQUE
─────────────────────────────────────────────
5.1 I/O fichier et sleeps sur le chemin critique
    - Y a-t-il des écritures de log synchrones
      (logging.INFO, print) dans le chemin critique ?
    - La persistance de l'état (bot_state.json ou
      équivalent) est-elle appelée sur le chemin critique ?
    - Des fichiers de config sont-ils relus à chaque cycle ?
    - POINT D'ATTENTION : cherche exhaustivement les
      `await asyncio.sleep(X)` fixes sur le chemin critique.
      En particulier, les appels qui attendent une réponse
      IBKR via un sleep hardcodé au lieu d'un vrai await
      sur un event constituent une latence garantie à chaque
      cycle — quelle qu'en soit la valeur.

5.2 I/O réseau hors IBKR
    - Y a-t-il des appels HTTP externes sur le
      chemin critique (APIs de données, webhooks) ?
    - Ces appels ont-ils un timeout strict ?
    - Sont-ils mis en cache pour éviter les appels
      répétés dans un même cycle ?

─────────────────────────────────────────────
BLOC 6 — QUALITÉ ET FRAÎCHEUR DES DONNÉES
─────────────────────────────────────────────
6.1 Fraîcheur des données de marché
    - Comment l'âge des données est-il mesuré ?
    - Y a-t-il un seuil d'obsolescence au-delà duquel
      le bot refuse de trader ?
    - Les données sont-elles timestampées à la réception
      ou au moment du calcul ?

6.2 Latence de la source de données
    - Les données viennent-elles de l'API IBKR
      (market data subscription) ou d'une source tierce ?
    - Y a-t-il un buffer ou une queue entre la réception
      des données et leur utilisation ?
    - Le buffer peut-il introduire des données périmées
      si le traitement est lent ?

6.3 Synchronisation des timestamps
    - Les timestamps locaux sont-ils synchronisés
      avec le serveur IBKR ?
    - L'offset calculé est-il appliqué aux données
      de marché ou uniquement aux ordres ?

─────────────────────────────────────────────
BLOC 7 — RÉCUPÉRATION ET LATENCE DE RÉSILIENCE
─────────────────────────────────────────────
7.1 Temps de reconnexion IBKR
    - En cas de déconnexion TWS/Gateway, quel est
      le temps de reconnexion estimé ?
    - Les ordres en cours sont-ils annulés ou
      maintenus pendant la déconnexion ?
    - La reconnexion bloque-t-elle l'event loop principal ?

7.2 Temps de reprise après crash
    - Combien de temps pour recharger l'état complet
      depuis la persistance ?
    - La réconciliation avec IBKR au démarrage
      introduit-elle un délai avant le premier cycle ?
    - Y a-t-il un mode "warm start" vs "cold start" ?

7.3 Latence du circuit breaker
    - Quand le circuit breaker se déclenche,
      quelle est la latence avant reprise ?
    - Le timeout de reset est-il configuré pour
      minimiser le temps hors marché ?

─────────────────────────────────────────────
SYNTHÈSE FINALE
─────────────────────────────────────────────
Tableau complet :
| ID | Bloc | Description | Fichier:Ligne |
| Sévérité | Latence estimée | Effort correction |

Sévérité :
🔴 Critique (>10ms chemin critique)
🟠 Majeur (1-10ms ou non déterministe)
🟡 Mineur (<1ms ou hors chemin critique)

Produit également :

1. Budget latence total estimé
```
   Latence signal → ordre (cible) : < X ms
   Latence signal → ordre (actuel): ~ X ms
   Écart à combler                 : X ms
```

2. Top 3 optimisations prioritaires
   Les 3 corrections qui réduiraient le plus
   la latence sur le chemin critique.

3. Ce qui est déjà optimal
   Mécanismes de latence déjà bien gérés
   à ne pas modifier.

4. Recommandations de mesure en production
   Comment instrumenter le code pour mesurer
   la latence réelle (non estimée) :
   - Points de mesure recommandés
   - Outils : `time.perf_counter_ns()`, `cProfile`,
     `py-spy`, `perf` Linux

─────────────────────────────────────────────
SORTIE OBLIGATOIRE
─────────────────────────────────────────────
Crée le fichier :
  tasks/audits/audit_latence_alphaedge.md
Crée le dossier tasks/audits/ s'il n'existe pas.

Structure du fichier :
## BLOC 1 — CHEMIN CRITIQUE
## BLOC 2 — CYTHON VS STUBS
## BLOC 3 — LATENCE IBKR
## BLOC 4 — EVENT LOOP ET STARVATION
## BLOC 5 — I/O SYNCHRONES
## BLOC 6 — QUALITÉ DES DONNÉES
## BLOC 7 — RÉSILIENCE
## SYNTHÈSE

Confirme dans le chat :
"✅ tasks/audits/audit_latence_alphaedge.md créé
 🔴 X · 🟠 X · 🟡 X
 Latence estimée chemin critique : ~X ms
 Top optimisation : [titre]"
```

---



