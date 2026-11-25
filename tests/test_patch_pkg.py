import subprocess
from pathlib import Path

import pytest

from talos_rockpi4b import patch_pkg

# artifacts/rockpi4/u-boot/pkg.yaml from siderolabs/sbc-rockchip v0.2.1, prepare section.
PKG = """\
steps:
  - sources:
      - url: https://ftp.denx.de/pub/u-boot/u-boot-{{ .uboot_version }}.tar.bz2
        destination: u-boot.tar.bz2
    prepare:
      # rock-pi-4-rk3399
      - |
        tar xf u-boot.tar.bz2 --strip-components=1
      - |
        make rock-pi-4-rk3399_defconfig
    build:
      - |
        make -j $(nproc)
"""

DTSI_SDHCI = """\
&sdhci {
\tmax-frequency = <150000000>;
\tbus-width = <8>;
\tmmc-hs400-1_8v;
\tmmc-hs400-enhanced-strobe;
\tnon-removable;
\tstatus = "okay";
};
"""


def test_patch_inserts_one_step_after_the_tar_line():
    patched = patch_pkg.patch(PKG)
    lines = patched.splitlines()
    tar = lines.index("        tar xf u-boot.tar.bz2 --strip-components=1")
    assert lines[tar + 1] == "      - |"
    assert lines[tar + 2] == "        " + patch_pkg.MARKER
    assert "        dtsi=dts/upstream/src/arm64/rockchip/rk3399-rock-pi-4.dtsi" in lines
    defconfig = lines.index("        make rock-pi-4-rk3399_defconfig")
    assert lines[defconfig - 1] == "      - |"
    # Only the new step is added. The rest of the file is unchanged.
    assert patched.replace(patch_pkg.STEP, "") == PKG


def test_step_has_no_template_braces():
    # bldr renders pkg.yaml as a Go template.
    assert "{{" not in patch_pkg.STEP


def test_patch_fails_on_a_patched_file():
    with pytest.raises(patch_pkg.PatchError, match="already"):
        patch_pkg.patch(patch_pkg.patch(PKG))


def test_patch_fails_without_the_anchor():
    with pytest.raises(patch_pkg.PatchError, match="no line"):
        patch_pkg.patch(PKG.replace("tar xf u-boot.tar.bz2", "tar -xf u-boot.tar.bz2"))


def test_patch_fails_with_two_anchors():
    twice = PKG.replace(
        "      - |\n        make rock",
        "      - |\n        tar xf u-boot.tar.xz --strip-components=1\n      - |\n        make rock",
    )
    with pytest.raises(patch_pkg.PatchError, match="2 lines"):
        patch_pkg.patch(twice)


def _run_step(tmp_path: Path, dtsi: str) -> subprocess.CompletedProcess:
    path = tmp_path / "dts/upstream/src/arm64/rockchip/rk3399-rock-pi-4.dtsi"
    path.parent.mkdir(parents=True)
    path.write_text(dtsi)
    script = "\n".join(line.removeprefix("        ") for line in patch_pkg.STEP.splitlines()[1:])
    return subprocess.run(["bash", "-c", script], cwd=tmp_path, capture_output=True, text=True)


def test_step_deletes_both_hs400_lines(tmp_path):
    result = _run_step(tmp_path, DTSI_SDHCI)
    assert result.returncode == 0, result.stderr
    dtsi = (tmp_path / "dts/upstream/src/arm64/rockchip/rk3399-rock-pi-4.dtsi").read_text()
    assert dtsi == DTSI_SDHCI.replace("\tmmc-hs400-1_8v;\n", "").replace("\tmmc-hs400-enhanced-strobe;\n", "")


@pytest.mark.parametrize("line", ["\tmmc-hs400-1_8v;\n", "\tmmc-hs400-enhanced-strobe;\n"])
def test_step_fails_when_a_line_is_missing(tmp_path, line):
    result = _run_step(tmp_path, DTSI_SDHCI.replace(line, ""))
    assert result.returncode != 0
    assert line.strip() in result.stderr


def test_step_fails_when_the_dtsi_is_missing(tmp_path):
    script = "\n".join(line.removeprefix("        ") for line in patch_pkg.STEP.splitlines()[1:])
    result = subprocess.run(["bash", "-c", script], cwd=tmp_path, capture_output=True, text=True)
    assert result.returncode != 0


def test_main_patches_the_file(tmp_path, capsys):
    path = tmp_path / "pkg.yaml"
    path.write_text(PKG)
    assert patch_pkg.main([str(path)]) == 0
    assert path.read_text() == patch_pkg.patch(PKG)

    assert patch_pkg.main([str(path)]) == 1
    assert "already" in capsys.readouterr().err
