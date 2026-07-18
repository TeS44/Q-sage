#!/usr/bin/env bash
# Build QuBi (linux/amd64) inside Docker and install to solvers/qubi/qubi
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
OUT="$ROOT/solvers/qubi"
mkdir -p "$OUT"

docker run --rm --platform linux/amd64 \
  -v "$OUT:/out" \
  ubuntu:22.04 \
  bash -c '
set -e
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y -qq build-essential git cmake libgmp-dev ca-certificates >/dev/null
cd /tmp
git clone --depth 1 https://github.com/trolando/sylvan.git
cd sylvan
mkdir build && cd build
cmake .. -DCMAKE_BUILD_TYPE=Release -DBUILD_SHARED_LIBS=OFF
make -j"$(nproc)"
make install
ldconfig || true
cd /tmp
git clone --depth 1 https://github.com/jacopol/qubi.git
cd qubi
# find headers/libs
g++ -O2 -std=c++17 *.cpp -o qubi \
  -I/usr/local/include -L/usr/local/lib \
  -lsylvan -lpthread -llace -lgmp 2>/tmp/qubi_build.err || {
    cat /tmp/qubi_build.err
    # try lace name variants
    g++ -O2 -std=c++17 *.cpp -o qubi \
      -I/usr/local/include -L/usr/local/lib \
      -lsylvan -lpthread -lgmp || { cat /tmp/qubi_build.err; exit 1; }
  }
cp qubi /out/qubi
chmod +x /out/qubi
echo built_ok
'
echo "Installed: $OUT/qubi"
file "$OUT/qubi"
