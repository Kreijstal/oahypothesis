"""Tests for oaparser.format — the format-accurate .oa primitives."""

import os
import struct

from oaparser.format import (
    MAGIC, OaFile, pack_uint4, unpack_packed_uint4,
    parse_base_tbl, parse_byte_table, parse_string_table, scan_packed_uint4,
)

HERE = os.path.dirname(os.path.abspath(__file__))
SCH_OLD = os.path.join(HERE, "..", "files", "rc", "sch_old.oa")


def test_packed_uint4_roundtrip():
    for width in (1, 2, 4):
        for v in (0, 1, 15, 16, 255, 256, 4095, 4096,
                  0xFFFFF, 0x100000, 0xFFFFFFF, 0x10000000, 0xFFFFFFFF):
            b = pack_uint4(v, width)
            got, n = unpack_packed_uint4(b, 0, width)
            assert got == v and n == len(b)


def test_packed_uint4_known_encodings():
    # width=1 -> every value is "aligned" (odd tags)
    assert pack_uint4(0, 1) == b"\x01"
    assert pack_uint4(15, 1) == b"\xf1"
    # width=2 -> aligned only when even
    assert pack_uint4(1, 2) == b"\x10"   # odd, tag 0
    assert pack_uint4(2, 2) == b"\x11"   # even, tag 1, stored 1
    # and decode back
    assert unpack_packed_uint4(b"\x10", 0, 2) == (1, 1)
    assert unpack_packed_uint4(b"\x11", 0, 2) == (2, 1)


def test_packed_uint4_stream_stops_at_bad_tag():
    buf = bytes([0x0A])  # tag 10 > 9 -> invalid
    assert scan_packed_uint4(buf) == []


def test_sch_old_header():
    oa = OaFile.open(SCH_OLD)
    assert oa.header.magic == MAGIC
    assert oa.header.num_used == 33
    assert oa.header.schema_rev == 99


def test_sch_old_directory():
    oa = OaFile.open(SCH_OLD)
    ids = [e.id for e in oa.entries]
    assert ids[0] == 0x1
    assert 0x0A in ids and 0x0B in ids and 0x0C in ids and 0x107 in ids
    # deleted slot marker
    assert any(e.deleted for e in oa.entries)


def test_sch_old_string_table():
    oa = OaFile.open(SCH_OLD)
    strs = oa.strings()
    assert strs[0] == "simple"
    assert "R0" in strs and "V0" in strs and "analogLib" in strs
    # string refs resolve by index
    assert oa.resolve_string_ref(0) == "simple"
    assert oa.resolve_string_ref(strs.index("R0")) == "R0"


def test_byte_table_header():
    oa = OaFile.open(SCH_OLD)
    bt = oa.string_table.table
    assert bt.num_pages == 0
    assert bt.used_size == 922
    assert bt.last_page_alloc == 1024


def test_parse_string_table_direct():
    oa = OaFile.open(SCH_OLD)
    raw = oa.table_bytes(0x0A)
    st = parse_string_table(raw)
    assert st.strings[0] == "simple"
    assert len(st.strings) > 10


def test_object_tables_are_base_tables():
    """Object tables decode as base table containers (marker=4 + sub-TOC)."""
    oa = OaFile.open(SCH_OLD)
    for tid in (0x0B, 0x0C, 0x105, 0x107, 0x10C, 0x132, 0x133):
        bt = parse_base_tbl(oa.table_bytes(tid))
        assert bt is not None, f"0x{tid:x} should be a base table"
        assert bt.marker == 4
        assert bt.num_used >= 1
        # header fields 2 and 3 (counts) are present and equal-ish
        assert 2 in bt.header and 3 in bt.header
        # every table has at least one member sub-table (id >= 0x100)
        assert any(t >= 0x100 for t in bt.members)


def test_base_table_deleted_slots_are_skipped():
    oa = OaFile.open(SCH_OLD)
    bt = parse_base_tbl(oa.table_bytes(0x0D))
    assert bt is not None
    # entries 12..15 of 0xd are deleted (offset = 0xffff..); parser skips them
    assert len(bt.members) + len(bt.header) <= bt.num_used


def test_string_refs_are_heap_offset_plus_one():
    """Member-table index entries reference strings as heap_offset + 1."""
    oa = OaFile.open(SCH_OLD)
    # In table 0xc (netlist data), the value 0x00da (218) is 'vdc' at heap 217.
    assert oa.resolve_string(0x00DA) == "vdc"
    # 0x012f (303) -> 'instance#' at heap 302
    assert oa.resolve_string(0x012F) == "instance#"
    # 0x02ae (686) -> 'masterChangeCount' at heap 685
    assert oa.resolve_string(0x02AE) == "masterChangeCount"
    # component instance table 0x105 references library cell symbols
    tbl = oa.table_bytes(0x105)
    vals = [int.from_bytes(tbl[i:i + 2], "little")
            for i in range(0, len(tbl) - 1, 2)]
    resolved = {oa.resolve_string(v) for v in vals}
    assert "analogLib.vdc.symbol" in resolved
    assert "analogLib.res.symbol" in resolved


def test_big_endian_files_parse():
    """A big-endian .oa (magic bytes 01 23 45 67) parses correctly."""
    # synthesize a minimal big-endian file: header + 1-entry directory
    n = 1
    header = struct.pack(">IHHQII", MAGIC, 0, 99, 0, 1, n)
    toc = struct.pack(">QQQ", 0x0A, 24 + 24 * n, 64)  # one string-table entry
    body = b"\x00" * 64
    data = header + toc + body
    oa = OaFile.from_bytes(data)
    assert oa.byteorder == ">"
    assert oa.header.magic == MAGIC
    assert oa.header.num_used == 1
    assert oa.has(0x0A)
    assert oa.table_bytes(0x0A)[:4] == b"\x00\x00\x00\x00"
