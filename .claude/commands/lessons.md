# /lessons — Consulter et enrichir tasks/lessons.md

## Lecture
Afficher le contenu complet de `tasks/lessons.md`.

## Analyse
Identifier les patterns récurrents dans les leçons existantes :
- Erreurs répétées (type errors, import circulaires, etc.)
- Patterns de correction qui fonctionnent systématiquement
- Anti-patterns à éviter

## Proposition de nouvelle entrée
Si la session courante a produit une correction notable, proposer une nouvelle entrée :

```markdown
### [DATE] — <titre bref>
**Contexte :** <fichier:ligne> — <description du problème>
**Erreur :** <ce qui a mal tourné ou ce qui était ambigu>
**Correction :** <ce qui a fonctionné>
**Pattern à retenir :** <règle générale applicable à l'avenir>
```

Attendre validation avant d'écrire dans `tasks/lessons.md`.

## Règles
- Ne jamais écrire dans `tasks/lessons.md` sans montrer le diff d'abord
- Une leçon = un pattern précis, pas une généralité
- Si la leçon existe déjà → enrichir l'entrée existante plutôt que dupliquer
