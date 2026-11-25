"""Check that device trees keep the RK3399 eMMC in HS200.

A file can be a single DTB or a binary that embeds device trees, such as
``u-boot-rockchip.bin``. Every flattened device tree (FDT) blob in the file is
parsed. The check fails when:

- no valid FDT blob is found,
- no blob contains the eMMC controller node,
- an eMMC node does not have ``mmc-hs200-1_8v``,
- any node in any blob has an HS400 property.
"""

import re
import struct
import sys
from dataclasses import dataclass, field
from pathlib import Path

FDT_MAGIC = 0xD00DFEED
_MAGIC_BYTES = struct.pack(">I", FDT_MAGIC)
_HEADER = struct.Struct(">10I")
_BEGIN_NODE, _END_NODE, _PROP, _NOP, _END = 1, 2, 3, 4, 9

HS200 = "mmc-hs200-1_8v"
HS400_PROPERTIES = ("mmc-hs400-1_8v", "mmc-hs400-1_2v", "mmc-hs400-enhanced-strobe")
# The RK3399 SDHCI controller that drives the eMMC. Older trees name the node sdhci@.
EMMC_NODE = re.compile(r"^(mmc|sdhci)@fe330000$")

Tree = dict[str, dict[str, bytes]]


@dataclass
class Result:
    blobs: int = 0
    emmc_blobs: int = 0
    errors: list[str] = field(default_factory=list)


def _cstring(data: bytes, start: int) -> tuple[str, int]:
    end = data.index(b"\0", start)
    return data[start:end].decode("ascii"), end + 1


def _align(offset: int) -> int:
    return (offset + 3) & ~3


def parse_fdt(blob: bytes) -> Tree:
    """Return {node path: {property name: value}} for one FDT blob.

    Raises ValueError when the blob is not a valid FDT.
    """
    if len(blob) < _HEADER.size:
        raise ValueError("blob is shorter than an FDT header")
    magic, total, off_struct, off_strings, _, version, _, _, size_strings, size_struct = _HEADER.unpack_from(blob)
    if magic != FDT_MAGIC or total > len(blob) or version < 16:
        raise ValueError("not an FDT header")
    if off_struct + size_struct > total or off_strings + size_strings > total:
        raise ValueError("FDT blocks are outside the blob")

    strings = blob[off_strings : off_strings + size_strings]
    tree: Tree = {}
    stack: list[str] = []
    pos = off_struct
    end = off_struct + size_struct
    try:
        while pos < end:
            (token,) = struct.unpack_from(">I", blob, pos)
            pos += 4
            if token == _BEGIN_NODE:
                name, pos = _cstring(blob, pos)
                pos = _align(pos)
                path = "/" if not stack else stack[-1].rstrip("/") + "/" + name
                stack.append(path)
                tree.setdefault(path, {})
            elif token == _END_NODE:
                stack.pop()
            elif token == _PROP:
                length, name_offset = struct.unpack_from(">II", blob, pos)
                pos += 8
                name, _ = _cstring(strings, name_offset)
                tree[stack[-1]][name] = bytes(blob[pos : pos + length])
                pos = _align(pos + length)
            elif token == _NOP:
                continue
            elif token == _END:
                if stack:
                    raise ValueError("FDT ends inside a node")
                return tree
            else:
                raise ValueError(f"unknown FDT token {token:#x}")
    except (struct.error, IndexError, UnicodeDecodeError) as exc:
        raise ValueError(f"damaged FDT structure: {exc}") from exc
    raise ValueError("FDT structure has no end token")


def find_fdts(data: bytes) -> list[tuple[int, Tree]]:
    """Return (offset, tree) for each valid FDT blob in data."""
    found = []
    pos = data.find(_MAGIC_BYTES)
    while pos != -1:
        try:
            (total,) = struct.unpack_from(">I", data, pos + 4)
            tree = parse_fdt(data[pos : pos + total])
        except (ValueError, struct.error):
            pos = data.find(_MAGIC_BYTES, pos + 1)
            continue
        found.append((pos, tree))
        pos = data.find(_MAGIC_BYTES, pos + total)
    return found


def check_bytes(data: bytes) -> Result:
    result = Result()
    for offset, tree in find_fdts(data):
        result.blobs += 1
        has_emmc = False
        for path, props in tree.items():
            for name in HS400_PROPERTIES:
                if name in props:
                    result.errors.append(f"blob at {offset:#x}: {path} has {name}")
            if EMMC_NODE.match(path.rsplit("/", 1)[-1]):
                has_emmc = True
                if HS200 not in props:
                    result.errors.append(f"blob at {offset:#x}: {path} has no {HS200}")
        if has_emmc:
            result.emmc_blobs += 1
    if result.blobs == 0:
        result.errors.append("no device tree found")
    elif result.emmc_blobs == 0:
        result.errors.append("no eMMC node in any device tree")
    return result


def main(argv: list[str] | None = None) -> int:
    paths = sys.argv[1:] if argv is None else argv
    if not paths:
        print("usage: check-hs200 FILE...", file=sys.stderr)
        return 2
    failed = False
    for name in paths:
        result = check_bytes(Path(name).read_bytes())
        if result.errors:
            failed = True
            print(f"FAIL {name}: {result.blobs} device trees, {result.emmc_blobs} with the eMMC node")
            for error in result.errors:
                print(f"  {error}")
        else:
            print(f"OK   {name}: {result.blobs} device trees, {result.emmc_blobs} with the eMMC node, HS200 only")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
