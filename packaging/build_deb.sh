#!/usr/bin/env bash
# Build a .deb locally — same artifact CI produces, without waiting on CI.
#
# CI uses fpm, which wants Ruby, ruby-dev and a gem install behind sudo. dpkg-deb
# ships with any Debian-family system and needs none of that, so this script
# assembles the package tree itself. The result installs the same single frozen
# binary at the same path.
#
#   ./packaging/build_deb.sh            # version from src/markstar/__init__.py
#   ./packaging/build_deb.sh 0.4.1      # explicit version
#
# Output: dist/markstarstudio_<version>_<arch>.deb

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

# Version, in the order CI would see it: an explicit argument, else the tag on
# HEAD (what stamp_version.py uses in CI), else the version in the source. The
# source value is the least trustworthy — it is only correct between releases if
# someone bumped it by hand, which is the drift stamp_version.py exists to stop.
VERSION="${1:-}"
if [ -z "$VERSION" ]; then
  VERSION="$(git describe --tags --exact-match 2>/dev/null | sed 's/^v//')"
fi
if [ -z "$VERSION" ]; then
  VERSION="$(sed -n 's/^__version__ = "\(.*\)"/\1/p' src/markstar/__init__.py)"
  echo "note: HEAD is not tagged; using source version $VERSION" >&2
fi
[ -n "$VERSION" ] || { echo "could not determine version" >&2; exit 1; }
ARCH="$(dpkg --print-architecture)"
PKG="markstarstudio"

command -v dpkg-deb >/dev/null || { echo "dpkg-deb not found" >&2; exit 1; }
python -c "import PyInstaller" 2>/dev/null || {
  echo "PyInstaller missing — pip install '.[dev]'" >&2; exit 1; }

# Stamp the version into the source before freezing, exactly as CI does, so the
# binary's --version matches the package version. CI runs on a throwaway
# checkout; this is someone's working tree, so the originals are restored on the
# way out no matter how the build ends.
STAMPED_FILES=(src/markstar/__init__.py pyproject.toml)
BACKUP="$(mktemp -d)"
restore() {
  for f in "${STAMPED_FILES[@]}"; do
    [ -f "$BACKUP/$(basename "$f")" ] && cp "$BACKUP/$(basename "$f")" "$f"
  done
  rm -rf "$BACKUP"
}
trap restore EXIT
for f in "${STAMPED_FILES[@]}"; do cp "$f" "$BACKUP/$(basename "$f")"; done
GITHUB_REF_NAME="v$VERSION" python packaging/stamp_version.py

echo "==> freezing binary (this takes a minute)"
rm -rf build dist/markstar pkgroot
# Kept in step with PYINSTALLER_ARGS in .github/workflows/release.yml.
python -m PyInstaller --onefile --name markstar \
  --collect-all textual --collect-all rich --collect-all spellchecker \
  --collect-all openai --collect-all pydantic --collect-all pydantic_core \
  --log-level WARN \
  packaging/entry.py

echo "==> assembling package tree"
install -D -m 0755 dist/markstar "pkgroot/usr/bin/markstar"
mkdir -p pkgroot/DEBIAN
# Installed-Size is in KiB and is what apt shows before installing.
SIZE="$(du -ks pkgroot/usr | cut -f1)"
cat > pkgroot/DEBIAN/control <<CONTROL
Package: $PKG
Version: $VERSION
Section: editors
Priority: optional
Architecture: $ARCH
Maintainer: Ryan Baron de Ropp <daudzegir@gmail.com>
Homepage: https://markstar.studio
Installed-Size: $SIZE
Description: MarkStar Studio - a Markdown-native terminal word processor
 A modern homage to WordStar with Microsoft Works-style keys. Self-contained:
 the interpreter and every dependency are frozen into the binary, so no Python
 installation is required.
CONTROL

OUT="dist/${PKG}_${VERSION}_${ARCH}.deb"
dpkg-deb --build --root-owner-group pkgroot "$OUT" >/dev/null
rm -rf pkgroot

echo "==> verifying"
dpkg-deb -I "$OUT" | sed -n '2,8p'
./dist/markstar --version
echo
echo "built: $OUT  ($(du -h "$OUT" | cut -f1))"
echo "install with:  sudo dpkg -i $ROOT/$OUT"
