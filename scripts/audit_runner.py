#!/usr/bin/env python3
"""
ALPHAEDGE Code Modernization & Audit Script - Version Propre
Traitement dossier par dossier avec correction automatique des ARG001
"""

import re
import subprocess
from datetime import datetime
from pathlib import Path


class AlphaEdgeAuditRunner:
    def __init__(self) -> None:
        self.project_root = self.find_project_root()
        self.start_time = datetime.now()
        self.stats: dict[str, int] = {
            "directories": 0,
            "files_modified": 0,
            "ruff_fixed": 0,
            "arg_fixed": 0,
            "f401_fixed": 0,
        }

    def find_project_root(self) -> Path:
        """Trouve la racine du projet AlphaEdge."""
        current = Path.cwd()
        while current != current.parent:
            if (current / "alphaedge").exists() and (current / "setup.py").exists():
                return current
            current = current.parent
        # Fallback
        return Path(r"C:\Users\averr\AlphaEdge")

    def run_command(self, cmd: list[str], cwd: Path | None = None) -> tuple[int, str]:
        """Exécute une commande et retourne (code, output)."""
        try:
            result = subprocess.run(
                cmd,
                cwd=cwd or self.project_root,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                check=False,
            )
            return result.returncode, result.stdout + result.stderr
        except Exception as exc:  # pragma: no cover - logging simple
            return 1, f"Exception: {exc}"

    def fix_unused_arguments(self, file_path: Path) -> int:
        """Corrige automatiquement les ARG001 en renommant les paramètres en _nom."""
        if not file_path.exists():
            return 0

        try:
            content = file_path.read_text(encoding="utf-8")
            fixed_count = 0

            # Récupérer les erreurs ARG001 pour ce fichier
            _, output = self.run_command(
                [
                    "ruff",
                    "check",
                    str(file_path),
                    "--select",
                    "ARG",
                    "--output-format",
                    "text",
                ],
            )

            for line in output.splitlines():
                if "ARG001" not in line or "`" not in line:
                    continue

                match = re.search(r"Unused function argument: `([^`]+)`", line)
                if not match:
                    continue

                param_name = match.group(1).strip()
                if param_name.startswith("_"):
                    continue

                # Remplacement prudent dans la signature de fonction
                pattern = re.compile(
                    r"(?<!\w)" + re.escape(param_name) + r"(?=\s*[:,\)])",
                )
                new_content = pattern.sub("_" + param_name, content)

                if new_content != content:
                    content = new_content
                    fixed_count += 1
                    print(
                        "      ✅ ARG001 corrigé : "
                        f"{param_name} → _{param_name} dans {file_path.name}",
                    )

            if fixed_count > 0:
                file_path.write_text(content, encoding="utf-8")
                self.stats["arg_fixed"] += fixed_count
                self.stats["files_modified"] += 1

            return fixed_count

        except Exception as exc:  # pragma: no cover - logging simple
            print(
                "      ⚠️  Erreur lors de la correction ARG "
                f"dans {file_path.name}: {exc}",
            )
            return 0

    def fix_directory(self, directory: Path) -> bool:
        """Corrige tous les fichiers d'un dossier avec détection et correction fine."""
        # Path.is_relative_to n'existe qu'à partir de 3.9, gestion manuelle
        try:
            rel_path = directory.relative_to(self.project_root)
        except ValueError:
            rel_path = directory

        print(f"\n{'=' * 70}")
        print(f"📁 Traitement du dossier : {rel_path}")
        print(f"{'=' * 70}")

        # 1. Ruff auto-fix complet
        print("  🔧 Exécution de Ruff auto-fix...")
        self.run_command(["ruff", "check", str(directory), "--fix"])
        self.run_command(["ruff", "check", str(directory), "--fix", "--unsafe-fixes"])
        self.stats["ruff_fixed"] += 1

        # 2. Détection et correction ARG001
        print("  🔍 Détection et correction paramètres orphelins (ARG001)...")
        _, arg_output = self.run_command(
            ["ruff", "check", str(directory), "--select", "ARG"],
        )
        arg_errors = [line for line in arg_output.splitlines() if "ARG001" in line]

        if arg_errors:
            print(
                f"    ⚠️  {len(arg_errors)} ARG001 détectés — Correction automatique...",
            )
            for file_line in arg_errors:
                if ":" not in file_line:
                    continue
                file_part = file_line.split(":", 1)[0].strip()
                file_path = Path(file_part)
                if file_path.exists() and file_path.is_file():
                    self.fix_unused_arguments(file_path)

        # 3. Vérification F401
        print("  🔍 Vérification imports masqués (F401)...")
        _, f401_output = self.run_command(
            ["ruff", "check", str(directory), "--select", "F401", "--ignore-noqa"],
        )
        f401_errors = [line for line in f401_output.splitlines() if "F401" in line]
        if f401_errors:
            print(
                f"    ⚠️  {len(f401_errors)} imports morts masqués détectés",
            )
            self.stats["f401_fixed"] += len(f401_errors)

        # 4. Vérification finale Ruff
        print("  ✅ Vérification finale Ruff...")
        _, final_output = self.run_command(["ruff", "check", str(directory)])
        if "All checks passed" in final_output or not final_output.strip():
            print("    ✓ Ruff : OK")
        else:
            print("    ⚠️  Issues restantes (consultez le menu PROBLEMS) :")
            print(final_output[:400])

        return True

    def run(self) -> None:
        """Exécute l'audit complet dossier par dossier."""
        print("=" * 70)
        print("🚀 ALPHAEDGE Code Modernization & Audit")
        print(f"📂 Projet : {self.project_root}")
        print(f"🕐 Début : {self.start_time.strftime('%H:%M:%S')}")
        print("=" * 70)

        print("\n📊 Scan du projet en cours...")
        cmd = [
            "powershell",
            "-Command",
            (
                f'Get-ChildItem -Path "{self.project_root}" '
                '-Filter "*.py" -Recurse -File | '
                r"Where-Object { $_.FullName -notmatch "
                r'"(__pycache__|\.venv|\\build\\|\.git)" } | '
                "Select-Object -ExpandProperty DirectoryName | "
                "Sort-Object -Unique"
            ),
        ]
        _, output = self.run_command(cmd)

        directories: list[Path] = []
        for line in output.strip().splitlines():
            if not line or line.startswith("DirectoryName"):
                continue
            dir_path = Path(line.strip())
            if dir_path.exists():
                directories.append(dir_path)

        if (
            self.project_root / "setup.py"
        ).exists() and self.project_root not in directories:
            directories.insert(0, self.project_root)

        # Priorité aux stubs Cython
        stubs_dir = self.project_root / "alphaedge" / "core" / "_stubs"
        if stubs_dir in directories:
            directories.remove(stubs_dir)
            directories.insert(0, stubs_dir)

        # Unicité tout en gardant l'ordre
        directories = list(dict.fromkeys(directories))

        print(f"  ✅ {len(directories)} dossiers identifiés\n")
        self.stats["directories"] = len(directories)

        for index, directory in enumerate(directories, 1):
            print(f"\n📌 [{index}/{len(directories)}]")
            self.fix_directory(directory)

            if index < len(directories):
                response = input(
                    "\n➡️  Passer au dossier suivant ? "
                    "(GO pour continuer, STOP pour arrêter) : ",
                )
                if response.upper() != "GO":
                    print("⏸️  Arrêt demandé par l'utilisateur.")
                    break

        self.run_final_verification()

    def run_final_verification(self) -> None:
        """Vérification finale globale du projet."""
        print("\n" + "=" * 70)
        print("🔍 VÉRIFICATION FINALE GLOBALE")
        print("=" * 70)

        print("\n1. Ruff global...")
        _, ruff_out = self.run_command(["ruff", "check", "alphaedge/"])
        ruff_ok = "All checks passed" in ruff_out or not ruff_out.strip()

        print("\n2. Paramètres orphelins (ARG)...")
        _, arg_out = self.run_command(
            ["ruff", "check", "alphaedge/", "--select", "ARG"],
        )
        arg_ok = "All checks passed" in arg_out or not arg_out.strip()

        print("\n3. Imports masqués (F401)...")
        _, f401_out = self.run_command(
            ["ruff", "check", "alphaedge/", "--select", "F401", "--ignore-noqa"],
        )
        f401_ok = "All checks passed" in f401_out or not f401_out.strip()

        print("\n4. Exécution des tests (make qa)...")
        _, test_out = self.run_command(["make", "qa"])
        lower_test_out = test_out.lower()
        tests_ok = "passed" in lower_test_out and "failed" not in lower_test_out

        duration = datetime.now() - self.start_time

        print("\n" + "=" * 70)
        print("📊 RAPPORT FINAL")
        print("=" * 70)
        print(
            f"""
✅ Audit terminé — ALPHAEDGE
   Durée d'exécution               : {duration.total_seconds():.1f} secondes
   Dossiers traités                : {self.stats["directories"]}
   Fichiers modifiés              : {self.stats["files_modified"]}

   Corrections appliquées :
   - Ruff auto-fix                 : ✅ ({self.stats["ruff_fixed"]})
   - ARG001 (paramètres orphelins) : {self.stats["arg_fixed"]} corrigés
   - F401 (imports masqués)        : {self.stats["f401_fixed"]} détectés

   Vérification finale :
   - Ruff global                   : {"✅" if ruff_ok else "❌"}
   - ARG (orphelins)               : {"✅" if arg_ok else "❌"}
   - F401 (imports masqués)        : {"✅" if f401_ok else "❌"}
   - Tests (make qa)               : {"✅" if tests_ok else "❌"}
""",
        )

        if ruff_ok and arg_ok and f401_ok and tests_ok:
            print("🎉 SUCCÈS TOTAL — Le code est propre et les tests passent.")
        else:
            print("⚠️  Certaines vérifications ont échoué. Consultez le menu PROBLEMS.")


def main() -> None:
    runner = AlphaEdgeAuditRunner()
    runner.run()


if __name__ == "__main__":
    main()
