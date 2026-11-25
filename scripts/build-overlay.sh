#!/usr/bin/env bash
# Build the derived overlay for linux/amd64 and linux/arm64, push both and join
# them into one manifest list.
#
# Usage: scripts/build-overlay.sh FILES_DIR IMAGE TAG
# FILES_DIR holds u-boot-rockchip.bin and rk3399-rock-pi-4b.dtb. Prints
# IMAGE@sha256:<digest> of the manifest list on stdout.
#
# Use the default docker builder. An overlay pushed from a BuildKit
# docker-container builder gave a manifest that Talos Imager could not extract.
set -euo pipefail

files=${1:?usage: build-overlay.sh FILES_DIR IMAGE TAG}
image=${2:?usage: build-overlay.sh FILES_DIR IMAGE TAG}
tag=${3:?usage: build-overlay.sh FILES_DIR IMAGE TAG}
root=$(cd "$(dirname "$0")/.." && pwd)

context=$(mktemp -d)
trap 'rm -rf "$context"' EXIT
cp "$files/u-boot-rockchip.bin" "$files/rk3399-rock-pi-4b.dtb" "$context/"

refs=()
for arch in amd64 arm64; do
  ref="$image:$tag-$arch"
  docker build --platform="linux/$arch" --provenance=false --sbom=false \
    --file="$root/overlay/Dockerfile" --tag="$ref" "$context" >&2
  docker push --quiet "$ref" >&2
  refs+=("$ref")
done

docker buildx imagetools create --tag="$image:$tag" "${refs[@]}" >&2

platforms=$(docker buildx imagetools inspect --raw "$image:$tag" |
  jq -r '.manifests[] | select(.platform.os != "unknown") | "\(.platform.os)/\(.platform.architecture)"' |
  sort | paste -sd, -)
if [[ "$platforms" != "linux/amd64,linux/arm64" ]]; then
  echo "FAIL $image:$tag lists platforms '$platforms', expected linux/amd64,linux/arm64" >&2
  exit 1
fi

digest=$(docker buildx imagetools inspect "$image:$tag" --format '{{.Manifest.Digest}}')
echo "OK   $image:$tag lists $platforms, digest $digest" >&2
echo "$image@$digest"
