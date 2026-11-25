#!/usr/bin/env bash
# Copy the upstream files out of the pinned overlay and patch the external DTB.
#
# Usage: scripts/patch-dtb.sh OUT_DIR
# Writes OUT_DIR/rk3399-rock-pi-4b.dtb (patched) and the unpatched upstream
# u-boot-rockchip.bin and rk3399-rock-pi-4b.dtb to OUT_DIR/upstream/.
# Needs docker, fdtput (device-tree-compiler) and uv.
set -euo pipefail

out=${1:?usage: patch-dtb.sh OUT_DIR}
root=$(cd "$(dirname "$0")/.." && pwd)
base=$(sed -n 's/^FROM //p' "$root/overlay/Dockerfile")
dtb=rk3399-rock-pi-4b.dtb
node=/mmc@fe330000

mkdir -p "$out/upstream"
# The overlay holds the same arm64 files in every platform variant.
container=$(docker create "$base" /none)
trap 'docker rm "$container" >/dev/null' EXIT
docker cp "$container:/artifacts/arm64/dtb/rockchip/$dtb" "$out/upstream/$dtb"
docker cp "$container:/artifacts/arm64/u-boot/rockpi4/u-boot-rockchip.bin" "$out/upstream/u-boot-rockchip.bin"

cp "$out/upstream/$dtb" "$out/$dtb"
fdtput --delete "$out/$dtb" "$node" mmc-hs400-1_8v mmc-hs400-enhanced-strobe
fdtput "$out/$dtb" "$node" mmc-hs200-1_8v

uv run --project "$root" --locked check-hs200 "$out/$dtb"
uv run --project "$root" --locked check-dtb-patch "$out/upstream/$dtb" "$out/$dtb"
