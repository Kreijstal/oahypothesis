#!/usr/bin/env python3
"""oa_instances.py -- decode schematic instance placement straight from the bytes.

Fields were located by one-field variant cells (build_instvariants.il) and are
verified here against the SKILL oracle:

  count     table 0x0107, member 0x0003 (int32)
  origins   table 0x0107, member 0x0301: int32 header, 0xC0000000, then
            N x (i32 x, i32 y) in DBU (160 per user unit). NOTE: this writer
            drops the final int32, so the last origin can be short.
  orient    table 0x0107, member 0x0103, a column of u16:
            0x0001 R0, 0x0011 R90, 0x0021 R180, 0x0031 R270,
            0x0041 MY, 0x0061 MX, 0x0051 MYR90, 0x0071 MXR90
            (+0x10 per quarter turn, +0x40 mirror)
  master    a width-free column whose values are string heap offsets + 1 and
            whose strings look like "lib.cell.view"; found by scanning tables.

    python3 oa_instances.py synth/orients/schematic/sch.oa
"""
import struct
import sys

from oaparser.format import OaFile, parse_base_tbl

INST_TABLE = 0x0107
ORIENT = {0x01: "R0", 0x11: "R90", 0x21: "R180", 0x31: "R270",
          0x41: "MY", 0x61: "MX", 0x51: "MYR90", 0x71: "MXR90"}
SENTINEL_INT = -1073741824
DBU = 160.0
SENTINEL = b"\x00\x00\x00\xc0"


def members(oa, tid):
    if not oa.has(tid):
        return {}
    data = oa.table_bytes(tid)
    bt = parse_base_tbl(data)
    if not bt:
        return {}
    return {i: data[o:o + s] for i, o, s in zip(bt.ids, bt.offsets, bt.sizes)}


def _bo(oa):
    """Byte order of the cellview ('<' or '>')."""
    return getattr(oa, "byteorder", "<")


def inst_count(oa):
    m = members(oa, INST_TABLE)
    for mid in (0x0003, 0x0002):
        if mid in m and len(m[mid]) >= 4:
            return struct.unpack_from(f"{_bo(oa)}i", m[mid], 0)[0]
    return 0


def origins(oa, n):
    """Instance origins (x, y) in user units, in DBU in the file.

    The column lives in member 0x0301 (after its marker) and continues
    contiguously into the next record when it overflows, so it is read as one
    run of int32s, skipping any 0xC0000000 section markers.
    """
    m = members(oa, INST_TABLE)
    m0301 = m.get(0x0301)
    if not m0301:
        return []
    cut = m0301.find(SENTINEL)
    body = m0301[cut + 4:] if cut >= 0 else m0301
    table = oa.table_bytes(INST_TABLE)
    at = table.find(body)
    vals = []
    pos = at if at >= 0 else 0
    while len(vals) < 2 * n and pos + 4 <= len(table):
        v = struct.unpack_from(f"{_bo(oa)}i", table, pos)[0]
        pos += 4
        if v == SENTINEL_INT:            # section marker inside the run
            continue
        vals.append(v)
    out = [(vals[k] / DBU, vals[k + 1] / DBU) for k in range(0, len(vals) - 1, 2)]
    if len(vals) % 2:                    # a genuinely truncated final y
        out.append((vals[-1] / DBU, None))
    while len(out) < n:
        out.append((None, None))
    return out


def orients(oa, n):
    m = members(oa, INST_TABLE)
    m0103 = m.get(0x0103)
    if not m0103:
        return []
    for start in range(0, min(len(m0103), 256)):
        if start + 2 * n > len(m0103):
            break
        seq = [struct.unpack_from(f"{_bo(oa)}H", m0103, start + 2 * k)[0] for k in range(n)]
        codes = [v & 0xFF for v in seq]          # high byte carries flags
        if all(c in ORIENT for c in codes):
            return [ORIENT[c] for c in codes]
    return []


def master_map(oa):
    """Master strings, one per unique master, in map order.

    Refs are ``heap offset + 1`` and are stored one byte wide while the offsets
    stay under 256, two bytes wide above that. They live in table 0x0105, and a
    large map is split across members (observed: 0x0403 holds the leading
    entries, 0x0400 the trailing one).
    """
    st = oa.string_table
    if st is None:
        return []
    ms = members(oa, 0x0105)
    out = []
    for mid in (0x0403, 0x0400):
        seg = ms.get(mid)
        if not seg:
            continue
        taken = None
        for width, fmt in ((2, "<H"), (1, "<B")):
            for start_at in (12, 8, 4, 0):
                if start_at + width > len(seg):
                    continue
                vals, k = [], start_at
                while k + width <= len(seg):
                    v = struct.unpack_from(fmt, seg, k)[0]
                    name = st.get_by_offset(v - 1) if v >= 1 else None
                    if not name or name.count(".") != 2:
                        break
                    vals.append(name)
                    k += width
                if len(vals) > (len(taken) if taken else 0):
                    taken = vals
        if taken:
            out.extend(taken)
    return out


