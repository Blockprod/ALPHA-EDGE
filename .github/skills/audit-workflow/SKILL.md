---
name: audit-workflow
description: >
  Use when: launching any audit (structural, technical, best practices, etc.),
  generating an action plan from an audit result, or executing corrections
  from an action plan. This skill covers the full A → B → C pipeline.
---

# Skill — audit-workflow

## When to invoke this skill

- Starting a new audit of any type (structural, technical, cython, latence…)
- Generating an action plan from a completed audit result
- Executing corrections from an action plan
- Checking which audits have been run and which are pending

## Pipeline A → B → C (mandatory order)

```
A — Audit        → tasks/audits/resultats/audit_<type>_alphaedge.md
B — Action Plan  → tasks/corrections/plans/PLAN_ACTION_<type>_[DATE].md
C — Execution    → corrections applied, make qa green
```

> **Never launch B without A complete.**
> **Never mark C done without `make qa` green (504 tests).**

## Steps

### A — Audit
```
#file:tasks/audits/code/<type>_prompt.md      ← pour audits code
#file:tasks/audits/methode/<type>_prompt.md   ← pour audits méthode
Lance cet audit sur le workspace.
```

### B — Generate Action Plan
```
#file:tasks/corrections/generate_action_plan_prompt.md
Génère le plan d'action depuis l'audit disponible.
```

### C — Execute Corrections
```
#file:tasks/corrections/execute_corrections_prompt.md
Démarre l'exécution du plan d'action disponible.
```

## Available Audits

Full list of audits + sections: `tasks/WORKFLOW.md`

| Type | Prompt location |
|------|----------------|
| Structural, Technical, Cython, Strategic, Latence, Master | `tasks/audits/code/` |
| AI-Driven, IA/ML, Best Practices | `tasks/audits/methode/` |

## Common Errors

| Error | Cause | Fix |
|-------|-------|-----|
| Audit result vague, no file:line | Agent didn't cite sources | Re-run audit in Agent mode with `#codebase` |
| Action plan launched before audit done | Skipped step A | Always check `tasks/audits/resultats/` first |
| Correction marked ✅ without `make qa` | Incomplete validation | Run `make qa` and verify 504 tests pass |
| lessons.md not updated after correction | Skipped lesson capture | Add lesson before marking task complete |
| `.pyx` modified without `make build` | Silently broken runtime | Always `make build` then `make qa` after .pyx change |

## Session Startup (do this first)

1. Read `tasks/lessons.md`
2. Read `docs/ALPHAEDGE_STRUCTURAL_ACTION_PLAN.md`
3. Run `make qa` — confirm baseline green
