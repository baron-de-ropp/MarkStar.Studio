"""Stamp the release version (from the pushed git tag) into the source.

Run in CI *before* building so the frozen binary's ``--version`` and the
package metadata always match the tag — no manual bump can drift out of sync
(as ``__version__`` did, stuck at 0.1.0 while the package shipped 0.2.0).

The tag comes from ``$GITHUB_REF_NAME`` (e.g. "v0.2.1"); a leading "v" is
stripped. Reading the env var — rather than a shell ``${VAR#v}`` expansion —
keeps this identical under bash (Linux/macOS) and PowerShell (Windows).
"""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path


def main() -> None:
    ref = os.environ.get("GITHUB_REF_NAME", "")
    version = ref[1:] if ref.startswith("v") else ref
    if not re.fullmatch(r"\d+\.\d+\.\d+([.\-+].+)?", version):
        sys.exit(f"refusing to stamp non-version tag: {ref!r}")

    root = Path(__file__).resolve().parent.parent

    init = root / "src" / "markstar" / "__init__.py"
    init.write_text(
        re.sub(
            r'__version__ = "[^"]*"',
            f'__version__ = "{version}"',
            init.read_text(encoding="utf-8"),
        ),
        encoding="utf-8",
    )

    pyproject = root / "pyproject.toml"
    pyproject.write_text(
        re.sub(
            r'(?m)^version = "[^"]*"',
            f'version = "{version}"',
            pyproject.read_text(encoding="utf-8"),
        ),
        encoding="utf-8",
    )

    print(f"stamped version {version}")


if __name__ == "__main__":
    main()
