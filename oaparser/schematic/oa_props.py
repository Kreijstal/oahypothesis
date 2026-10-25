#!/usr/bin/env python3
"""oa_props.py -- decode object property records (strings) from the bytes.

Table 0x000c holds the property table:
  member 0x0002  member-slot count (8, constant here)
  member 0x0003  number of properties
  member 0x0301  property name, one byte per property = string heap offset + 1
  member 0x0302  type per property (1 = string)
  member 0x0304  property value, one byte per property = string heap offset + 1

The value column is subject to this writer's usual truncation, and non-string
values (ints, floats) do not appear there at all, so only string properties are
reported; the rest come back with value None.

    python3 oa_props.py synth/trans/schematic/sch.oa
"""
import struct
import sys

from oaparser.format import OaFile, parse_base_tbl

PROP_TABLE = 0x000C
SENTINEL = b"\x00\x00\x00\xc0"


def column(seg, members, mid, n):
    if mid not in members:
        return []
    o, s = members[mid]
    body = seg[o:o + s]
    cut = body.find(SENTINEL)
    return list(body[:cut] if cut >= 0 else body)[:n]


def decode(path):
    oa = OaFile.open(path)
    if not oa.has(PROP_TABLE):
        return []
    seg = oa.table_bytes(PROP_TABLE)
    bt = parse_base_tbl(seg)
    if not bt:
        return []
    members = {i: (o, s) for i, o, s in zip(bt.ids, bt.offsets, bt.sizes)}
    if 0x0003 not in members:
        return []
    n = struct.unpack_from("<i", seg, members[0x0003][0])[0]
    if not n:
        return []
    st = oa.string_table
    names = column(seg, members, 0x0301, n)
    values = column(seg, members, 0x0304, n)
    types = column(seg, members, 0x0302, n)

    offsets = set(st.offsets) if st else set()

    def resolve(v):
        if not v:
            return None
        return st.get_by_offset(v - 1) if st else None

    out = []
    for k in range(n):
        v = values[k] if k < len(values) else 0
        as_string = resolve(v) if (v - 1) in offsets else None
        out.append({
            "name": resolve(names[k]) if k < len(names) else None,
            "raw": v,
            "string": as_string,
            "int": v,
            # the file does not record the type: a value that resolves to a
            # string heap offset may still be a small integer (e.g. m = 7
            # collides with a string at offset 6)
            "ambiguous": as_string is not None and v < 256,
            "type_code": types[k] if k < len(types) else None,
        })
    return out


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    path = args[0] if args else "synth/trans/schematic/sch.oa"
    props = decode(path)
    print(f"{path}: {len(props)} propert(ies)")
    for p in props:
        note = ""
        if p["ambiguous"]:
            note = f"  [untyped: string {p['string']!r} or int {p['int']}]"
        elif p["string"] is not None:
            note = f"  (string {p['string']!r})"
        print(f"   {str(p['name']):10s} raw={p['raw']:<5d} int={p['int']:<5d}{note}")


if __name__ == "__main__":
    main()