def master_indices(oa, n):
    """table 0x0107 member 0x0300: one 1-based index per instance.

    The member starts with a marker then a count, and this writer drops the
    final byte, so fewer than n indices may be present.
    """
    m = members(oa, INST_TABLE)
    idx = []
    seg = m.get(0x0300)
    if seg:
        marker = seg.find(SENTINEL)
        body = seg[marker + 8:] if marker >= 0 else seg[8:]
        idx = list(body[:n])
    # The array spills into the leading bytes of member 0x0301 when it needs
    # more room (verified: balun has 7 instances, 0x0300 holds [1,2,2,2] and
    # 0x0301 begins [2,3,3] -> gnd, iopin x4, xfmr x2, matching the oracle).
    if len(idx) < n:
        seg1 = m.get(0x0301)
        if seg1:
            marker = seg1.find(SENTINEL)
            head = seg1[:marker] if marker > 0 else b""
            idx += list(head[:n - len(idx)])
    return idx[:n]


def decode(path):
    oa = OaFile.open(path)
    n = inst_count(oa)
    if not n:
        return []
    org = origins(oa, n)
    ori = orients(oa, n)
    idx = master_indices(oa, n)
    mmap = master_map(oa)
    out = []
    for k in range(n):
        out.append({
            # NOTE: the real instance name lives in the file but its table is
            # not decoded yet; this placeholder must not be used as a value.
            "name": f"I{k}",
            "name_is_synthetic": True,
            "master": (mmap[idx[k] - 1] if k < len(idx) and 1 <= idx[k] <= len(mmap) else None),
            "master_index": idx[k] if k < len(idx) else None,
            "x": org[k][0], "y": org[k][1],
            "orient": ori[k] if k < len(ori) else None,
        })
    return out


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    path = args[0] if args else "synth/orients/schematic/sch.oa"
    insts = decode(path)
    print(f"{path}: {len(insts)} instance(s) decoded from bytes")
    for i in insts:
        x = "?" if i["x"] is None else f"{i['x']:g}"
        y = "?" if i["y"] is None else f"{i['y']:g}"
        print(f"   {i['name']:3s} {str(i['master']):24s} at ({x},{y}) {i['orient']}")


if __name__ == "__main__":
    main()


def instance_names(oa, insts, terminals_by_master=None):
    """Real instance names, decoded by replaying the writer's string order.

    Per instance, in order, the writer emits:
        1. the instance name
        2. its master block on first use: lib.cell.view, then view, cell, lib
        3. its property name/value pairs
        4. its master's terminal names
    and the string table is de-duplicated, so repeats add nothing.  The first
    instance's name is the string immediately before its master spec.

    Verified against SKILL on analogLib/ideal_balun:
    I2, PIN3, PIN2, PIN0, PIN1, K1, K0.
    """
    import re
    st = getattr(oa, "string_table", None)
    if st is None or not insts:
        return {}
    seq = [st.get_by_offset(o) for o in st.offsets]
    term_map = terminals_by_master or {}
    seen, out, used = set(), {}, set()

    def advance(p):
        while p < len(seq) and seq[p] in seen:
            p += 1
        return p

    def block(p, spec):
        parts = spec.split(".")[::-1]
        if p < len(seq) and seq[p] == spec:
            seen.add(spec)
            p += 1
        for part in parts:
            if part not in seen and p < len(seq) and seq[p] == part:
                seen.add(part)
                p += 1
        return p

    def tail(p, spec):
        terms = term_map.get(spec) or []
        if not terms:
            return p
        while p < len(seq) and seq[p] not in seen and seq[p] not in terms:
            seen.add(seq[p])
            p += 1
        for _ in terms:
            p = advance(p)
            if p < len(seq) and seq[p] in terms:
                seen.add(seq[p])
                p += 1
        return p

    spec0 = insts[0].get("master")
    if not spec0 or spec0 not in seq:
        return {}
    k = seq.index(spec0)
    out[insts[0].get("name")] = seq[k - 1]
    used.add(spec0)
    pos = tail(block(k, spec0), spec0)

    for inst in insts[1:]:
        pos = advance(pos)
        if pos >= len(seq):
            break
        out[inst.get("name")] = seq[pos]
        pos += 1
        spec = inst.get("master") or ""
        if spec and spec not in used:
            used.add(spec)
            pos = tail(block(pos, spec), spec)
    return out
