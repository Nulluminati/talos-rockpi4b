import pytest
from fdtbuild import build, emmc_tree

from talos_rockpi4b import dtb_diff

HS200 = "mmc-hs200-1_8v"
HS400 = "mmc-hs400-1_8v"
STROBE = "mmc-hs400-enhanced-strobe"


def _upstream() -> dict:
    tree = emmc_tree(HS400, STROBE)
    tree["mmc@fe330000"]["bus-width"] = b"\0\0\0\x08"
    tree["mmc@fe320000"] = {"status": "okay"}
    return tree


def _patched() -> dict:
    tree = _upstream()
    del tree["mmc@fe330000"][HS400]
    del tree["mmc@fe330000"][STROBE]
    tree["mmc@fe330000"][HS200] = b""
    return tree


def test_expected_patch_passes():
    assert dtb_diff.check_patch(build(_upstream()), build(_patched())) == []


def test_changed_property_elsewhere_fails():
    patched = _patched()
    patched["mmc@fe320000"]["status"] = "disabled"
    errors = dtb_diff.check_patch(build(_upstream()), build(patched))
    assert errors == ["/mmc@fe320000: status changed"]


def test_extra_property_on_the_emmc_node_fails():
    patched = _patched()
    patched["mmc@fe330000"]["max-frequency"] = b"\0\0\0\x01"
    errors = dtb_diff.check_patch(build(_upstream()), build(patched))
    assert errors == ["/mmc@fe330000: max-frequency added"]


def test_removed_node_fails():
    patched = _patched()
    del patched["chosen"]
    assert dtb_diff.check_patch(build(_upstream()), build(patched)) == ["/chosen: node removed"]


def test_added_node_fails():
    patched = _patched()
    patched["extra"] = {}
    assert dtb_diff.check_patch(build(_upstream()), build(patched)) == ["/extra: node added"]


@pytest.mark.parametrize("prop", [HS400, STROBE])
def test_missing_part_of_the_patch_fails(prop):
    patched = _patched()
    patched["mmc@fe330000"][prop] = b""
    errors = dtb_diff.check_patch(build(_upstream()), build(patched))
    assert errors == [f"/mmc@fe330000: {prop} was not removed"]


def test_hs200_not_added_fails():
    patched = _patched()
    del patched["mmc@fe330000"][HS200]
    errors = dtb_diff.check_patch(build(_upstream()), build(patched))
    assert errors == [f"/mmc@fe330000: {HS200} was not added"]


def test_two_blobs_fail():
    data = build(_patched()) + build(_patched())
    assert dtb_diff.check_patch(build(_upstream()), data) == ["patched file has 2 device trees, expected 1"]


def test_main(tmp_path, capsys):
    upstream = tmp_path / "upstream.dtb"
    upstream.write_bytes(build(_upstream()))
    good = tmp_path / "good.dtb"
    good.write_bytes(build(_patched()))
    bad = tmp_path / "bad.dtb"
    bad.write_bytes(build(_upstream()))

    assert dtb_diff.main([str(upstream), str(good)]) == 0
    assert "OK" in capsys.readouterr().out
    assert dtb_diff.main([str(upstream), str(bad)]) == 1
    assert "was not removed" in capsys.readouterr().out
