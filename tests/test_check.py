import struct

import pytest
from fdtbuild import build, emmc_tree

from talos_rockpi4b import check

HS200 = "mmc-hs200-1_8v"
HS400 = "mmc-hs400-1_8v"
STROBE = "mmc-hs400-enhanced-strobe"


def test_parse_reads_nodes_and_properties():
    tree = check.parse_fdt(build(emmc_tree(HS200)))
    assert tree["/mmc@fe330000"][HS200] == b""
    assert tree["/mmc@fe330000"]["compatible"] == b"rockchip,rk3399-sdhci-5.1\0"
    assert "/chosen" in tree


def test_dtb_with_hs200_only_passes():
    result = check.check_bytes(build(emmc_tree(HS200)))
    assert result.errors == []
    assert result.blobs == 1
    assert result.emmc_blobs == 1


@pytest.mark.parametrize("bad", [HS400, STROBE])
def test_dtb_with_hs400_property_fails(bad):
    result = check.check_bytes(build(emmc_tree(HS200, bad)))
    assert any(bad in e and "/mmc@fe330000" in e for e in result.errors)


def test_hs400_property_on_any_node_fails():
    tree = emmc_tree(HS200)
    tree["mmc@fe320000"] = {STROBE: b""}
    result = check.check_bytes(build(tree))
    assert any("/mmc@fe320000" in e for e in result.errors)


def test_emmc_node_without_hs200_fails():
    result = check.check_bytes(build(emmc_tree()))
    assert any(HS200 in e for e in result.errors)


def test_old_sdhci_node_name_counts_as_emmc():
    tree = {"sdhci@fe330000": {HS200: b""}}
    result = check.check_bytes(build(tree))
    assert result.errors == []
    assert result.emmc_blobs == 1


def test_no_emmc_node_fails():
    result = check.check_bytes(build({"chosen": {}}))
    assert result.emmc_blobs == 0
    assert any("no eMMC node" in e for e in result.errors)


def test_uboot_binary_with_embedded_trees():
    data = b"\x55" * 1000 + build({"chosen": {}}) + b"\xaa" * 333 + build(emmc_tree(HS200)) + b"\0" * 64
    result = check.check_bytes(data)
    assert result.errors == []
    assert result.blobs == 2
    assert result.emmc_blobs == 1


def test_uboot_binary_with_one_bad_tree_fails():
    data = b"\x55" * 100 + build(emmc_tree(HS200)) + build(emmc_tree(HS200, HS400))
    result = check.check_bytes(data)
    assert result.blobs == 2
    assert any(HS400 in e for e in result.errors)


def test_false_magic_is_skipped():
    fake = struct.pack(">II", check.FDT_MAGIC, 0xFFFFFFF0) + b"junk" * 10
    data = fake + build(emmc_tree(HS200))
    result = check.check_bytes(data)
    assert result.errors == []
    assert result.blobs == 1


def test_binary_without_any_tree_fails():
    result = check.check_bytes(b"\x00\x11" * 500)
    assert result.blobs == 0
    assert any("no device tree" in e for e in result.errors)


def test_main_exit_codes(tmp_path, capsys):
    good = tmp_path / "good.dtb"
    good.write_bytes(build(emmc_tree(HS200)))
    bad = tmp_path / "bad.bin"
    bad.write_bytes(build(emmc_tree(HS200, STROBE)))

    assert check.main([str(good)]) == 0
    assert "OK" in capsys.readouterr().out

    assert check.main([str(good), str(bad)]) == 1
    out = capsys.readouterr().out
    assert "FAIL" in out and STROBE in out
