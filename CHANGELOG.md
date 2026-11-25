# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/). Release tags name the upstream versions in each image (`v<talos>-<overlay>-r<n>`); see [docs/releasing.md](docs/releasing.md).

## [Unreleased]

### Added

- `check-hs200`: finds every device tree in a DTB or U-Boot binary and fails on any HS400 property or an eMMC node without `mmc-hs200-1_8v`.
