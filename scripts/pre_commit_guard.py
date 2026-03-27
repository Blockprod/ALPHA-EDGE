"""
pre_commit_guard.py — AlphaEdge pre-commit safety check.

Vérifie dans les fichiers stagés git :
1. Pas de ALPHAEDGE_PAPER=FALSE (ne jamais écrire la version minuscule exacte)
2. Pas de # type: ignore
3. Pas de fichier .env

Usage : python scripts/pre_commit_guard.py
Exit 0 = OK · Exit 1 = violation trouvée
"""

import subprocess
import sys
from pathlib import Path


def get_staged_files() -> list[str]:
    result = subprocess.run(
        ["git", "diff", "--cached", "--name-only"],
        capture_output=True,
        text=True,
        check=False,
    )
    return [f.strip() for f in result.stdout.splitlines() if f.strip()]


def check_file(path: Path) -> list[str]:
    violations: list[str] = []
    try:
        content = path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return violations

    if "ALPHAEDGE_PAPER=false" in content:
        # Interdit : ALPHAEDGE_PAPER=false (minuscule exact)
        violations.append(f"  🔴 {path}: contient ALPHAEDGE_PAPER=FALSE (INTERDIT)")

    if "# type: ignore" in content:
        violations.append(
            f"  🔴 {path}: contient '# type: ignore' "
            f"(INTERDIT — trouver la vraie cause)"
        )

    return violations


def main() -> int:
    staged = get_staged_files()
    violations: list[str] = []

    for filename in staged:
        # Blocklist : fichiers .env jamais committables
        if filename == ".env" or filename.endswith("/.env"):
            violations.append(
                f"  🔴 {filename}: fichier .env stagé "
                f"(INTERDIT — contient des credentials)"
            )
            continue

        path = Path(filename)
        if path.suffix in {".py", ".pyx", ".yaml", ".yml", ".toml", ".json", ".md"}:
            violations.extend(check_file(path))

    if violations:
        print("❌ pre_commit_guard — violations détectées :\n")
        for v in violations:
            print(v)
        print("\nCorrige ces violations avant de committer.")
        return 1

    print(f"✅ pre_commit_guard — {len(staged)} fichiers stagés · aucune violation")
    return 0


if __name__ == "__main__":
    sys.exit(main())
