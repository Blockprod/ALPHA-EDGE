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

    # Interdit : détection de la variable de mode live (jamais la chaîne brute)
    if "ALPHAEDGE_PAPER=" in content and "=false" in content:
        violations.append(
            f"  🔴 {path}: contient la variable de mode live interdite (INTERDIT)"
        )

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
