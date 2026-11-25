import json
from pathlib import Path

import pytest

from talos_rockpi4b import pins

DATA = Path(__file__).parent / "data"
IMAGER = "ghcr.io/siderolabs/imager:v1.14.7@sha256:e95c8bdb8e581fd56fb78284dc44f0bf477329980626ac444d12eb43bedc7bc7"
OVERLAY_DIGEST = "sha256:9ce1d1d2ca1c0866bafd9728bd12eb0ef70b386318b033db2c841ce35e33b882"
TAG_OBJECT = "081d08776d88cc490bf2fbe12c392f4455601a0e"
COMMIT = "2db5d21112f9be2cf0ec9cdc1f2540b7cc98cedc"
ROOT_COMMIT = "56dfd708ea36b47ca7a2e61158d0d8f7a98ae960"
COMMITS_URL = f"https://api.github.com/repos/siderolabs/sbc-rockchip/commits?sha={COMMIT}&per_page=1"
LAST_PAGE_URL = f"https://api.github.com/repositories/771586612/commits?sha={COMMIT}&per_page=1&page=68"


def _json(value) -> pins.Response:
    return pins.Response(json.dumps(value).encode(), {})


def recorded_web() -> dict[str, pins.Response]:
    """Responses recorded from Image Factory and GitHub on 2026-11-25."""
    return {
        "https://factory.talos.dev/version/v1.14.7/overlays/official": pins.Response(
            (DATA / "factory-v1.14.7-overlays.json").read_bytes(), {}
        ),
        "https://api.github.com/repos/siderolabs/sbc-rockchip/git/ref/tags/v0.2.1": _json(
            {"ref": "refs/tags/v0.2.1", "object": {"sha": TAG_OBJECT, "type": "tag"}}
        ),
        f"https://api.github.com/repos/siderolabs/sbc-rockchip/git/tags/{TAG_OBJECT}": _json(
            {"object": {"sha": COMMIT, "type": "commit"}}
        ),
        f"https://raw.githubusercontent.com/siderolabs/sbc-rockchip/{COMMIT}/Makefile": pins.Response(
            (DATA / "sbc-rockchip-v0.2.1-Makefile").read_bytes(), {}
        ),
        COMMITS_URL: pins.Response(
            json.dumps([{"sha": COMMIT, "parents": [{"sha": "x"}]}]).encode(),
            {"Link": f'<{LAST_PAGE_URL.replace("68", "2")}>; rel="next", <{LAST_PAGE_URL}>; rel="last"'},
        ),
        LAST_PAGE_URL: _json(
            [{"sha": ROOT_COMMIT, "parents": [], "commit": {"committer": {"date": "2024-03-13T15:14:11Z"}}}]
        ),
    }


def fetcher(web: dict[str, pins.Response]):
    def fetch(url: str) -> pins.Response:
        if url not in web:
            raise AssertionError(f"unexpected request: {url}")
        return web[url]

    return fetch


@pytest.fixture
def repo(tmp_path):
    (tmp_path / "pins").mkdir()
    (tmp_path / "pins" / "talos.Dockerfile").write_text(f"FROM {IMAGER}\n")
    return tmp_path


def test_read_talos_tag(repo):
    assert pins.read_talos_tag(repo) == "v1.14.7"


def test_read_talos_tag_needs_a_digest(repo):
    (repo / "pins" / "talos.Dockerfile").write_text("FROM ghcr.io/siderolabs/imager:v1.14.7\n")
    with pytest.raises(pins.PinError, match="digest"):
        pins.read_talos_tag(repo)


def test_factory_overlay_picks_rockpi4():
    overlay = pins.factory_overlay("v1.14.7", fetcher(recorded_web()))
    assert overlay == pins.Overlay(tag="v0.2.1", digest=OVERLAY_DIGEST)


def test_factory_overlay_without_rockpi4_fails():
    web = recorded_web()
    url = "https://factory.talos.dev/version/v1.14.7/overlays/official"
    web[url] = _json([x for x in json.loads(web[url].body) if x["name"] != "rockpi4"])
    with pytest.raises(pins.PinError, match="rockpi4"):
        pins.factory_overlay("v1.14.7", fetcher(web))


def test_resolve_commit_dereferences_an_annotated_tag():
    assert pins.resolve_commit("v0.2.1", fetcher(recorded_web())) == COMMIT


def test_resolve_commit_of_a_lightweight_tag():
    web = recorded_web()
    web["https://api.github.com/repos/siderolabs/sbc-rockchip/git/ref/tags/v0.2.1"] = _json(
        {"object": {"sha": COMMIT, "type": "commit"}}
    )
    assert pins.resolve_commit("v0.2.1", fetcher(web)) == COMMIT


