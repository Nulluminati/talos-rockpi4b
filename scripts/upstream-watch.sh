#!/usr/bin/env bash
# Run check-hs200 on the unpatched upstream files. This step never fails the
# build: a failing check is the normal result. When the check passes, upstream
# has dropped HS400 and this repository may no longer be needed.
#
# Usage: scripts/upstream-watch.sh UPSTREAM_DIR
set -euo pipefail

upstream=${1:?usage: upstream-watch.sh UPSTREAM_DIR}
root=$(cd "$(dirname "$0")/.." && pwd)
files=("$upstream/u-boot-rockchip.bin" "$upstream/rk3399-rock-pi-4b.dtb")
for file in "${files[@]}"; do
  test -s "$file"
done

if uv run --project "$root" --locked check-hs200 "${files[@]}"; then
  echo "::warning title=Upstream dropped HS400::The official sbc-rockchip rockpi4 files pass check-hs200. The official image may now be enough."
else
  echo "Upstream still has HS400, as expected. This repository is still needed."
fi
