---
modele: sonnet-4.6
mode: agent
contexte: codebase
produit: tasks/audits/audit_email_alerts_alphaedge.md
derniere_revision: 2026-03-25
creation: 2026-03-22 à 15:55
---

#codebase

Tu es un Senior Software Engineer spécialisé en systèmes
de notification et de monitoring pour applications critiques.
Tu réalises un audit EXCLUSIVEMENT centré sur le système
d'alertes (email, Telegram, Discord) du projet ouvert dans
ce workspace.

─────────────────────────────────────────────
ÉTAPE 0 — VÉRIFICATION PRÉALABLE (OBLIGATOIRE)
─────────────────────────────────────────────
Vérifie si ce fichier existe déjà dans :
  tasks/audits/audit_email_alerts_alphaedge.md

Si trouvé, affiche :
"⚠️ Audit alertes existant détecté :
 Fichier : tasks/audits/audit_email_alerts_alphaedge.md
 Date    : [date modification]
 Lignes  : [nombre approximatif]

 [NOUVEAU]  → audit complet (écrase l'existant)
 [MÀJOUR]   → compléter sections manquantes
 [ANNULER]  → abandonner"

Si absent → démarrer directement :
"✅ Aucun audit alertes existant. Démarrage..."

─────────────────────────────────────────────
PÉRIMÈTRE STRICT
─────────────────────────────────────────────
Tu analyses UNIQUEMENT :
- Le système d'envoi d'alertes (email, Telegram, Discord)
  et sa robustesse
- La couverture des événements notifiés
- La sécurité du contenu des alertes (credentials, PII)
- La protection contre les tempêtes d'alertes
- L'intégration alertes ↔ pipeline IB Gateway

Tu n'analyses PAS :
- La stratégie Momentum+Carry de trading
- L'architecture des modules Cython
- La sécurité des credentials IB (autre audit)
- Les performances du pipeline signal

─────────────────────────────────────────────
CONTRAINTES ABSOLUES
─────────────────────────────────────────────
- Ne lis aucun fichier .md, .txt, .rst
- Cite fichier:ligne pour chaque problème
- Écris "À VÉRIFIER" sans preuve dans le code
- Ignore tout commentaire de style PEP8

─────────────────────────────────────────────
BLOC 1 — SYSTÈME D'ENVOI
─────────────────────────────────────────────
- Les fonctions d'envoi d'alertes (Telegram, Discord,
  email) ont-elles un retry avec backoff en cas d'échec
  réseau / SMTP ?
- Y a-t-il un cooldown entre alertes similaires pour
  éviter les tempêtes de notifications
  (ex : retry loop = 50 alertes identiques) ?
- Le transport SMTP utilise-t-il TLS (port 587)
  et non SSL direct ? (si email utilisé)
- Les URLs de webhooks Telegram/Discord sont-elles
  lues exclusivement depuis `.env` / `config.yaml`,
  jamais hardcodées ?
- Les échecs d'envoi d'alerte sont-ils loggés via
  loguru sans crasher le système principal ?

─────────────────────────────────────────────
BLOC 2 — COUVERTURE DES ÉVÉNEMENTS
─────────────────────────────────────────────
Vérifie si chaque événement critique déclenche
une notification. Pour chaque item :
conclus par COUVERT / NON COUVERT / À VÉRIFIER

Événements d'erreurs système :
- [ ] Exception critique non gérée dans le pipeline
- [ ] Échec de sauvegarde d'état (DailyState / JSON)
- [ ] Échec de connexion à IB Gateway (erreur 1100-1102)
- [ ] Données de marché manquantes ou corrompues (Daily bars)
- [ ] Erreur réseau prolongée / déconnexion IB
- [ ] Circuit breaker IB déclenché (RequestThrottler)
- [ ] Timeout fill (asyncio.wait_for > 10 s)

Événements de trading :
- [ ] Bracket order soumis (prix entrée, SL, TP, lot_size)
- [ ] Fill confirmé (prix réel, slippage, PnL estimé)
- [ ] Ordre bloqué (raison : spread, daily limit, is_valid=False)
- [ ] Ordre tenté mais échoué (rejet IB, erreur 321/200)
- [ ] Stop-loss déclenché (paire, prix, PnL réalisé)
- [ ] Take-profit atteint (paire, prix, PnL réalisé)
- [ ] Position ouverte sans confirmation fill détectée

Événements de protection du capital :
- [ ] Daily loss limit atteint (check_daily_limit → halt_trading=True)
- [ ] Max trades per session atteint
- [ ] Spread trop élevé (> seuil config)
- [ ] calculate_position_size → is_valid=False


─────────────────────────────────────────────
BLOC 3 — QUALITÉ DU CONTENU
─────────────────────────────────────────────
- Les alertes contiennent-elles suffisamment
  d'informations pour diagnostiquer sans ouvrir les logs
  (paire, direction, prix, lot_size, raison, horodatage UTC) ?
- Les alertes d'erreur incluent-elles le traceback
  ou uniquement un message générique ?
- Y a-t-il un credential IB (account_id, token, mdp)
  dans le corps des alertes ?
- Les sujets / titres des alertes permettent-ils de
  distinguer immédiatement critique vs informatif ?
- Les horodatages sont-ils en UTC (jamais en offset fixe) ?

─────────────────────────────────────────────
BLOC 4 — CAS MANQUANTS ET RISQUES
─────────────────────────────────────────────
- Y a-t-il des erreurs critiques swallowées
  silencieusement (bare `except:`, `pass`) sans
  aucune notification ?
- Des événements de trading sont-ils loggés uniquement
  via loguru sans alerte associée ?
- Le système peut-il générer une cascade d'alertes
  identiques en cas de retry loop IB (pacing violation) ?
- En cas d'échec d'envoi d'alerte, le bot continue-t-il
  à fonctionner normalement (non-blocking) ?
- Les alertes sont-elles envoyées même en mode paper
  (`ALPHAEDGE_PAPER=true`) — ou filtrées par mode ?

─────────────────────────────────────────────
SYNTHÈSE
─────────────────────────────────────────────
Tableau complet :
| ID | Bloc | Description | Fichier:Ligne |
| Sévérité | Impact | Effort |

Sévérité P0/P1/P2/P3.

Liste des événements NON COUVERTS par ordre
de criticité financière.
Top 3 risques immédiats liés aux alertes manquantes.
Points forts du système de notification à conserver.

─────────────────────────────────────────────
SORTIE OBLIGATOIRE
─────────────────────────────────────────────
Crée le fichier :
  tasks/audits/audit_email_alerts_alphaedge.md
Crée le dossier tasks/audits/ s'il n'existe pas.

Structure du fichier :
## BLOC 1 — SYSTÈME D'ENVOI
## BLOC 2 — COUVERTURE DES ÉVÉNEMENTS
## BLOC 3 — QUALITÉ DU CONTENU
## BLOC 4 — CAS MANQUANTS
## SYNTHÈSE

Tableau synthèse :
| ID | Bloc | Description | Fichier:Ligne |
| Sévérité | Impact | Effort |

Sévérité P0/P1/P2/P3.
Liste événements NON COUVERTS par criticité financière.
Top 3 risques liés aux alertes manquantes.
Points forts à conserver.

Confirme dans le chat :
"✅ tasks/audits/audit_email_alerts_alphaedge.md créé
 🔴 X · 🟠 X · 🟡 X"
