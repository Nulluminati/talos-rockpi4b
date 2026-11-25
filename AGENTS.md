# talos-rockpi4b

Builds Talos Linux images for the Radxa ROCK Pi 4B/4B+ with the eMMC limited to HS200. The image is the official `siderolabs/sbc-rockchip` `rockpi4` overlay with two files replaced: a U-Boot built from a patched `rk3399-rock-pi-4.dtsi`, and a patched external `rk3399-rock-pi-4b.dtb`. The Python package holds `check-hs200`, which proves that a built artifact has no HS400 property, and the build tools `pins`, `patch-pkg` and `check-dtb-patch`. The owner runs these images on ROCK Pi control-plane and worker nodes.

## Layout

- `src/talos_rockpi4b/check.py`: FDT parser and the HS200 check. Entry point `check-hs200`.
- `src/talos_rockpi4b/pins.py`: `pins sync | check | tag`. Derives the overlay and U-Boot build pins from the Talos pin through Image Factory and the GitHub API.
- `src/talos_rockpi4b/patch_pkg.py`: `patch-pkg`, adds the HS400 removal step to the upstream `rockpi4` U-Boot `pkg.yaml`.
- `src/talos_rockpi4b/dtb_diff.py`: `check-dtb-patch`, proves that the patched DTB differs from upstream only in the 3 eMMC properties.
- `pins/talos.Dockerfile`: the Talos pin, the only pin Dependabot updates. `pins/sbc-rockchip.json` and `overlay/Dockerfile` are written by `pins sync`.
- `scripts/`: the build steps, in order: `build-uboot.sh`, `patch-dtb.sh`, `build-overlay.sh`, `build-images.sh`, `verify-images.sh`, `upstream-watch.sh`.
- `tests/fdtbuild.py`: builds small FDT blobs for the tests. `tests/data/`: recorded Image Factory and Makefile responses for the `pins` tests.
- `docs/releasing.md`: tag scheme and release steps.
- `.github/workflows/ci.yml`: lint, format, tests, `pins check`, gitleaks, and the `Build image` job from `build.yml`. `release.yml`: builds, pushes, signs and releases on a `v*` tag.

## Commands

```bash
uv run pytest
uv run ruff check .
uv run ruff format --check .
uv lock --check
uv run check-hs200 FILE...
uv run pins check   # after a Talos bump: uv run pins sync
```

## Releases

Tags are `v<talos>-<overlay>-r<n>`, not semver. See `docs/releasing.md`.

## Gotchas

- The boot chain has two device-tree sources. U-Boot embeds its own trees and passes one to Linux through EFI. Patching only the external DTB still boots in HS400. Check both files, and the copies inside the installer.
- `u-boot-rockchip.bin` from `sbc-rockchip:v0.3.0` holds 4 FDT blobs. Only 2 have the eMMC node (`/mmc@fe330000`). A check that requires every blob to have the node is wrong.
- The upstream external DTB has HS400 properties and no `mmc-hs200-1_8v`. The patch must add HS200, not only delete HS400.
- Talos Imager pulls `--overlay-image` from a registry at build time. Publish the derived overlay for both `linux/amd64` and `linux/arm64`. An amd64-only overlay makes Imager silently skip the overlay files for `--arch arm64`.
- Do not push from a BuildKit `docker-container` builder for the overlay. It produced a manifest that Imager could not extract. The U-Boot build is the exception the other way: the bldr frontend needs `mergeop`, which the default `docker` driver rejects without the containerd image store, so `build-uboot.sh` uses its own `docker-container` builder for local output only.
- Never edit `overlay/Dockerfile` or `pins/sbc-rockchip.json` by hand. The overlay must be the one Image Factory pairs with the Talos pin. Change `pins/talos.Dockerfile`, then run `uv run pins sync`.
- The `sbc-rockchip` tags are annotated. Pin the commit the tag points to, not the tag object.
- `ftp.denx.de` is the only upstream host for the U-Boot tarball and can be down for hours. When it does not answer, `build-uboot.sh` runs `patch-pkg --fedora-mirror`, which takes the same file from the Fedora package cache. bldr still checks the upstream SHA-256 and SHA-512 pins.
- The build runs on `ubuntu-24.04-arm` so U-Boot builds natively. The dev machine is x86_64 without QEMU and cannot reach `ftp.denx.de`: build U-Boot in CI. The other scripts run locally.
- Imager's built-in `metal` profile makes a systemd-boot image with no external DTB. Use the overlay's `profiles/rockpi4.yaml` (GRUB) for the raw image, as Image Factory does. `--output-kind` does not override a profile read from stdin.
- The raw image is about 2.3 GB uncompressed. `/tmp` on the dev machine is a small tmpfs: put build outputs in `_out/`.
- All cluster nodes must run the same Talos version. A Talos upgrade waits for a tested image from this repo.
