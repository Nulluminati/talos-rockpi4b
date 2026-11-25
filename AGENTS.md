# talos-rockpi4b

Builds Talos Linux images for the Radxa ROCK Pi 4B/4B+ with the eMMC limited to HS200. The image is the official `siderolabs/sbc-rockchip` `rockpi4` overlay with two files replaced: a U-Boot built from a patched `rk3399-rock-pi-4.dtsi`, and a patched external `rk3399-rock-pi-4b.dtb`. The Python package holds `check-hs200`, which proves that a built artifact has no HS400 property. The owner runs these images on ROCK Pi control-plane and worker nodes.

## Layout

- `src/talos_rockpi4b/check.py`: FDT parser and the HS200 check. Entry point `check-hs200`.
- `tests/fdtbuild.py`: builds small FDT blobs for the tests. `tests/test_check.py`: the checker tests.
- `docs/releasing.md`: tag scheme and release steps.
- `.github/workflows/ci.yml`: lint, format, tests and gitleaks.

## Commands

```bash
uv run pytest
uv run ruff check .
uv run ruff format --check .
uv lock --check
uv run check-hs200 FILE...
```

## Releases

Tags are `v<talos>-<overlay>-r<n>`, not semver. See `docs/releasing.md`.

## Gotchas

- The boot chain has two device-tree sources. U-Boot embeds its own trees and passes one to Linux through EFI. Patching only the external DTB still boots in HS400. Check both files, and the copies inside the installer.
- `u-boot-rockchip.bin` from `sbc-rockchip:v0.3.0` holds 4 FDT blobs. Only 2 have the eMMC node (`/mmc@fe330000`). A check that requires every blob to have the node is wrong.
- The upstream external DTB has HS400 properties and no `mmc-hs200-1_8v`. The patch must add HS200, not only delete HS400.
- Talos Imager pulls `--overlay-image` from a registry at build time. Publish the derived overlay for both `linux/amd64` and `linux/arm64`. An amd64-only overlay makes Imager silently skip the overlay files for `--arch arm64`.
- Do not push from a BuildKit `docker-container` builder for the overlay. It produced a manifest that Imager could not extract.
- All cluster nodes must run the same Talos version. A Talos upgrade waits for a tested image from this repo.
