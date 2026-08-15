#!/usr/bin/env python3
"""Dump an OpenAccess .oa file using the format-accurate primitives.

Usage:
  oadump.py <file.oa>                     header + directory + string summary
  oadump.py <file.oa> header              header fields
  oadump.py <file.oa> toc                 table directory
  oadump.py <file.oa> strings             decoded string table
  oadump.py <file.oa> table <id>          hex + int32 dump of one table
  oadump.py <file.oa> packed <id>         decode a table as packed-UInt4 stream
  oadump.py <file.oa> refs <id>           packed-UInt4 stream, resolving string refs

<id> is hexadecimal (e.g. 0xa, 0x107).
"""

import os
import struct
import sys
from typing import List

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from oaparser.format import (
    OaFile, unpack_packed_uint4, scan_packed_uint4,
    TABLE_STRING, TABLE_NAME, DELETED_OFFSET,
    parse_base_tbl, parse_byte_table, looks_like_byte_tbl,
)

TABLE_NAMES = {
    0x01: "global metadata", 0x04: "flags", 0x05: "timestamp",
    0x06: "last-saved time", 0x07: "master map", 0x08: "data table",
    0x0A: "string table", 0x0B: "property list", 0x0C: "netlist data",
    0x19: "create time", 0x1C: "data-model + build", 0x1D: "build info",
    0x1F: "database map delta", 0x24: "design database table", 0x28: "database marker",
    0x101: "nets", 0x102: "name table",
    0x103: "terminals", 0x105: "dfII instances",
    0x106: "module instance header", 0x107: "instances",
    0x109: "instance terminals", 0x10C: "occurrences", 0x10D: "dfII data",
    0x10E: "dfII data", 0x10F: "dfII data", 0x114: "temp connectivity",
    0x116: "temp connectivity", 0x132: "blocks", 0x133: "modules",
    0x13B: "dfII data", 0x13C: "dfII data", 0x13D: "dfII data",
    0x13E: "app data", 0x25: "(deleted slot)", 0x26: "(deleted slot)",
    0x2A: "object data",
}


def name_of(tid: int) -> str:
    return TABLE_NAMES.get(tid, "")


def _hexdump(data: bytes, base: int = 0, limit: int = 0) -> str:
    if limit:
        data = data[:limit]
    lines = []
    for i in range(0, len(data), 16):
        chunk = data[i:i + 16]
        hx = " ".join(f"{b:02x}" for b in chunk)
        asc = "".join(chr(b) if 32 <= b < 127 else "." for b in chunk)
        lines.append(f"  {base + i:08x}: {hx:<48} |{asc}|")
    if limit and len(data) > limit:
        lines.append(f"  ... ({len(data) - limit} more bytes)")
    return "\n".join(lines)


def _int32dump(data: bytes) -> str:
    pad = (-len(data)) % 4
    d = data + b"\x00" * pad
    vals = [int.from_bytes(d[i:i + 4], "little") for i in range(0, len(d), 4)]
    lines = []
    for i, v in enumerate(vals):
        lines.append(f"  [{i:04d}] 0x{v:08x}  {v}")
    return "\n".join(lines)


def cmd_header(oa: OaFile) -> None:
    h = oa.header
    print(f"magic      0x{h.magic:08x}")
    print(f"type id    {h.type_id}")
    print(f"schema rev {h.schema_rev}")
    print(f"toc offset {h.toc_offset}")
    print(f"num alloc  {h.num_alloc} (0x{h.num_alloc:x})   # table directory capacity")
    print(f"num used   {h.num_used} (0x{h.num_used:x})   # table count")
    print(f"file size  {len(oa.data)}")


def cmd_toc(oa: OaFile) -> None:
    print(f"{'#':>3} {'id':>8} {'offset':>12} {'size':>8}  role")
    for i, e in enumerate(oa.entries):
        mark = "DELETED" if e.deleted else ""
        print(f"{i:>3} 0x{e.id:06x} 0x{e.offset:010x} {e.size:>8}  {name_of(e.id)} {mark}")


def cmd_strings(oa: OaFile) -> None:
    if oa.string_table is None:
        print("no string table (0xa)")
        return
    st = oa.string_table
    print(f"byte table: numPages={st.table.num_pages} "
          f"lastPageAlloc={st.table.last_page_alloc} usedSize={st.table.used_size} "
          f"field2={st.table.field2}")
    for ref, (off, s) in enumerate(zip(st.offsets, st.strings)):
        print(f"  [{ref:3d}] +{off:04x} {s!r}")


def _resolve(oa: OaFile, ref: int) -> str:
    s = oa.resolve_string_ref(ref)
    if s is None:
        return ""
    return f'  = "{s}"'


def cmd_table(oa: OaFile, tid: int) -> None:
    data = oa.table_bytes(tid)
    print(f"table 0x{tid:x} ({name_of(tid)}) — {len(data)} bytes")
    print(_hexdump(data))
    print("\n-- as int32 --")
    print(_int32dump(data))


