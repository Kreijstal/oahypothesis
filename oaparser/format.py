"""
Core OpenAccess ``.oa`` file-format primitives.

Pure-Python implementation of the on-disk format, with no dependency on any
external runtime.

Implemented here:

* file header         (magic + id + schema + TOC offset + counts)
* table directory     (numUsed x {id, offset, size} u64 triples)
* byte table          (paged byte heap; used by the string table 0xa)
* string table        (0xa = byte table + null-terminated heap)
* packed UInt4 varint (variable-length integer; the encoding of every
                      string / name reference)
"""

from __future__ import annotations

import struct
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

MAGIC = 0x01234567

# Table ids with known meaning.
TABLE_STRING = 0x0A          # string table (byte heap)
TABLE_PROP_LIST = 0x0B       # property list
TABLE_NETLIST = 0x0C         # netlist data
TABLE_MASTER_MAP = 0x07      # master map
TABLE_INSTANCES = 0x105      # component instances
TABLE_EDIT_META = 0x107      # object edit metadata
TABLE_NAME = 0x102           # name table (packed records; absent in small designs)

DELETED_OFFSET = 0xFFFFFFFFFFFFFFFF


# --------------------------------------------------------------------------- #
# packed UInt4 varint
# --------------------------------------------------------------------------- #

def unpack_packed_uint4(buf: bytes, pos: int = 0, width: int = 1) -> Tuple[int, int]:
    """Decode one packed UInt4 value.

    Layout: the value occupies the high bits of a 1..5-byte little-endian
    sequence; the low nibble of the first byte is a 4-bit length tag
    (0/1->1 byte, 2/3->2, 4/5->3, 6/7->4, 8/9->5 bytes). Odd tags are the
    "aligned" variant, where the stored value is the quotient of the real value
    divided by ``width``.

    Returns ``(value, num_bytes_consumed)``.
    """
    if pos < 0 or pos >= len(buf):
        raise ValueError(f"packed UInt4: position {pos} out of range ({len(buf)} bytes)")
    b0 = buf[pos]
    tag = b0 & 0x0F
    if tag > 9:
        raise ValueError(f"packed UInt4: bad tag {tag:#x} at offset {pos:#x}")
    nbytes = ((tag & 0x0E) >> 1) + 1
    if pos + nbytes > len(buf):
        raise ValueError(f"packed UInt4: truncated ({nbytes} bytes needed at {pos:#x})")
    raw = int.from_bytes(buf[pos:pos + nbytes], "little")
    value = raw >> 4
    if tag & 1:                       # aligned variant
        value *= width
    return value, nbytes


def pack_uint4(value: int, width: int = 1) -> bytes:
    """Encode a packed UInt4 value (inverse of :func:`unpack_packed_uint4`)."""
    if value < 0:
        raise ValueError("packed UInt4: negative value")
    aligned = bool(width and value % width == 0)
    v = value // width if (aligned and width) else value
    if v <= 0xF:
        tag = 1 if aligned else 0
        return bytes([(v << 4) | tag])
    if v <= 0xFFF:
        tag = 3 if aligned else 2
        return bytes([((v & 0xF) << 4) | tag, (v >> 4) & 0xFF])
    if v <= 0xFFFFF:
        tag = 5 if aligned else 4
        return bytes([((v & 0xF) << 4) | tag, (v >> 4) & 0xFF, (v >> 12) & 0xFF])
    if v <= 0xFFFFFFF:
        tag = 7 if aligned else 6
        return bytes([((v & 0xF) << 4) | tag, (v >> 4) & 0xFF,
                      (v >> 12) & 0xFF, (v >> 20) & 0xFF])
    tag = 9 if aligned else 8
    return bytes([((v & 0xF) << 4) | tag, (v >> 4) & 0xFF, (v >> 12) & 0xFF,
                  (v >> 20) & 0xFF, (v >> 28) & 0xFF])


def scan_packed_uint4(buf: bytes, width: int = 1) -> List[Tuple[int, int, int]]:
    """Decode a buffer as a stream of packed UInt4 values.

    Returns a list of ``(offset, value, nbytes)``. Stops at the first byte that
    is not a valid packed UInt4 (tag > 9).
    """
    out = []
    pos = 0
    while pos < len(buf):
        b0 = buf[pos]
        tag = b0 & 0x0F
        if tag > 9:
            break
        try:
            value, n = unpack_packed_uint4(buf, pos, width)
        except ValueError:
            break
        out.append((pos, value, n))
        pos += n
    return out


# --------------------------------------------------------------------------- #
# header + table directory
# --------------------------------------------------------------------------- #

@dataclass
class OaHeader:
    """The 24-byte file header."""
    magic: int
    type_id: int
    schema_rev: int
    toc_offset: int
    num_alloc: int
    num_used: int

    @property
    def valid(self) -> bool:
        return self.magic == MAGIC


@dataclass
class TableEntry:
    """One record in the table directory."""
    id: int
    offset: int
    size: int

    @property
    def deleted(self) -> bool:
        return self.offset == DELETED_OFFSET


