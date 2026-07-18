#!/usr/bin/env bash
# Build DepQBF + QRPcert for AIGER strategy certificates.
#
# Sources (official / GPLv3):
#   DepQBF 6.03  https://github.com/lonsing/depqbf
#                https://lonsing.github.io/depqbf/
#   QRPcert 1.0.1 https://fmv.jku.at/qrpcert/  (qrpcert-1.0.1.tar.gz)
#   PicoSAT 960  https://fmv.jku.at/picosat/
#   Nenofex 1.1  https://github.com/lonsing/nenofex
#   QBFcert pkg  https://fmv.jku.at/qbfcert/   (optional Linux ELF fallback)
#
# Installs:
#   solvers/depqbf_cert/depqbf
#   solvers/depqbf_cert/qrpcert
#
# Usage matches legacy + qsage:
#   depqbf --trace --dep-man=simple --no-lazy-qpup inst.qdimacs > trace.qrp
#   qrpcert --aiger-ascii --simplify trace.qrp > cert.aag
#
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SRC="$ROOT/third_party/depqbf_cert_src"
OUT="$ROOT/solvers/depqbf_cert"
mkdir -p "$SRC" "$OUT"

have() { command -v "$1" >/dev/null 2>&1; }

download() {
  local url="$1" dest="$2"
  if [[ -f "$dest" ]]; then
    return 0
  fi
  echo "Downloading $url"
  if have curl; then
    curl -fL --retry 3 -o "$dest" "$url"
  elif have wget; then
    wget -O "$dest" "$url"
  else
    echo "need curl or wget" >&2
    exit 1
  fi
}

# ---------------------------------------------------------------------------
# DepQBF from GitHub (source — builds on macOS arm64 / Linux)
# ---------------------------------------------------------------------------
build_depqbf() {
  local d="$SRC/depqbf"
  if [[ ! -d "$d/.git" ]]; then
    echo "Cloning DepQBF (lonsing/depqbf)…"
    git clone --depth 1 https://github.com/lonsing/depqbf.git "$d"
  else
    echo "DepQBF sources present at $d"
    git -C "$d" pull --ff-only || true
  fi

  # compile.sh uses wget; fetch deps with curl if needed
  if [[ ! -d "$d/picosat" ]]; then
    download "https://fmv.jku.at/picosat/picosat-960.tar.gz" "$SRC/picosat-960.tar.gz"
    tar -xzf "$SRC/picosat-960.tar.gz" -C "$d"
    mv "$d/picosat-960" "$d/picosat"
  fi
  (
    cd "$d/picosat"
    if [[ ! -f picosat.o && ! -f libpicosat.a ]]; then
      ./configure
      make
    fi
  )

  if [[ ! -d "$d/nenofex" ]]; then
    download "https://github.com/lonsing/nenofex/archive/refs/tags/version-1.1.tar.gz" \
      "$SRC/nenofex-1.1.tar.gz"
    tar -xzf "$SRC/nenofex-1.1.tar.gz" -C "$d"
    mv "$d/nenofex-version-1.1" "$d/nenofex"
  fi
  (
    cd "$d/nenofex"
    if [[ ! -f libnenofex.a && ! -f nenofex ]]; then
      make || make -j1
    fi
  )

  (
    cd "$d"
    make clean >/dev/null 2>&1 || true
    make
  )

  if [[ ! -x "$d/depqbf" ]]; then
    echo "DepQBF binary missing after build" >&2
    exit 1
  fi
  cp -f "$d/depqbf" "$OUT/depqbf"
  chmod +x "$OUT/depqbf"
  echo "OK: $OUT/depqbf"
  "$OUT/depqbf" --version 2>&1 | head -3 || "$OUT/depqbf" -h 2>&1 | head -5 || true
}

