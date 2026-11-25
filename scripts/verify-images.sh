#!/usr/bin/env bash
# Prove that the Imager outputs carry the patched files.
#
# Usage: scripts/verify-images.sh FILES_DIR IMAGES_DIR
# FILES_DIR holds the patched u-boot-rockchip.bin and rk3399-rock-pi-4b.dtb.
# IMAGES_DIR holds metal-arm64.raw.xz and installer-arm64.tar.
#
# Extracts U-Boot and the DTB from the installer layers, and from the raw image
# (U-Boot at sector 64, the DTB on the EFI partition). Runs check-hs200 on each
# copy and compares its SHA-256 with FILES_DIR. Needs jq, sfdisk, mtools, xz
# and uv.
set -euo pipefail

files=${1:?usage: verify-images.sh FILES_DIR IMAGES_DIR}
images=${2:?usage: verify-images.sh FILES_DIR IMAGES_DIR}
root=$(cd "$(dirname "$0")/.." && pwd)
uboot=u-boot-rockchip.bin
dtb=rk3399-rock-pi-4b.dtb
# The rockpi4 overlay installer writes U-Boot at this byte offset.
uboot_offset=$((512 * 64))

# Large scratch files go next to the images, not in a small /tmp.
work="$images/verify"
rm -rf "$work"
mkdir -p "$work/installer" "$work/raw"
trap 'rm -rf "$work"' EXIT

failed=0
compare() {
  local copy=$1 expected=$2
  if ! uv run --project "$root" --locked check-hs200 "$copy"; then
    failed=1
  fi
  if cmp -s "$copy" "$expected"; then
    echo "OK   $copy: same SHA-256 as $expected ($(sha256sum <"$copy" | cut -d' ' -f1))"
  else
    echo "FAIL $copy: differs from $expected"
    failed=1
  fi
}

# Installer: a docker-archive tarball. One layer holds the overlay artifacts.
installer="$images/installer-arm64.tar"
members=("overlay/artifacts/arm64/u-boot/rockpi4/$uboot" "overlay/artifacts/arm64/dtb/rockchip/$dtb")
for layer in $(tar -xOf "$installer" manifest.json | jq -r '.[0].Layers[]'); do
  tar -xOf "$installer" "$layer" | tar -xz -C "$work/installer" "${members[@]}" 2>/dev/null || true
done
for member in "${members[@]}"; do
  if [[ ! -f "$work/installer/$member" ]]; then
    echo "FAIL $installer has no layer with $member"
    failed=1
  fi
done
[[ ! -f "$work/installer/${members[0]}" ]] || compare "$work/installer/${members[0]}" "$files/$uboot"
[[ ! -f "$work/installer/${members[1]}" ]] || compare "$work/installer/${members[1]}" "$files/$dtb"

# Raw image.
raw="$work/raw/metal-arm64.raw"
xz -dc "$images/metal-arm64.raw.xz" >"$raw"
size=$(stat -c %s "$files/$uboot")
dd if="$raw" of="$work/raw/$uboot" bs=512 skip=$((uboot_offset / 512)) count=$((size / 512)) status=none
if ((size % 512)); then
  echo "FAIL $files/$uboot is not a multiple of 512 bytes"
  failed=1
fi
compare "$work/raw/$uboot" "$files/$uboot"

efi_start=$(sfdisk --json "$raw" | jq -er '.partitiontable.partitions[] | select(.name == "EFI") | .start')
mcopy -n -i "$raw@@$((efi_start * 512))" "::/dtb/rockchip/$dtb" "$work/raw/$dtb"
compare "$work/raw/$dtb" "$files/$dtb"

if ((failed)); then
  echo "FAIL the images do not carry the patched files"
  exit 1
fi
echo "OK   installer and raw image carry the patched U-Boot and DTB"
