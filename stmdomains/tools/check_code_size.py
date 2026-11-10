"""Check physical lines in changed STM Domains source files and tests."""

import argparse
from pathlib import Path
import subprocess


CODE_SUFFIXES = {".py", ".js", ".ts", ".jsx", ".tsx", ".css", ".html", ".sh", ".qml", ".ui"}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", default="HEAD", help="Git ref to compare (default: HEAD)")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[2]

    def git(*arguments: str) -> list[str]:
        return subprocess.check_output(["git", *arguments], cwd=root, text=True).splitlines()

    scope = ["stmdomains", "tests/stmdomains"]
    paths = set(git("diff", "--name-only", "--diff-filter=ACMR", args.base, "--", *scope))
    paths.update(git("ls-files", "--others", "--exclude-standard", "--", *scope))
    failed = False
    checked = 0
    for name in sorted(paths):
        path = root / name
        if not path.is_file() or path.suffix not in CODE_SUFFIXES:
            continue
        count = len(path.read_text(encoding="utf-8").splitlines())
        checked += 1
        label = "OK" if count <= 1000 else "WYMAGA UZASADNIENIA" if count <= 1500 else "BŁĄD"
        failed |= count > 1500
        print(f"{label}: {count:4d} linii — {name}")
    print(f"Sprawdzono {checked} plików. Cel: 1000; twardy limit: 1500 linii.")
    return int(failed)


if __name__ == "__main__":
    raise SystemExit(main())
