#!/usr/bin/env bash
# Run Talos Imager with the derived overlay. Makes the raw disk image and the
# installer image.
#
# Usage: scripts/build-images.sh OVERLAY_REF OUT_DIR
# Writes OUT_DIR/metal-arm64.raw.xz and OUT_DIR/installer-arm64.tar.
#
# For the raw image, Imager gets the profile that the overlay ships for the
# board (profiles/rockpi4.yaml), the one Image Factory uses: GRUB, external DTB
# on the EFI partition, xz output. The built-in "metal" profile makes a
# systemd-boot image without the external DTB instead. The installer uses the
# built-in "installer" profile: --output-kind does not change a profile read
# from stdin.
set -euo pipefail

overlay=${1:?usage: build-images.sh OVERLAY_REF OUT_DIR}
out=${2:?usage: build-images.sh OVERLAY_REF OUT_DIR}
root=$(cd "$(dirname "$0")/.." && pwd)
imager=$(sed -n 's/^FROM //p' "$root/pins/talos.Dockerfile")

mkdir -p "$out"
work=$(mktemp -d)
container=""
cleanup() {
  [[ -z "$container" ]] || docker rm "$container" >/dev/null
  rm -rf "$work"
}
trap cleanup EXIT

container=$(docker create "$overlay" /none)
docker cp "$container:/profiles/rockpi4.yaml" "$work/rockpi4.yaml"
if grep -q '^overlay:' "$work/rockpi4.yaml"; then
  echo "FAIL the overlay profile already has an overlay section" >&2
  exit 1
fi
cat >>"$work/rockpi4.yaml" <<EOF
overlay:
  name: rockpi4
  image:
    imageRef: $overlay
EOF
echo "Imager profile:" >&2
cat "$work/rockpi4.yaml" >&2

insecure=()
if [[ "$overlay" == 127.0.0.1:* || "$overlay" == localhost:* ]]; then
  insecure=(--insecure)
fi

run_imager() {
  docker run --rm -i --privileged --network=host -v /dev:/dev -v "$(realpath "$out"):/out" "$imager" "$@"
}

run_imager - "${insecure[@]}" <"$work/rockpi4.yaml"
run_imager installer --arch=arm64 --overlay-name=rockpi4 --overlay-image="$overlay" "${insecure[@]}" </dev/null

for file in metal-arm64.raw.xz installer-arm64.tar; do
  test -s "$out/$file" || {
    echo "FAIL Imager did not write $out/$file" >&2
    exit 1
  }
done
