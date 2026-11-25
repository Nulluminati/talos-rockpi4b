"""Build small flattened device tree (FDT) blobs for the tests."""

import struct

MAGIC = 0xD00DFEED
BEGIN_NODE, END_NODE, PROP, END = 1, 2, 3, 9


def _pad(data: bytes) -> bytes:
    return data + b"\0" * (-len(data) % 4)


def build(tree: dict) -> bytes:
    """Encode a nested dict as an FDT blob.

    A dict value is a child node. A bytes or str value is a property; a str gets a trailing NUL.
    The empty-string key at the top level is the root node.
    """
    strings = bytearray()
    offsets: dict[str, int] = {}

    def name_offset(name: str) -> int:
        if name not in offsets:
            offsets[name] = len(strings)
            strings.extend(name.encode() + b"\0")
        return offsets[name]

    def node(name: str, body: dict) -> bytes:
        out = struct.pack(">I", BEGIN_NODE) + _pad(name.encode() + b"\0")
        for key, value in body.items():
            if isinstance(value, dict):
                continue
            raw = value.encode() + b"\0" if isinstance(value, str) else value
            out += struct.pack(">III", PROP, len(raw), name_offset(key)) + _pad(raw)
        for key, value in body.items():
            if isinstance(value, dict):
                out += node(key, value)
        return out + struct.pack(">I", END_NODE)

    dt_struct = node("", tree) + struct.pack(">I", END)
    header_size = 40
    rsvmap = b"\0" * 16
    off_rsvmap = header_size
    off_struct = off_rsvmap + len(rsvmap)
    off_strings = off_struct + len(dt_struct)
    total = off_strings + len(strings)
    header = struct.pack(
        ">10I", MAGIC, total, off_struct, off_strings, off_rsvmap, 17, 16, 0, len(strings), len(dt_struct)
    )
    return header + rsvmap + dt_struct + bytes(strings)


def emmc_tree(*props: str) -> dict:
    """A tree with an RK3399 eMMC controller node that has the given boolean properties."""
    emmc = {"compatible": "rockchip,rk3399-sdhci-5.1"}
    emmc.update({p: b"" for p in props})
    return {"compatible": "radxa,rockpi4b", "mmc@fe330000": emmc, "chosen": {}}
