"""Prove that the patched external DTB differs from upstream only in the eMMC speed mode.

``check-dtb-patch UPSTREAM PATCHED`` parses both files and compares the trees.
The only allowed difference is on ``/mmc@fe330000``: ``mmc-hs400-1_8v`` and
``mmc-hs400-enhanced-strobe`` removed, ``mmc-hs200-1_8v`` added with an empty
value. Any other added, removed or changed node or property fails the check.
"""

import sys
from pathlib import Path

from talos_rockpi4b.check import HS200, Tree, find_fdts

EMMC_PATH = "/mmc@fe330000"
REMOVED = ("mmc-hs400-1_8v", "mmc-hs400-enhanced-strobe")


def _one_tree(data: bytes, label: str) -> Tree | str:
    trees = find_fdts(data)
    if len(trees) != 1:
        return f"{label} file has {len(trees)} device trees, expected 1"
    return trees[0][1]


def diff_trees(upstream: Tree, patched: Tree) -> list[str]:
    """Return one line for each difference that the HS200 patch does not explain."""
    errors = []
    for path in sorted(upstream.keys() - patched.keys()):
        errors.append(f"{path}: node removed")
    for path in sorted(patched.keys() - upstream.keys()):
        errors.append(f"{path}: node added")
    for path in sorted(upstream.keys() & patched.keys()):
        before, after = dict(upstream[path]), dict(patched[path])
        if path == EMMC_PATH:
            for name in REMOVED:
                if name in after:
                    errors.append(f"{path}: {name} was not removed")
                before.pop(name, None)
                after.pop(name, None)
            if after.pop(HS200, None) != b"":
                errors.append(f"{path}: {HS200} was not added")
            before.pop(HS200, None)
        for name in sorted(before.keys() - after.keys()):
            errors.append(f"{path}: {name} removed")
        for name in sorted(after.keys() - before.keys()):
            errors.append(f"{path}: {name} added")
        for name in sorted(before.keys() & after.keys()):
            if before[name] != after[name]:
                errors.append(f"{path}: {name} changed")
    return errors


def check_patch(upstream_data: bytes, patched_data: bytes) -> list[str]:
    upstream = _one_tree(upstream_data, "upstream")
    patched = _one_tree(patched_data, "patched")
    errors = [tree for tree in (upstream, patched) if isinstance(tree, str)]
    if errors:
        return errors
    return diff_trees(upstream, patched)


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    if len(args) != 2:
        print("usage: check-dtb-patch UPSTREAM PATCHED", file=sys.stderr)
        return 2
    upstream, patched = args
    errors = check_patch(Path(upstream).read_bytes(), Path(patched).read_bytes())
    if errors:
        print(f"FAIL {patched}: differs from {upstream} beyond the HS200 patch")
        for error in errors:
            print(f"  {error}")
        return 1
    print(f"OK   {patched}: only the HS200 patch on {EMMC_PATH} differs from {upstream}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
