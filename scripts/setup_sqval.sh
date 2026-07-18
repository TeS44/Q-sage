#!/usr/bin/env bash
# Clone SQval next to the qsage package for certificate validation (#9).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DEST="$ROOT/third_party/SQval"
mkdir -p "$ROOT/third_party"
if [[ -d "$DEST/.git" ]]; then
  echo "SQval already present at $DEST"
  git -C "$DEST" pull --ff-only || true
else
  git clone --depth 1 https://github.com/irfansha/SQval.git "$DEST"
fi
python3 -m pip install -q -r "$DEST/requirements.txt" || python3 -m pip install -q python-sat
echo "OK: $DEST"
echo "Try: qsage cert demo-equivalence"
