#!/usr/bin/env bash
# Build the rockpi4 U-Boot from the pinned sbc-rockchip tag, with HS400 removed
# from the embedded device trees.
#
# Usage: scripts/build-uboot.sh OUT_DIR
# Writes OUT_DIR/u-boot-rockchip.bin. Needs an arm64 host, git, jq, docker and uv.
set -euo pipefail

out=${1:?usage: build-uboot.sh OUT_DIR}
root=$(cd "$(dirname "$0")/.." && pwd)
pins="$root/pins/sbc-rockchip.json"
pin() { jq -er ".$1" "$pins"; }

tag=$(pin tag)
commit=$(pin commit)
epoch=$(pin source_date_epoch)

work=$(mktemp -d)
trap 'rm -rf "$work"' EXIT
src="$work/sbc-rockchip"

# A blobless clone keeps the history, which the epoch check below needs.
git clone --quiet --filter=blob:none --branch "$tag" https://github.com/siderolabs/sbc-rockchip.git "$src"
head=$(git -C "$src" rev-parse HEAD)
if [[ "$head" != "$commit" ]]; then
  echo "FAIL sbc-rockchip $tag is $head, pins/sbc-rockchip.json says $commit" >&2
  exit 1
fi
root_commit=$(git -C "$src" rev-list --max-parents=0 HEAD)
root_epoch=$(git -C "$src" log -1 --pretty=%ct "$root_commit")
if [[ "$root_epoch" != "$epoch" ]]; then
  echo "FAIL root commit time is $root_epoch, pins/sbc-rockchip.json says $epoch" >&2
  exit 1
fi

uv run --project "$root" --locked patch-pkg "$src/artifacts/rockpi4/u-boot/pkg.yaml"

docker buildx build \
  --file="$src/Pkgfile" \
  --target=u-boot-rockpi4 \
  --platform=linux/arm64 \
  --provenance=false \
  --sbom=false \
  --progress=plain \
  --build-arg=SOURCE_DATE_EPOCH="$epoch" \
  --build-arg=PKGS_PREFIX="$(pin pkgs_prefix)" \
  --build-arg=PKGS="$(pin pkgs)" \
  --build-arg=TOOLS_PREFIX="$(pin tools_prefix)" \
  --build-arg=TOOLS="$(pin tools)" \
  --output=type=local,dest="$work/out" \
  "$src"

built=$(find "$work/out" -path '*/artifacts/arm64/u-boot/rockpi4/u-boot-rockchip.bin')
if [[ -z "$built" || $(wc -l <<<"$built") != 1 ]]; then
  echo "FAIL expected one u-boot-rockchip.bin in the build output, found: ${built:-none}" >&2
  exit 1
fi
mkdir -p "$out"
cp "$built" "$out/u-boot-rockchip.bin"
uv run --project "$root" --locked check-hs200 "$out/u-boot-rockchip.bin"
