# Releasing

> **Status:** the Release workflow is not built yet. This file describes the target process.

A release is a tag on `main` that names the upstream versions in the image:

```text
v<talos>-<overlay>-r<n>        for example v1.13.8-v0.3.0-r1
```

- `<talos>` is the Talos version of `imager` and `installer-base`.
- `<overlay>` is the `siderolabs/sbc-rockchip` release that the derived overlay starts from.
- `r<n>` starts at 1 and goes up when the same pair is built again, for example after a patch fix in this repo.

The project version in `pyproject.toml` belongs to the `check-hs200` tool and does not follow the tags.

## Cut a release

1. Merge the pull request that changes the pins. CI must pass on `main`.
2. Add a `## [v1.13.8-v0.3.0-r1] - YYYY-MM-DD` section to `CHANGELOG.md` with the upstream versions and any change in this repo. Commit it on `main`.
3. Create and push the annotated tag:

   ```bash
   git tag -a v1.13.8-v0.3.0-r1 -m "v1.13.8-v0.3.0-r1"
   git push origin v1.13.8-v0.3.0-r1
   ```

4. The Release workflow checks that the tag matches the pins and that the CHANGELOG section exists. It builds the images, runs `check-hs200`, pushes the installer to GHCR, signs it with cosign and creates the GitHub Release.
5. Run the hardware test in the README before you use the image on a control plane.

The `release tags` ruleset protects `v*` tags: they cannot be moved or deleted.