def _detect_byteorder(data: bytes) -> str:
    """Return '<' or '>' based on the 4-byte swap-check magic."""
    if data[:4] == MAGIC.to_bytes(4, "big"):
        return ">"
    return "<"


def parse_header(data: bytes) -> OaHeader:
    if len(data) < 24:
        raise ValueError(f"file too short for header ({len(data)} bytes)")
    bo = _detect_byteorder(data)
    magic, type_id, schema_rev, toc_offset, num_alloc, num_used = \
        struct.unpack_from(f"{bo}IHHQII", data, 0)
    return OaHeader(magic, type_id, schema_rev, toc_offset, num_alloc, num_used)


def parse_directory(data: bytes, header: OaHeader) -> List[TableEntry]:
    """Parse the table directory: num_used x {u64 id, u64 offset, u64 size}."""
    n = header.num_used
    base = 24
    bo = _detect_byteorder(data)
    if base + 24 * n > len(data):
        raise ValueError(f"directory truncated: need {24 * n} bytes at offset 24")
    ids = struct.unpack_from(f"{bo}{n}Q", data, base)
    offs = struct.unpack_from(f"{bo}{n}Q", data, base + 8 * n)
    sizes = struct.unpack_from(f"{bo}{n}Q", data, base + 16 * n)
    return [TableEntry(i, o, s) for i, o, s in zip(ids, offs, sizes)]


# --------------------------------------------------------------------------- #
# byte table — used by the string table
# --------------------------------------------------------------------------- #

@dataclass
class ByteTable:
    """A paged byte table."""
    info: int
    used_size: int
    field2: int
    page_index: List[int]
    page_size: List[int]
    data: bytes

    @property
    def num_pages(self) -> int:
        return self.info >> 17

    @property
    def last_page_alloc(self) -> int:
        return self.info & 0x1FFFF

    @property
    def num_full_pages(self) -> int:
        return self.used_size >> 17


def parse_byte_table(data: bytes, byteorder: str = "<") -> ByteTable:
    """Decode an byte table serialization (header + paged byte heap)."""
    if len(data) < 20:
        raise ValueError(f"byte table too short ({len(data)} bytes)")
    info, used_size, field2 = struct.unpack_from(f"{byteorder}III", data, 0)
    num_pages = info >> 17
    n_meta = num_pages + 1
    meta_base = 12
    if meta_base + 8 * n_meta > len(data):
        raise ValueError("byte table page metadata truncated")
    page_index = list(struct.unpack_from(f"{byteorder}{n_meta}I", data, meta_base))
    page_size = list(struct.unpack_from(f"{byteorder}{n_meta}I", data, meta_base + 4 * n_meta))
    heap = data[meta_base + 8 * n_meta:]
    return ByteTable(info, used_size, field2, page_index, page_size, heap)


# --------------------------------------------------------------------------- #
# string table
# --------------------------------------------------------------------------- #

@dataclass
class StringTable:
    """The string table (0xa): a byte heap of null-terminated strings."""
    table: ByteTable
    strings: List[str] = field(default_factory=list)
    offsets: List[int] = field(default_factory=list)

    def __post_init__(self):
        self._by_offset = {off: s for off, s in zip(self.offsets, self.strings)}

    def get(self, ref: int) -> Optional[str]:
        """Resolve a string *index* (string reference)."""
        if 0 <= ref < len(self.strings):
            return self.strings[ref]
        return None

    def get_by_offset(self, off: int) -> Optional[str]:
        """Resolve a string *heap byte offset*."""
        return self._by_offset.get(off)

    def get_by_ref_or_offset(self, v: int) -> Optional[str]:
        """Resolve a value that may be an index, or a heap offset, or offset+1.

        Member-table index entries store string references as ``heap_offset + 1``
        (so 0 can mean "no string"). This tries, in order: index, offset+1, offset.
        """
        if v == 0:
            return None
        s = self.get(v)
        if s is not None and v < len(self.strings) and self.offsets[v] == v - 1:
            return s
        s = self.get_by_offset(v - 1)
        if s is not None:
            return s
        return self.get_by_offset(v)


def parse_string_table(data: bytes, byteorder: str = "<") -> StringTable:
    """Decode table 0xa into a StringTable."""
    tbl = parse_byte_table(data, byteorder)
    strings: List[str] = []
    offsets: List[int] = []
    heap = tbl.data[:tbl.used_size]
    pos = 0
    while pos < len(heap):
        end = heap.find(b"\x00", pos)
        if end == -1:
            s = heap[pos:]
            strings.append(s.decode("utf-8", "replace"))
            offsets.append(pos)
            break
        s = heap[pos:end]
        strings.append(s.decode("utf-8", "replace"))
        offsets.append(pos)
        pos = end + 1
    return StringTable(tbl, strings, offsets)


# --------------------------------------------------------------------------- #
# base table — the generic container for object tables
# --------------------------------------------------------------------------- #

