"""
session_end_summary.py — AlphaEdge SessionEnd hook (C-09).

Génère un résumé de session en fin de conversation Claude Code :
- Fichiers modifiés (git diff HEAD)
- Compte de tests actuel
- Candidat d'entrée lessons.md (affiché, jamais écrit automatiquement)

Usage : python scripts/session_end_summary.py
"""

import subprocess
import sys
from datetime import date
from pathlib import Path


def get_modified_files() -> list[str]:
    result = subprocess.run(
        ["git", "diff", "HEAD", "--name-only"],
        capture_output=True,
        text=True,
        check=False,
    )
    return [f.strip() for f in result.stdout.splitlines() if f.strip()]


def get_test_count() -> str:
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "alphaedge/tests/", "-q", "--tb=no", "--co"],
        capture_output=True,
        text=True,
        check=False,
    )
    lines = result.stdout.splitlines()
    for line in reversed(lines):
        if "test" in line and ("selected" in line or "item" in line):
            return line.strip()
    return "inconnu"


def main() -> int:
    modified = get_modified_files()
    test_count = get_test_count()
    today = date.today().isoformat()

    print("\n" + "─" * 60)
    print("📋 RÉSUMÉ FIN DE SESSION — AlphaEdge")
    print("─" * 60)
    print(f"Date        : {today}")
    print(f"Tests       : {test_count}")
    print(f"Modifiés    : {len(modified)} fichier(s)")
    for f in modified[:20]:
        print(f"  • {f}")
    if len(modified) > 20:
        print(f"  ... et {len(modified) - 20} autres")

    print(
        "\n💡 CANDIDAT LEÇON (à valider manuellement avant d'écrire dans "
        "tasks/lessons.md) :"
    )
    print("─" * 60)
    print(f"### [{today}] — <titre bref de la session>")
    print("**Contexte :** <fichier:ligne> — <description du problème>")
    print("**Erreur :** <ce qui a mal tourné ou ce qui était ambigu>")
    print("**Correction :** <ce qui a fonctionné>")
    print("**Pattern à retenir :** <règle générale applicable à l'avenir>")
    print("─" * 60)
    print("→ Utilise /lessons pour proposer une entrée complète.\n")

    lessons_path = Path("tasks/lessons.md")
    if lessons_path.exists():
        lines = lessons_path.read_text(encoding="utf-8").splitlines()
        entry_count = sum(1 for line in lines if line.startswith("### ["))
        print(f"📚 tasks/lessons.md : {entry_count} leçon(s) existante(s)")

    return 0


if __name__ == "__main__":
    sys.exit(main())