def instance_properties(path):
    """Per-instance property values from table 0x000c.

    Layout (verified on rfLib/ten_plexer against SKILL):
        0x0300  property names, u16 string refs from offset len-2*P
        0x0301  instance index per property (1-based), bytes from len-P
        0x030c  property values, u16 string refs at 204 + 2*k
    with P = number of properties, and `names[k]` belonging to instance
    `idx[k+2]`.
    """
    from . import oa_shapes
    from oaparser.format import OaFile
    oa = OaFile.open(path)
    st = oa.string_table
    m = oa_shapes.members(oa, 0x000C)
    if not (0x0300 in m and 0x0301 in m and 0x030C in m):
        return {}
    a3, a1, ac = m[0x0300], m[0x0301], m[0x030C]
    P = min(len(a1) - 12, (len(a3) - 16) // 2)
    if P <= 0:
        return {}

    def s(v):
        if not v:
            return None
        try:
            return st.get_by_offset(v - 1)
        except Exception:
            return None

    names = [struct.unpack_from("<H", a3, len(a3) - 2 * P + 2 * k)[0]
             for k in range(P)]
    idx = list(a1[len(a1) - P:])
    out = {}
    for k in range(P):
        j = k + 2
        if j >= P:
            break
        name = s(names[k])
        pos = 204 + 2 * k
        value = None
        if pos + 2 <= len(ac):
            value = s(struct.unpack_from("<H", ac, pos)[0])
        if name:
            out.setdefault(idx[j], {})[name] = value
    return out


def property_arrays(path):
    """Find the property NAME and VALUE arrays in table 0x000c by content.

    Member ids are NOT stable across cellviews (a 2-property cell puts names in
    0x0301 and values in 0x0304, while ideal_balun uses 0x0300 / 0x0312), so the
    arrays are identified by what they contain: a run of string references that
    all resolve in the heap.  Ref width follows the heap size (1 byte when every
    offset fits in 255, else 2).
    """
    from . import oa_shapes
    from oaparser.format import OaFile
    oa = OaFile.open(path)
    st = oa.string_table
    offs = set(st.offsets)
    m = oa_shapes.members(oa, 0x000C)
    cands = []
    for mid, mem in m.items():
        if mid < 0x300 or len(mem) < 2:
            continue
        for w in (1, 2):
            n = min(len(mem) // w, 600)
            vals = [int.from_bytes(mem[i * w:(i + 1) * w], "little")
                    for i in range(n)]
            run = []
            for v in vals:
                if v and (v - 1) in offs:
                    run.append(v)
                else:
                    break
            if len(run) >= 2:
                strs = [st.get_by_offset(v - 1) for v in run]
                cands.append((mid, w, run, strs))
    return cands


def simple_properties(path):
    """[(name, value)] for cellviews whose property arrays are unambiguous.

    Returns [] when the cellview mixes string and numeric values (the numeric
    ones live in a separate u32 array whose type tag is not decoded), so callers
    never get a wrong pairing.
    """
    cands = property_arrays(path)
    if not cands:
        return []
    # drop arrays that repeat a single string (cell-name noise); a properties
    # array always has at least two distinct entries in the cells examined
    uniq = [c for c in cands if len(set(c[3])) > 1]
    if len(uniq) != 2:
        return []
    a, b = sorted(uniq, key=lambda c: c[0])
    if len(a[3]) != len(b[3]):
        return []
    # The name array always carries the lower member id in every cellview
    # examined: pt/s1 and pt/s2 name 0x0301 < value 0x0304, ideal_balun name
    # 0x0300 < value 0x0312.
    return list(zip(a[3], b[3]))


def tail_values(path):
    """Decode the property VALUE section that ends table 0x000c.

    Layout (verified on pt/s1, pt/s2, pt3/u1..u3):

        [8][count][0][-1][0xC0000000][1][values...][0]

    The values are packed at the narrowest width that fits (1 byte for small
    string refs, 4 for numbers) and the region is padded to a multiple of 8.
    """
    from . import oa_shapes
    from oaparser.format import OaFile
    oa = OaFile.open(path)
    st = oa.string_table
    offs = set(st.offsets)
    tbl = oa.table_bytes(0x000C)
    sent = oa_shapes.SENTINEL
    s = tbl.rfind(sent)
    if s < 20:
        return []
    count = struct.unpack_from("<I", tbl, s - 12)[0]
    if not (0 < count < 400):
        return []
    # A u32 == 1 right after the sentinel marks 1-byte string refs; without it
    # the values are u32 (numbers).
    narrow = struct.unpack_from("<I", tbl, s + 4)[0] == 1
    body = tbl[s + (8 if narrow else 4):]
    body = body[:-4] if len(body) >= 4 else body      # trailing terminator
    region = len(body)
    if narrow:
        vals = list(body[:count])
        strs = [st.get_by_offset(v - 1) if v and (v - 1) in offs else None
                for v in vals]
        if all(x is not None for x in strs):
            return strs
    for w in (1, 2, 4):
        need = count * w
        if need > region or region - need >= 8:
            continue
        vals = [int.from_bytes(body[i * w:(i + 1) * w], "little")
                for i in range(count)]
        strs = [st.get_by_offset(v - 1) if v and (v - 1) in offs else None
                for v in vals]
        if all(x is not None for x in strs):
            return strs
    # fall back to numbers at the widest width that fits
    for w in (4, 2, 1):
        if count * w <= region and region - count * w < 8:
            return [int.from_bytes(body[i * w:(i + 1) * w], "little")
                    for i in range(count)]
    return []


