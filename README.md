# talos-rockpi4b

Talos Linux images for the Radxa ROCK Pi 4B and 4B+ that run the onboard eMMC in HS200 instead of HS400.

> **Status:** not built yet. The device-tree check (`check-hs200`) works and is tested. The build and release workflows come next.

## Why

The official Talos overlay for this board, [`siderolabs/sbc-rockchip`](https://github.com/siderolabs/sbc-rockchip) `rockpi4`, uses the stock U-Boot and the mainline device tree. Both advertise `mmc-hs400-1_8v` and `mmc-hs400-enhanced-strobe`, so the kernel picks HS400. On the boards tested here, HS400 gave `mmc0: running CQE recovery` warnings and read I/O errors within the first boot. In HS200 the same boards passed a full eMMC read scan, a synchronous-write test and a 44-hour soak with no storage errors.

The fix has to go in two places. U-Boot carries its own copies of the device tree and hands one of them to Linux through the EFI boot path. Patching only the external DTB still boots in HS400. This repo patches both:

| File | Change |
|---|---|
| `u-boot-rockchip.bin` (embedded device trees) | HS400 removed from `rk3399-rock-pi-4.dtsi` before U-Boot is built |
| `rk3399-rock-pi-4b.dtb` (external Linux DTB) | `mmc-hs400-1_8v` and `mmc-hs400-enhanced-strobe` replaced by `mmc-hs200-1_8v` |

Nothing else changes. The image is the official overlay with these two files replaced.

This is an unofficial image with no support from Sidero Labs. HS200 is slower than HS400: about 370 synchronous 4 KiB write IOPS on the tested eMMC, against roughly three times that in HS400.

## Usage

Planned. Each release will publish:

- an installer image on GHCR, for `talosctl upgrade --image ghcr.io/nulluminati/talos-rockpi4b-installer:<tag>@sha256:<digest>`
- `metal-arm64.raw.xz` as a release asset, for the first flash to microSD or eMMC
- SHA-256 checksums, the build log and a cosign signature

Pin the installer by digest, not by tag.

## Release tags

A tag names the upstream versions inside it: `v<talos>-<overlay>-r<n>`, for example `v1.13.8-v0.3.0-r1`. `r<n>` counts rebuilds of the same pair. See [docs/releasing.md](docs/releasing.md).

## Keeping up with upstream

1. Dependabot opens a pull request when Talos (`imager`, `installer-base`) or `sbc-rockchip` publishes a new version.
2. CI builds U-Boot, the derived overlay, the installer and the raw image in the pull request. Nothing is published from a pull request.
3. CI runs `check-hs200` on the built U-Boot binary, the external DTB and the copies inside the installer. The build fails if any device tree with the eMMC node lacks `mmc-hs200-1_8v` or if any node has an HS400 property. If a new U-Boot release moves the device-tree source and the patch stops applying, the build fails instead of shipping HS400.
4. CI also runs the check on the unpatched upstream files. When upstream drops HS400 on its own, the job reports it, and this repo can be retired in favour of the official image.
5. Merging to `main` and pushing a tag builds, signs and publishes the release.
6. Test on hardware before the image reaches a control plane. Upgrade one worker first.

### Hardware test

CI cannot boot a board. Pick the test from what changed in the Dependabot pull request:

| What changed | Example | Test on one worker |
|---|---|---|
| Talos patch release, same overlay and U-Boot | v1.13.8 to v1.13.9 | Short test |
| New `sbc-rockchip` release or new U-Boot version | v0.3.0 to v0.3.1 | Short test, then leave the worker on the new image overnight |
| Talos minor release (new kernel) | v1.13 to v1.14 | Short test, then leave the worker on the new image overnight |

The short test takes about 15 minutes:

1. `/sys/kernel/debug/mmc0/ios` shows HS200.
2. `dmesg` has no `CQE recovery` or `I/O error` lines.
3. A full read of the eMMC (31 GB) completes with no errors.
4. A 5-minute synchronous-write test completes with no errors.
5. The node is Ready and its pods run.

After the overnight run, check `dmesg` again. Then upgrade the control planes one at a time and wait for etcd to report healthy before the next one.

## Development

```bash
uv sync
uv run pytest
uv run ruff check .
uv run ruff format --check .
uv run check-hs200 path/to/u-boot-rockchip.bin path/to/rk3399-rock-pi-4b.dtb
```

`check-hs200` reads any file, finds every flattened device tree in it and exits 1 when a check fails. Run against the official `sbc-rockchip:v0.3.0` files it reports 4 device trees in U-Boot, 2 of them with the eMMC node, and HS400 in all of them.

## License

MIT. See [LICENSE](LICENSE).
