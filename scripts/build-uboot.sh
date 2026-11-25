#!/usr/bin/env bash
# Build the rockpi4 U-Boot from the pinned sbc-rockchip tag, with HS400 removed
# from the embedded device trees.
#
# Usage: scripts/build-uboot.sh OUT_DIR
# Writes OUT_DIR/u-boot-rockchip.bin. Needs an arm64 host, git, jq, curl, docker and uv.
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

# ftp.denx.de, the only upstream host for the U-Boot release tarball, is
# sometimes unreachable for a long time. The Fedora package cache keeps the
# same file, and bldr checks it against the SHA-256 and SHA-512 pins.
mirror=()
if ! curl -sSf -o /dev/null --max-time 30 https://ftp.denx.de/pub/u-boot/; then
  echo "ftp.denx.de does not answer. The U-Boot source comes from the Fedora package cache." >&2
  mirror=(--fedora-mirror)
fi
uv run --project "$root" --locked patch-pkg "${mirror[@]}" "$src/artifacts/rockpi4/u-boot/pkg.yaml"

# The bldr frontend needs BuildKit features (mergeop) that the default docker
# driver has only with the containerd image store. This builder writes local
# output and pushes nothing. The overlay build keeps the default builder.
builder=talos-rockpi4b-uboot
docker buildx inspect "$builder" >/dev/null 2>&1 || docker buildx create --name="$builder" --driver=docker-container >/dev/null

docker buildx build \
  --builder="$builder" \
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
