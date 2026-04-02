# Exemple de bloc d'audit bien formé — ALPHAEDGE

> Référence pour `audit-workflow`. Copier la structure, adapter le contenu.

---

## Structure d'un bloc d'audit

Chaque bloc doit suivre exactement ce format :

```
## BLOC X — [TITRE DE LA DIMENSION]

### [ID-XX] Titre court du problème

**Fichier :** `alphaedge/chemin/fichier.py:ligne`
**Problème :** Description concise, factuelle. Citer le code concerné.
**Impact :** Conséquence concrète (ex: données perdues, erreur silencieuse, biais backtest).
**Correction :** Ce qui doit être fait, sans implémenter.
**Sévérité :** 🔴 Critique | 🟠 Majeur | 🟡 Mineur
```

---

## Exemple extrait de `audit_trade_journal_alphaedge.md`

### [J-01] PnL USD — formule incorrecte pour USDJPY

**Fichier :** `alphaedge/engine/session_lifecycle.py:362`
**Problème :**
```python
# Avant (incorrect — manque la division par exchange_rate)
pnl_usd = pnl_pips * pip_size * lot_size * 100_000
```
Le PnL EUR/USD est calculé directement en USD mais pour des paires comme USDJPY où
`exchange_rate = 150`, la conversion devrait diviser par `exchange_rate`.
**Impact :** PnL USD affiché faux pour USDJPY — toujours 150× trop haut.
**Correction :** `pnl_usd = raw_pnl / exchange_rate if exchange_rate > 0 else raw_pnl`
**Sévérité :** 🔴 Critique

---

## Tableau SYNTHÈSE obligatoire (fin de fichier)

```markdown
## SYNTHÈSE

| ID | Bloc | Description | Fichier:Ligne | Sévérité | Impact | Effort |
|----|------|-------------|--------------|----------|--------|--------|
| J-01 | Journal | PnL USD formule USDJPY | session_lifecycle.py:362 | 🔴 | PnL 150× faux | S |
| J-02 | Journal | Absence exit_reason dans CSV | live_journal.py:45 | 🟠 | Réconciliation impossible | S |
| J-03 | Journal | CSV non-atomique — perte données crash | live_journal.py:78 | 🔴 | Corruption journal | S |
```

**Confirmation dans le chat uniquement :**
```
✅ tasks/audits/resultats/audit_<type>_alphaedge.md créé
🔴 X · 🟠 X · 🟡 X
```

---

## Règles de qualité

| Règle | Obligatoire |
|-------|-------------|
| Citer `fichier:ligne` pour chaque problème | ✅ |
| Sévérité 🔴/🟠/🟡 sur chaque item | ✅ |
| Ne pas proposer de code dans l'audit (réservé au plan) | ✅ |
| Tableau SYNTHÈSE en fin de fichier | ✅ |
| Confirmation une seule ligne dans le chat | ✅ |
