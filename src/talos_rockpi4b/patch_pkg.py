"""Patch the sbc-rockchip ``rockpi4`` U-Boot package to keep the eMMC in HS200.

``patch-pkg PKG_YAML`` edits ``artifacts/rockpi4/u-boot/pkg.yaml`` in place. It
adds one prepare step right after the step that unpacks the U-Boot source. The
step deletes ``mmc-hs400-1_8v`` and ``mmc-hs400-enhanced-strobe`` from the
upstream ``rk3399-rock-pi-4.dtsi`` that U-Boot embeds. U-Boot's own
``rk3399-rock-pi-4-u-boot.dtsi`` already adds ``mmc-hs200-1_8v``.

The patch fails when the unpack line is missing or found more than once, and
the step fails the build when either HS400 line is not in the dtsi.

``patch-pkg --fedora-mirror PKG_YAML`` also changes the U-Boot source URL from
ftp.denx.de to the Fedora package cache, which keeps the same release tarball
by its SHA-512. bldr still checks the SHA-256 and SHA-512 pins of the tarball.
"""

import re
import sys
from pathlib import Path

MARKER = "# talos-rockpi4b: keep the eMMC in HS200"
DTSI = "dts/upstream/src/arm64/rockchip/rk3399-rock-pi-4.dtsi"
_ANCHOR = re.compile(r"^( *)tar xf u-boot\.tar\.\S+.*$", re.M)
DENX_URL = "https://ftp.denx.de/pub/u-boot/u-boot-{{ .uboot_version }}.tar.bz2"
FEDORA_URL = (
    "https://src.fedoraproject.org/repo/pkgs/uboot-tools/u-boot-{{ .uboot_version }}.tar.bz2"
    "/sha512/{{ .uboot_sha512 }}/u-boot-{{ .uboot_version }}.tar.bz2"
)

# The script lines of the step. bldr renders pkg.yaml as a Go template, so the
# script must not contain double braces.
_SCRIPT = f"""\
{MARKER}
set -euo pipefail
dtsi={DTSI}
test -f "$dtsi"
for prop in mmc-hs400-1_8v mmc-hs400-enhanced-strobe; do
  count=$(grep -c "^[[:space:]]*$prop;\\$" "$dtsi" || true)
  if [ "$count" != 1 ]; then
    echo "$dtsi: expected 1 line '$prop;', found $count" >&2
    exit 1
  fi
  sed -i "/^[[:space:]]*$prop;\\$/d" "$dtsi"
done
"""


class PatchError(Exception):
    pass


def _step(indent: int) -> str:
    item = " " * (indent - 2) + "- |\n"
    return item + "".join(" " * indent + line + "\n" for line in _SCRIPT.splitlines())


STEP = _step(8)


def patch(text: str) -> str:
    if MARKER in text:
        raise PatchError("pkg.yaml is already patched")
    anchors = list(_ANCHOR.finditer(text))
    if not anchors:
        raise PatchError("pkg.yaml has no line 'tar xf u-boot.tar.*'")
    if len(anchors) > 1:
        raise PatchError(f"pkg.yaml has {len(anchors)} lines 'tar xf u-boot.tar.*', expected 1")
    anchor = anchors[0]
    end = anchor.end() + 1
    return text[:end] + _step(len(anchor.group(1))) + text[end:]


def use_fedora_mirror(text: str) -> str:
    """Change the U-Boot source URL from ftp.denx.de to the Fedora package cache."""
    count = text.count(f"url: {DENX_URL}\n")
    if count != 1:
        raise PatchError(f"pkg.yaml has {count} lines 'url: {DENX_URL}', expected 1 (ftp.denx.de)")
    return text.replace(f"url: {DENX_URL}\n", f"url: {FEDORA_URL}\n")


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    mirror = args[:1] == ["--fedora-mirror"]
    if mirror:
        args = args[1:]
    if len(args) != 1:
        print("usage: patch-pkg [--fedora-mirror] PKG_YAML", file=sys.stderr)
        return 2
    path = Path(args[0])
    try:
        text = path.read_text()
        if mirror:
            text = use_fedora_mirror(text)
        path.write_text(patch(text))
    except PatchError as exc:
        print(f"FAIL {path}: {exc}", file=sys.stderr)
        return 1
    print(f"OK   {path}: added the HS200 step" + (", U-Boot source from the Fedora package cache" if mirror else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
