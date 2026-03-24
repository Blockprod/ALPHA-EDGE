---
modele: sonnet-4.6
mode: agent
contexte: codebase
produit: audit_best_practices_alphaedge.md
derniere_revision: 2026-03-24
creation: 2026-03-24 à 13:20
---

#codebase

<investigate_before_answering>
Toujours lire le contenu complet de ce fichier prompt avant de vérifier si un
audit existant est encore valide. Si une nouvelle source a été ajoutée ou si
une instruction a changé, relancer l'audit — ne pas réutiliser un résultat antérieur.
</investigate_before_answering>

Voici 4 sources de "best practices" pour les projets
utilisant Claude et GitHub Copilot dans VSCode :

  https://github.com/shanraisshan/claude-code-best-practice
  https://claude.com/fr-fr/blog/using-claude-md-files
  https://claude.com/fr-fr/product/overview
  https://platform.claude.com/docs/en/home

─────────────────────────────────────────────
MISSION
─────────────────────────────────────────────

<instructions>
1. Lis le contenu de chacun de ces 4 liens
2. Analyse l'ensemble du projet EDGECORE pour
   cartographier ce qui est déjà en place
3. Identifie les best practices présentes dans
   ces sources qui NE SONT PAS encore utilisées
   dans le projet
4. Pour chaque best practice identifiée, évalue
   sa pertinence dans le contexte exact du projet :
   Claude Sonnet 4.6 via Copilot Pro+ dans VSCode
   (pas Claude Code CLI, pas d'API directe)
</instructions>

─────────────────────────────────────────────
FILTRE OBLIGATOIRE
─────────────────────────────────────────────

<filter>
⚠️ Certaines best practices des sources sont
spécifiques à Claude Code CLI (outil terminal)
ou à l'API Anthropic directe.

Ces pratiques sont NON PERTINENTES pour ce projet
et doivent être classées séparément :

Exclure automatiquement :
- Tout ce qui nécessite la commande `claude` en CLI
- Tout ce qui nécessite un token API Anthropic
- Les hooks Claude Code (PreToolUse, PostToolUse)
- Les commandes slash Claude Code (/compact, /init…)
- Les fichiers CLAUDE.md auto-exécutés par Claude Code
  (ils restent utiles comme contexte Copilot mais
   leur comportement est différent — à signaler)

Conserver et évaluer :
- Les pratiques applicables via #codebase ou #file
  dans Copilot Chat VSCode
- Les fichiers de contexte (.github/copilot-instructions.md,
  .claude/context.md, .claude/rules.md)
- Les structures de prompts réutilisables dans tasks/
- Les patterns d'organisation de repo pour l'IA
- Les pratiques de documentation orientées IA
</filter>

─────────────────────────────────────────────
FORMAT DE SORTIE
─────────────────────────────────────────────

<output_format>
Fichier produit : tasks/audits/resultats/audit_best_practices_alphaedge.md
Sections obligatoires :
1. Header (Date · Sources analysées · Stack · Scope)
2. Tableau BEST PRACTICES DÉJÀ EN PLACE
   | Practice | Source | Fichier:Ligne | Statut |
3. Sections BEST PRACTICES MANQUANTES (BP-XX)
   — une section ### par pratique, avec :
   Source · Description · Pourquoi pertinent ·
   Comment appliquer · Effort (XS/S/M/L) · Impact
4. Tableau BEST PRACTICES NON APPLICABLES (CLI)
5. Tableau SYNTHÈSE PRIORITAIRE
</output_format>

─────────────────────────────────────────────
EXEMPLES DE FORMAT ATTENDU
─────────────────────────────────────────────

<examples>
  <example>
    <!-- Cas 1 : Best practice déjà en place -->
    | CLAUDE.md au root — fichier de contexte chargé à chaque session | Anthropic blog | CLAUDE.md:1 | ✅ |
  </example>
  <example>
    <!-- Cas 2 : Best practice manquante, pertinente -->
    ### BP-XX — Titre court

    **Source :** shanraisshan · Anthropic blog
    **Description :** Une phrase décrivant la pratique.
    **Pourquoi pertinent pour ALPHAEDGE + Copilot VSCode :**
    Explication contextualisée au projet et au stack.
    **Comment l'appliquer concrètement :**
      - Étape 1
      - Étape 2
    **Effort :** S
    **Impact estimé :** Une ligne de résultat attendu.
  </example>
  <example>
    <!-- Cas 3 : Best practice non applicable (CLI uniquement) -->
    | Hooks PreToolUse/PostToolUse | shanraisshan | Requiert la commande `claude` CLI |
  </example>
</examples>

─────────────────────────────────────────────
CONTRAINTES
─────────────────────────────────────────────
- Base chaque recommandation sur le code réel
  du projet — pas de généralités
- Pour chaque best practice déjà en place :
  cite le fichier:ligne qui le prouve
- Pour chaque best practice manquante et pertinente :
  explique concrètement comment l'appliquer
  à EDGECORE avec Copilot Pro+ dans VSCode
- Verdict pour chaque best practice :
  ✅ DÉJÀ EN PLACE
  ❌ MANQUANT — PERTINENT (Copilot VSCode)
  ⚠️ PARTIEL
  🚫 NON APPLICABLE (Claude Code CLI uniquement)

─────────────────────────────────────────────
SORTIE OBLIGATOIRE
─────────────────────────────────────────────
Crée le fichier :
  tasks/audits/audit_best_practices_alphaedge.md
Crée le dossier tasks/audits/ s'il n'existe pas.

Structure du fichier :

# AUDIT BEST PRACTICES — EDGECORE — [DATE]
Sources analysées : [liste des 3 URLs]
Stack : Claude Sonnet 4.6 · Copilot Pro+ · VSCode

## BEST PRACTICES DÉJÀ EN PLACE
| Practice | Source | Fichier:Ligne | Statut |

## BEST PRACTICES MANQUANTES — PERTINENTES COPILOT
Pour chaque item :
### [Titre de la best practice]
**Source** : [URL]
**Description** : [ce que c'est]
**Pourquoi pertinent pour EDGECORE + Copilot VSCode** :
**Comment l'appliquer concrètement** :
  - Fichier à créer ou modifier
  - Contenu exact à ajouter
  - Commande Copilot pour l'utiliser (#file, #codebase…)
**Effort** : XS / S / M / L
**Impact estimé** : [bénéfice concret]

## BEST PRACTICES NON APPLICABLES (Claude Code CLI)
| Practice | Source | Raison |

## BEST PRACTICES MANQUANTES — NON PERTINENTES
| Practice | Source | Raison de non-pertinence |

## SYNTHÈSE ET PRIORITÉS
| Priorité | Practice | Effort | Impact |

Confirme dans le chat :
"✅ audit_best_practices_alphaedge.md créé
 ✅ Déjà en place        : X
 ❌ Pertinentes Copilot  : X
 🚫 Claude Code CLI only : X
 ➡️ Priorité 1 : [titre]"
