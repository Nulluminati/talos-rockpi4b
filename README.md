# talos-rockpi4b

Talos Linux images for the Radxa ROCK Pi 4B and 4B+ that run the onboard eMMC in HS200 instead of HS400.

> **Status:** the build and release workflows exist. The first release is `v1.14.7-v0.2.1-r1` (Talos v1.14.7, `sbc-rockchip` v0.2.1). Run the hardware test below before you put it on a control plane.

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

Each release publishes:

- an installer image, `ghcr.io/nulluminati/talos-rockpi4b-installer:<tag>`, for `talosctl upgrade`
- the derived overlay, `ghcr.io/nulluminati/talos-rockpi4b-overlay:<tag>`, for your own Imager builds
- `metal-arm64.raw.xz`, `SHA256SUMS` and `build.log` as release assets

The release notes give the digest of each image. Pin the installer by digest, not by tag. Both images carry a keyless cosign signature from the Release workflow.

### Verify

```bash
cosign verify ghcr.io/nulluminati/talos-rockpi4b-installer@sha256:<digest> \
  --certificate-oidc-issuer https://token.actions.githubusercontent.com \
  --certificate-identity https://github.com/nulluminati/talos-rockpi4b/.github/workflows/release.yml@refs/tags/<tag>
sha256sum -c SHA256SUMS
```

### Flash a new node

Write the raw image to a microSD card or the eMMC module. Replace `/dev/sdX` with the target disk; `dd` destroys its contents.

```bash
xz -dc metal-arm64.raw.xz | sudo dd of=/dev/sdX bs=4M conv=fsync status=progress
```

### Upgrade a node

```bash
talosctl upgrade --nodes <node> --image ghcr.io/nulluminati/talos-rockpi4b-installer:<tag>@sha256:<digest>
```

## Release tags

A tag names the upstream versions inside it: `v<talos>-<overlay>-r<n>`, for example `v1.14.7-v0.2.1-r1`. `r<n>` counts rebuilds of the same pair. See [docs/releasing.md](docs/releasing.md).

## Keeping up with upstream

1. Dependabot opens a pull request when Talos publishes a new `imager`. It tracks only `pins/talos.Dockerfile`.
2. The overlay is not tracked by Dependabot. [Image Factory](https://factory.talos.dev) pairs each Talos version with one `sbc-rockchip` release, and this repo uses the same pair. `pins check` in CI fails until someone runs `uv run pins sync` on the branch. That command writes the paired overlay pin to `overlay/Dockerfile` and the U-Boot build pins to `pins/sbc-rockchip.json`.
3. CI builds U-Boot, the derived overlay, the installer and the raw image in the pull request. Nothing is published from a pull request.
4. CI runs `check-hs200` on the built U-Boot binary, the external DTB and the copies inside the installer. The build fails if any device tree with the eMMC node lacks `mmc-hs200-1_8v` or if any node has an HS400 property. If a new U-Boot release moves the device-tree source and the patch stops applying, the build fails instead of shipping HS400.
5. CI also runs the check on the unpatched upstream files. When upstream drops HS400 on its own, the job reports it, and this repo can be retired in favour of the official image.
6. Merging to `main` and pushing a tag builds, signs and publishes the release.
7. Test on hardware before the image reaches a control plane. Upgrade one worker first.

### Hardware test

CI cannot boot a board. Pick the test from what changed in the Dependabot pull request:

| What changed | Example | Test on one worker |
|---|---|---|
| Talos patch release, same overlay and U-Boot | v1.14.7 to v1.14.8 | Short test |
| New `sbc-rockchip` release or new U-Boot version | v0.2.1 to v0.2.2 | Short test, then leave the worker on the new image overnight |
| Talos minor release (new kernel) | v1.14 to v1.15 | Short test, then leave the worker on the new image overnight |

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
uv run pins check
```

`check-hs200` reads any file, finds every flattened device tree in it and exits 1 when a check fails. Run against the official `sbc-rockchip` v0.2.1 and v0.3.0 files it reports 4 device trees in U-Boot, 2 of them with the eMMC node, and HS400 in all of them.

### Build steps

The `Build image` workflow (`.github/workflows/build.yml`) runs these scripts on a GitHub-hosted arm64 runner. Each script also runs on a Linux arm64 host with docker, jq, fdtput, mtools and uv.

1. `scripts/build-uboot.sh`: clones `sbc-rockchip` at the pinned tag, adds the HS200 step to the `rockpi4` U-Boot package with `patch-pkg`, and builds it.
2. `scripts/patch-dtb.sh`: copies the DTB out of the pinned overlay, patches it with `fdtput` and checks with `check-dtb-patch` that nothing else changed.
3. `scripts/build-overlay.sh`: builds the derived overlay for amd64 and arm64 and pushes it to a registry on the runner.
4. `scripts/build-images.sh`: runs Talos Imager with the overlay's own `rockpi4` profile (GRUB, external DTB) for the raw image, and the `installer` profile for the installer.
5. `scripts/verify-images.sh`: extracts U-Boot and the DTB from both outputs, runs `check-hs200` and compares checksums.
6. `scripts/upstream-watch.sh`: runs `check-hs200` on the unpatched upstream files and warns when they pass.

## License

MIT. See [LICENSE](LICENSE).
