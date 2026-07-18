#!/usr/bin/env bash
# Build QuBi for macOS (arm64/x86_64) against a local Sylvan install.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PREFIX="${PREFIX:-$HOME/.local}"
OUT="$ROOT/solvers/qubi"
mkdir -p "$OUT" "$PREFIX"

if [[ ! -f "$PREFIX/lib/libsylvan.a" ]]; then
  echo "Building Sylvan into $PREFIX ..."
  rm -rf /tmp/sylvan-build
  git clone --depth 1 https://github.com/trolando/sylvan.git /tmp/sylvan-build
  cmake -S /tmp/sylvan-build -B /tmp/sylvan-build/build \
    -DCMAKE_BUILD_TYPE=Release \
    -DCMAKE_INSTALL_PREFIX="$PREFIX" \
    -DBUILD_SHARED_LIBS=OFF
  cmake --build /tmp/sylvan-build/build -j"$(sysctl -n hw.ncpu)"
  cmake --install /tmp/sylvan-build/build
fi

rm -rf /tmp/qubi-build
git clone --depth 1 https://github.com/jacopol/qubi.git /tmp/qubi-build
cd /tmp/qubi-build

# Newer Sylvan/Lace: TASK()-based GC hooks no longer match; disable them.
python3 - <<'PY'
from pathlib import Path
p = Path("bdd_sylvan.cpp")
t = p.read_text()
t = t.replace(
    """    if (VERBOSE>=2) {
        sylvan_gc_hook_pregc(TASK(gc_start)); // message for garbage collection
        sylvan_gc_hook_postgc(TASK(gc_done)); // message for garbage collection
    }
""",
    """    // GC hooks disabled for newer Sylvan/Lace API compatibility.
    (void)0;
""",
)
p.write_text(t)
print("patched bdd_sylvan.cpp")
PY

CXX="${CXX:-clang++}"
$CXX -O2 -std=c++17 *.cpp -o qubi \
  -I"$PREFIX/include" -L"$PREFIX/lib" \
  -lsylvan -llace -lpthread \
  -I/opt/homebrew/include -L/opt/homebrew/lib \
  -I/usr/local/include -L/usr/local/lib \
  -lgmp

cp -f qubi "$OUT/qubi"
chmod +x "$OUT/qubi"
echo "Installed $OUT/qubi"
file "$OUT/qubi"
"$OUT/qubi" -v=0 Test/qbf3.qcir
