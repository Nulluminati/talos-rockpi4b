# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/). Release tags name the upstream versions in each image (`v<talos>-<overlay>-r<n>`); see [docs/releasing.md](docs/releasing.md).

## [Unreleased]

## [v1.14.7-v0.2.1-r1] - 2026-11-25

First release. Talos v1.14.7 with the `sbc-rockchip` v0.2.1 `rockpi4` overlay (U-Boot 2026.01, TF-A lts-v2.14.6), as paired by Image Factory.

### Added

- Installer image `ghcr.io/nulluminati/talos-rockpi4b-installer` and derived overlay `ghcr.io/nulluminati/talos-rockpi4b-overlay`, signed with cosign.
- `metal-arm64.raw.xz` with checksums and the build log.
- U-Boot built with `mmc-hs400-1_8v` and `mmc-hs400-enhanced-strobe` removed from `rk3399-rock-pi-4.dtsi`.
- External `rk3399-rock-pi-4b.dtb` with the HS400 properties replaced by `mmc-hs200-1_8v`.
- `pins`: keeps the overlay and U-Boot build pins in step with the Talos pin through Image Factory.
- `patch-pkg` and `check-dtb-patch`: patch the U-Boot package and prove that the DTB patch changes nothing else.
- `check-hs200`: finds every device tree in a DTB or U-Boot binary and fails on any HS400 property or an eMMC node without `mmc-hs200-1_8v`.