def cmd_packed(oa: OaFile, tid: int, resolve: bool) -> None:
    data = oa.table_bytes(tid)
    print(f"table 0x{tid:x} ({name_of(tid)}) — {len(data)} bytes as packed-UInt4 stream")
    for pos, value, n in scan_packed_uint4(data):
        suffix = _resolve(oa, value) if resolve else ""
        print(f"  +{pos:04x}: {value} (0x{value:x}) [{n}b]{suffix}")


def _mem_tbl_header(data: bytes):
    """Recognize the common member-table header: u32 field0, u32 0xc8000000, u32 count."""
    if len(data) >= 12:
        f0 = struct.unpack_from("<I", data, 0)[0]
        marker = struct.unpack_from("<I", data, 4)[0]
        if marker == 0xC8000000:
            count = struct.unpack_from("<I", data, 8)[0]
            return f0, count
    return None


def _describe(data: bytes, depth: int, indent: str = "") -> None:
    """Recursively describe a table payload (base table -> members -> ...)."""
    pad = indent + "  "
    bt = parse_base_tbl(data)
    if bt is not None:
        print(f"{indent}base table  (num_used={bt.num_used}, toc_off={bt.toc_offset})")
        if bt.header:
            h = ", ".join(f"h[{k}]=0x{v:x}" for k, v in sorted(bt.header.items()))
            print(f"{pad}header: {h}")
        for tid, chunk in sorted(bt.members.items()):
            print(f"{pad}member 0x{tid:x}  ({len(chunk)} bytes)")
            if depth > 0:
                _describe(chunk, depth - 1, pad)
            else:
                print(f"{pad}  ... (recursion limit)")
        return

    mt = _mem_tbl_header(data)
    if mt is not None:
        f0, count = mt
        print(f"{indent}oaMemberTbl  (field0=0x{f0:x}, count={count})")
        rest = data[12:]
        if rest:
            print(f"{pad}data: {rest[:32].hex(' ')}")
        return

    try:
        if looks_like_byte_tbl(data):
            b = parse_byte_table(data)
            print(f"{indent}byte table  (numPages={b.num_pages}, usedSize={b.used_size})")
            preview = b.data[:b.used_size][:32]
            if preview:
                print(f"{pad}data: {preview.hex(' ')}")
            return
    except (ValueError, struct.error):
        pass

    hx = data[:16].hex(" ")
    print(f"{indent}raw {len(data)} bytes: {hx}{"..." if len(data) > 16 else ""}")


def cmd_struct(oa: OaFile, tid: int, depth: int) -> None:
    data = oa.table_bytes(tid)
    print(f"table 0x{tid:x} ({name_of(tid)}) — {len(data)} bytes")
    _describe(data, depth, "")


def cmd_string_refs(oa: OaFile, tid: int) -> None:
    """Scan a table for values that resolve to string-table strings."""
    data = oa.table_bytes(tid)
    print(f"table 0x{tid:x} ({name_of(tid)}) — {len(data)} bytes, resolved string refs:")
    seen = {}
    for width in (1, 2, 4):
        for off in range(0, len(data) - width + 1, width):
            v = int.from_bytes(data[off:off + width], "little")
            s = oa.resolve_string(v)
            if s is not None and s != "":
                seen.setdefault((v, s), []).append(off)
    for (v, s), offs in sorted(seen.items(), key=lambda kv: kv[0][0]):
        locs = ", ".join(f"+{o:#x}" for o in offs[:6])
        more = f" (+{len(offs) - 6} more)" if len(offs) > 6 else ""
        print(f"  0x{v:04x} ({v}) -> {s!r}   @ {locs}{more}")


def main(argv: List[str]) -> int:
    if len(argv) < 1:
        print(__doc__)
        return 2
    path = argv[0]
    args = argv[1:]

    oa = OaFile.open(path)

    if not args:
        cmd_header(oa)
        print()
        cmd_toc(oa)
        print()
        cmd_strings(oa)
        return 0

    sub = args[0]
    if sub == "header":
        cmd_header(oa)
    elif sub in ("toc", "dir"):
        cmd_toc(oa)
    elif sub == "strings":
        cmd_strings(oa)
    elif sub in ("table", "hex"):
        cmd_table(oa, int(args[1], 0))
    elif sub == "packed":
        cmd_packed(oa, int(args[1], 0), resolve=False)
    elif sub == "refs":
        cmd_packed(oa, int(args[1], 0), resolve=True)
    elif sub in ("struct", "tree"):
        depth = 6
        if len(args) > 2:
            depth = int(args[2])
        cmd_struct(oa, int(args[1], 0), depth)
    elif sub in ("strrefs", "srefs"):
        cmd_string_refs(oa, int(args[1], 0))
    else:
        print(f"unknown subcommand {sub!r}")
        print(__doc__)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
