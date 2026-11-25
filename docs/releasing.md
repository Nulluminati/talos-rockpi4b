# Releasing

A release is a tag on `main` that names the upstream versions in the image:

```text
v<talos>-<overlay>-r<n>        for example v1.14.7-v0.2.1-r1
```

- `<talos>` is the Talos version of `imager` and `installer-base`, from `pins/talos.Dockerfile`.
- `<overlay>` is the `siderolabs/sbc-rockchip` release that the derived overlay starts from, from `overlay/Dockerfile`. Image Factory picks it: `uv run pins sync` writes the release that Image Factory pairs with `<talos>`.
- `r<n>` starts at 1 and goes up when the same pair is built again, for example after a patch fix in this repo.

The project version in `pyproject.toml` belongs to the `check-hs200` tool and does not follow the tags.

## Cut a release

1. Merge the pull request that changes the pins. CI must pass on `main`, including `pins check` and `Build image`. Run `uv run pins tag` to print the `v<talos>-<overlay>` part of the tag.
2. Add a `## [v1.14.7-v0.2.1-r1] - YYYY-MM-DD` section to `CHANGELOG.md` with the upstream versions and any change in this repo. Use the release date: the release gate rejects the `YYYY-MM-DD` placeholder. Commit it on `main`.
3. Create and push the annotated tag:

   ```bash
   git tag -a v1.14.7-v0.2.1-r1 -m "v1.14.7-v0.2.1-r1"
   git push origin v1.14.7-v0.2.1-r1
   ```

4. The Release workflow checks that the tag is on `main`, that it matches the pins (`pins tag`), that the pins match Image Factory (`pins check`) and that the CHANGELOG section exists. It runs the same build as CI. Then it pushes the overlay and the installer to GHCR, signs both digests with cosign and creates the GitHub Release with `metal-arm64.raw.xz`, `SHA256SUMS` and `build.log`.
5. Run the hardware test in the README before you use the image on a control plane.

The Release job rebuilds the overlay from the checked U-Boot and DTB before it pushes. Its digest differs from the overlay that the build fed to Imager, but the files in it are the same bytes.

After the first release, open the two GHCR packages (`talos-rockpi4b-installer`, `talos-rockpi4b-overlay`) and set their visibility to public if GitHub created them private.

The `release tags` ruleset protects `v*` tags: they cannot be moved or deleted.