@dataclass
class BaseTable:
    """A base-table container.

    On-disk layout (from the base-table writer):

        u32 4                     marker
        [pad to 8]
        u64 toc_off               table-relative offset of the sub-data
        u32 num_alloc
        u32 num_used
        num_used x u64 ids[]       sub-component ids (1..4 = header fields)
        num_used x u64 offsets[]   table-relative; 0xffff.. = deleted slot
        num_used x u64 sizes[]
        [pad]
        sub-data at toc_off: the num_used components, concatenated in order

    Component ids 1, 2, 3, 4 are the table's four u32 header fields;
    every other id is a member table (its own serialized sub-structure).
    """
    marker: int
    toc_offset: int
    num_alloc: int
    num_used: int
    ids: List[int]
    offsets: List[int]
    sizes: List[int]
    header: Dict[int, int] = field(default_factory=dict)   # id(1..4) -> u32 value
    members: Dict[int, bytes] = field(default_factory=dict)  # id -> raw bytes


def parse_base_tbl(data: bytes) -> Optional[BaseTable]:
    """Parse a base-table container. Returns None if ``data`` is not one."""
    if len(data) < 24:
        return None
    marker = struct.unpack_from("<I", data, 0)[0]
    if marker != 4:
        return None
    toc_offset = struct.unpack_from("<Q", data, 8)[0]
    num_alloc = struct.unpack_from("<I", data, 16)[0]
    num_used = struct.unpack_from("<I", data, 20)[0]
    if num_used == 0 or num_used > 100000:
        return None
    if 24 + 24 * num_used > len(data):
        return None
    ids = list(struct.unpack_from(f"<{num_used}Q", data, 24))
    offsets = list(struct.unpack_from(f"<{num_used}Q", data, 24 + 8 * num_used))
    sizes = list(struct.unpack_from(f"<{num_used}Q", data, 24 + 16 * num_used))

    header: Dict[int, int] = {}
    members: Dict[int, bytes] = {}
    for tid, off, size in zip(ids, offsets, sizes):
        if off == DELETED_OFFSET:
            continue
        if off + size > len(data):
            continue
        chunk = data[off:off + size]
        if tid in (1, 2, 3, 4):
            if size >= 4:
                header[tid] = struct.unpack_from("<I", chunk, 0)[0]
        else:
            members[tid] = chunk
    return BaseTable(marker, toc_offset, num_alloc, num_used,
                     ids, offsets, sizes, header, members)


def looks_like_byte_tbl(data: bytes) -> bool:
    """Heuristic: does ``data`` look like an byte table serialization?"""
    if len(data) < 20:
        return False
    info, used_size = struct.unpack_from("<II", data, 0)
    if info >> 17 > 0x10000:      # implausibly many pages
        return False
    if (info & 0x1FFFF) > 0x20000:
        return False
    if used_size > len(data):
        return False
    return True

@dataclass
class OaFile:
    """A parsed .oa database file."""
    path: str
    data: bytes
    header: OaHeader
    entries: List[TableEntry]
    string_table: Optional[StringTable] = None
    byteorder: str = "<"
    _by_id: Dict[int, List[TableEntry]] = field(default_factory=dict)

    @classmethod
    def open(cls, path: str) -> "OaFile":
        with open(path, "rb") as f:
            data = f.read()
        return cls.from_bytes(data, path)

    @classmethod
    def from_bytes(cls, data: bytes, path: str = "<memory>") -> "OaFile":
        header = parse_header(data)
        if not header.valid:
            raise ValueError(f"bad magic 0x{header.magic:08x} (expected 0x{MAGIC:08x})")
        entries = parse_directory(data, header)
        obj = cls(path=path, data=data, header=header, entries=entries,
                  byteorder=_detect_byteorder(data))
        for e in entries:
            obj._by_id.setdefault(e.id, []).append(e)
        # eagerly decode the string table when present
        if TABLE_STRING in obj._by_id:
            obj.string_table = parse_string_table(obj.table_bytes(TABLE_STRING),
                                                  obj.byteorder)
        return obj

    def table_bytes(self, table_id: int, occurrence: int = 0) -> bytes:
        entries = self._by_id.get(table_id, [])
        if not entries:
            raise KeyError(f"table 0x{table_id:x} not present")
        e = entries[occurrence]
        if e.deleted:
            return b""
        return self.data[e.offset:e.offset + e.size]

    def has(self, table_id: int) -> bool:
        return table_id in self._by_id

    def resolve_string_ref(self, ref: int) -> Optional[str]:
        if self.string_table is None:
            return None
        return self.string_table.get(ref)

    def resolve_string(self, v: int) -> Optional[str]:
        """Resolve a raw value (index, heap offset, or offset+1) to a string."""
        if self.string_table is None:
            return None
        return self.string_table.get_by_ref_or_offset(v)

    def strings(self) -> List[str]:
        return self.string_table.strings if self.string_table else []
