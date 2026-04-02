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

    # `# type: ignore` forbidden in Python source only (not docs/config)
    if path.suffix in {".py", ".pyx"}:
        if "# type: ignore" in content:
            violations.append(
                f"  🔴 {path}: contient '# type: ignore' "
                f"(INTERDIT — trouver la vraie cause)"
            )

    # ALPHAEDGE_PAPER=false forbidden in Python/YAML application config
    # (CI workflows legitimately set PAPER=false for integration tests)
    if path.suffix in {".py", ".yaml"} and path.parts[0] != ".github":
        if "ALPHAEDGE_PAPER=" in content and "=false" in content:
            violations.append(
                f"  🔴 {path}: contient la variable de mode live interdite (INTERDIT)"
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
        # Exclude documentation/agent dirs and self
        excluded_prefixes = ("tasks/", "tasks\\", "agents/", "agents\\")
        if any(str(path).startswith(p) for p in excluded_prefixes):
            continue
        if path.name == "pre_commit_guard.py":
            continue
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