def test_makefile_vars():
    text = (DATA / "sbc-rockchip-v0.2.1-Makefile").read_text()
    assert pins.makefile_vars(text) == {
        "PKGS_PREFIX": "ghcr.io/siderolabs",
        "PKGS": "v1.14.0-alpha.0-127-g7d8b87b",
        "TOOLS_PREFIX": "ghcr.io/siderolabs",
        "TOOLS": "v1.14.0-alpha.0-29-g80fd6eb",
    }


def test_makefile_vars_missing_fails():
    with pytest.raises(pins.PinError, match="TOOLS"):
        pins.makefile_vars("PKGS_PREFIX ?= a\nPKGS ?= b\nTOOLS_PREFIX ?= c\n")


def test_source_date_epoch_is_the_root_commit_time():
    assert pins.source_date_epoch(COMMIT, fetcher(recorded_web())) == 1710342851


def test_source_date_epoch_rejects_a_commit_with_parents():
    web = recorded_web()
    web[LAST_PAGE_URL] = _json(
        [{"sha": "y", "parents": [{"sha": "z"}], "commit": {"committer": {"date": "2024-03-13T15:14:11Z"}}}]
    )
    with pytest.raises(pins.PinError, match="root commit"):
        pins.source_date_epoch(COMMIT, fetcher(web))


def test_sync_writes_the_overlay_and_build_pins(repo):
    changed = pins.sync(repo, fetcher(recorded_web()))
    assert sorted(p.relative_to(repo).as_posix() for p in changed) == ["overlay/Dockerfile", "pins/sbc-rockchip.json"]

    dockerfile = (repo / "overlay" / "Dockerfile").read_text()
    assert f"FROM ghcr.io/siderolabs/sbc-rockchip:v0.2.1@{OVERLAY_DIGEST}\n" in dockerfile
    assert "COPY u-boot-rockchip.bin /artifacts/arm64/u-boot/rockpi4/u-boot-rockchip.bin\n" in dockerfile
    assert "COPY rk3399-rock-pi-4b.dtb /artifacts/arm64/dtb/rockchip/rk3399-rock-pi-4b.dtb\n" in dockerfile

    assert json.loads((repo / "pins" / "sbc-rockchip.json").read_text()) == {
        "tag": "v0.2.1",
        "commit": COMMIT,
        "pkgs_prefix": "ghcr.io/siderolabs",
        "pkgs": "v1.14.0-alpha.0-127-g7d8b87b",
        "tools_prefix": "ghcr.io/siderolabs",
        "tools": "v1.14.0-alpha.0-29-g80fd6eb",
        "source_date_epoch": 1710342851,
    }


def test_sync_twice_changes_nothing(repo):
    pins.sync(repo, fetcher(recorded_web()))
    assert pins.sync(repo, fetcher(recorded_web())) == []


def test_check_passes_after_sync(repo):
    pins.sync(repo, fetcher(recorded_web()))
    assert pins.check(repo, fetcher(recorded_web())) == []


def test_check_fails_on_a_hand_edited_overlay_pin(repo):
    pins.sync(repo, fetcher(recorded_web()))
    path = repo / "overlay" / "Dockerfile"
    path.write_text(path.read_text().replace("v0.2.1", "v0.3.0"))
    assert pins.check(repo, fetcher(recorded_web())) == ["overlay/Dockerfile"]


def test_check_fails_when_files_are_missing(repo):
    assert pins.check(repo, fetcher(recorded_web())) == ["overlay/Dockerfile", "pins/sbc-rockchip.json"]


def test_tag_stem(repo):
    pins.sync(repo, fetcher(recorded_web()))
    assert pins.tag_stem(repo) == "v1.14.7-v0.2.1"


@pytest.mark.parametrize("tag", ["v1.14.7-v0.2.1-r1", "v1.14.7-v0.2.1-r12"])
def test_release_tag_matches(repo, tag):
    pins.sync(repo, fetcher(recorded_web()))
    assert pins.tag_matches(repo, tag)


@pytest.mark.parametrize("tag", ["v1.14.7-v0.2.1", "v1.14.7-v0.2.1-r0", "v1.14.6-v0.2.1-r1", "v1.14.7-v0.3.0-r1"])
def test_release_tag_does_not_match(repo, tag):
    pins.sync(repo, fetcher(recorded_web()))
    assert not pins.tag_matches(repo, tag)


def test_main_check_and_tag(repo, monkeypatch, capsys):
    monkeypatch.chdir(repo)
    monkeypatch.setattr(pins, "http_fetch", fetcher(recorded_web()))

    assert pins.main(["check"]) == 1
    assert "overlay/Dockerfile" in capsys.readouterr().out

    assert pins.main(["sync"]) == 0
    assert pins.main(["check"]) == 0
    capsys.readouterr()

    assert pins.main(["tag"]) == 0
    assert capsys.readouterr().out == "v1.14.7-v0.2.1\n"
    assert pins.main(["tag", "v1.14.7-v0.2.1-r1"]) == 0
    assert pins.main(["tag", "v1.14.7-v0.2.0-r1"]) == 1
