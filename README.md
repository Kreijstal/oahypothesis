# oaparser

A pure-Python parser for the **Cadence OpenAccess (`.oa`) binary database format**
used by Virtuoso and other custom-IC design tools.

The parser reads the on-disk format directly — file header, table directory,
string table, and object tables — with no dependency on the OpenAccess runtime.

## Key structures

The `.oa` file is a database made of a header plus a table directory, followed by
typed tables. The header is:

```
0x00 u32 0x01234567   magic
0x04 u16 id
0x06 u16 schema revision
0x08 u64 TOC offset
0x10 u32 TOC field 0
0x14 u32 table count
```

followed by `count` × `(u64 id, u64 offset, u64 size)` directory entries.

## Layout

```
oaparser/format.py    format primitives (header, directory, string/byte tables,
                      base-table containers, packed-UInt4 varint, byte order)
tools/oadump.py       format-accurate CLI dumper
tools/oa_scan.py      batch inventory over a directory tree
tools/render_symbol.py  render a library symbol to SVG
tests/test_format.py  format tests
```

## Quick start

```sh
python3 tools/oadump.py files/rc/sch_old.oa               # header + directory + strings
python3 tools/oadump.py files/rc/sch_old.oa toc           # table directory
python3 tools/oadump.py files/rc/sch_old.oa strings       # decoded string table
python3 tools/oadump.py files/rc/sch_old.oa struct 0x107  # recursive object-table decode
python3 tools/oadump.py files/rc/sch_old.oa strrefs 0x105 # resolved string references

python3 tools/oa_scan.py /path/to/oa/files                # inventory summary
python3 tools/render_symbol.py path/to/symbol.oa          # -> symbol.oa.svg
```
