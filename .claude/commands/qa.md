# /qa — Lance make qa et résume le résultat

Exécute la commande suivante dans le terminal :

```powershell
.\.venv\Scripts\Activate.ps1 ; make qa
```

Analyse la sortie et affiche :

```
📊 QA AlphaEdge
─────────────────
Ruff   : ✅ 0 erreur  /  ❌ X erreurs
Mypy   : ✅ 0 erreur  /  ❌ X erreurs
Tests  : ✅ X passés  /  ❌ X échoués (baseline attendue : 610+)
─────────────────
Statut : ✅ GREEN  /  ❌ RED
```

Si RED :
- Liste les erreurs groupées par type (Ruff / Mypy / Pytest)
- Propose une correction ciblée pour chaque erreur
- Ne passe PAS à la suite tant que QA n'est pas GREEN