# ---------------------------------------------------------------------------
# QRPcert 1.0.1 from JKU (source; small macOS portability fix)
# ---------------------------------------------------------------------------
build_qrpcert() {
  local d="$SRC/qrpcert-1.0.1"
  if [[ ! -d "$d" ]]; then
    download "https://fmv.jku.at/qrpcert/qrpcert-1.0.1.tar.gz" "$SRC/qrpcert-1.0.1.tar.gz"
    mkdir -p "$d"
    tar -xzf "$SRC/qrpcert-1.0.1.tar.gz" -C "$d" --strip-components=0
    # tarball may unpack flat into cwd of extract; handle both layouts
    if [[ ! -f "$d/qrpcert.c" ]]; then
      # files landed in d/ subdir or current extract root
      if [[ -f "$SRC/qrpcert-1.0.1/qrpcert.c" ]]; then
        :
      else
        # extract to temp flat
        rm -rf "$d"
        mkdir -p "$d"
        tar -xzf "$SRC/qrpcert-1.0.1.tar.gz" -C "$d"
        if [[ ! -f "$d/qrpcert.c" ]]; then
          # nested dir
          local sub
          sub="$(find "$d" -name qrpcert.c | head -1)"
          if [[ -n "$sub" ]]; then
            d="$(dirname "$sub")"
          fi
        fi
      fi
    fi
  fi

  # locate sources
  local srcdir="$d"
  if [[ ! -f "$srcdir/qrpcert.c" ]]; then
    srcdir="$(dirname "$(find "$SRC" -name qrpcert.c | head -1)")"
  fi
  if [[ ! -f "$srcdir/qrpcert.c" ]]; then
    echo "QRPcert sources not found under $SRC" >&2
    exit 1
  fi

  # macOS/clang: <sys/unistd.h> does not declare close/unlink under C99.
  # Official QRPcert 1.0.1 uses sys/unistd.h; inject <unistd.h> next to it.
  python3 - "$srcdir" <<'PY'
import pathlib, sys
root = pathlib.Path(sys.argv[1])
for name in ("simpleaig.c", "qrpcert.h", "qrpcert.c"):
    path = root / name
    if not path.is_file():
        continue
    text = path.read_text(encoding="utf-8", errors="replace")
    if "#include <unistd.h>" in text:
        continue
    if "#include <sys/unistd.h>" in text:
        text = text.replace(
            "#include <sys/unistd.h>",
            "#include <sys/unistd.h>\n#include <unistd.h>",
        )
    elif name == "qrpcert.h":
        text = text.replace(
            "#ifndef INCLUDE_QRPCERT_H",
            "#ifndef INCLUDE_QRPCERT_H\n\n#include <unistd.h>",
            1,
        )
    else:
        continue
    path.write_text(text, encoding="utf-8")
    print(f"patched {path.name} for unistd.h")
PY

  (
    cd "$srcdir"
    make clean >/dev/null 2>&1 || true
    # Allow bit-field warnings on modern clang; treat only errors as fatal
    make CFLAGSOPT="-O3 -W -Wall -Wextra -Wunused -DNDEBUG -Wno-error"
  )
  if [[ ! -x "$srcdir/qrpcert" ]]; then
    echo "qrpcert binary missing after build" >&2
    exit 1
  fi
  cp -f "$srcdir/qrpcert" "$OUT/qrpcert"
  chmod +x "$OUT/qrpcert"
  echo "OK: $OUT/qrpcert"
  "$OUT/qrpcert" -h 2>&1 | head -8 || true
}

# ---------------------------------------------------------------------------
# Optional: install Linux ELF from QBFcert 1.0 if native build fails
# ---------------------------------------------------------------------------
fallback_linux_binaries() {
  echo "Attempting QBFcert 1.0 prebuilt Linux binaries (ELF only)…"
  download "https://fmv.jku.at/qbfcert/qbfcert-1.0.tar.gz" "$SRC/qbfcert-1.0.tar.gz"
  local unpack="$SRC/qbfcert-unpack"
  rm -rf "$unpack"
  mkdir -p "$unpack"
  tar -xzf "$SRC/qbfcert-1.0.tar.gz" -C "$unpack"
  cp -f "$unpack/qbfcert/depqbf/depqbf" "$OUT/depqbf"
  cp -f "$unpack/qbfcert/qrpcert/qrpcert" "$OUT/qrpcert"
  chmod +x "$OUT/depqbf" "$OUT/qrpcert"
  echo "Installed Linux ELFs to $OUT (use Docker/WSL on non-Linux hosts)"
}

# ---------------------------------------------------------------------------
main() {
  local mode="${1:-build}"
  case "$mode" in
    build)
      if ! build_depqbf; then
        echo "DepQBF native build failed" >&2
        if [[ "$(uname -s)" == "Linux" ]] || [[ "${FORCE_LINUX_BINS:-}" == "1" ]]; then
          fallback_linux_binaries
        else
          exit 1
        fi
      fi
      if ! build_qrpcert; then
        echo "QRPcert native build failed" >&2
        if [[ "$(uname -s)" == "Linux" ]] || [[ "${FORCE_LINUX_BINS:-}" == "1" ]]; then
          fallback_linux_binaries
        else
          exit 1
        fi
      fi
      ;;
    binaries|linux-bins)
      fallback_linux_binaries
      ;;
    *)
      echo "Usage: $0 [build|linux-bins]" >&2
      exit 2
      ;;
  esac

  cat <<EOF

Installed:
  $OUT/depqbf
  $OUT/qrpcert

Generate AIGER certificate (trace flags required for DepQBF 6.x):
  $OUT/depqbf --trace --dep-man=simple --no-lazy-qpup formula.qdimacs > trace.qrp
  $OUT/qrpcert --aiger-ascii --simplify trace.qrp > certificate.aag

Or: qsage cert generate --backend depqbf --qdimacs formula.qdimacs --out cert.aag
EOF
}

main "$@"
