#!/usr/bin/env python3
"""oa_shapes.py -- decode schematic figures (bbox + class) straight from bytes.

  bbox   table 0x010f member 0x0304: int32 header, 0xC0000000, then N x
         (i32 x1, i32 y1, i32 x2, i32 y2) in DBU (160/user unit).
         This writer drops the final int32.
  class  table 0x010f member 0x0103, at byte offset 16: one u16 per figure.
         4 = line, 8 = rect, 7 = polygon  (verified by single-shape cells and
         the five-figure cell, which reads 4,4,4,8,7)

Vertex lists for polygons are packed uint4 varints in the tail of member 0x030c;
their values scale exactly with the geometry but the mapping to (x,y) is not yet
decoded, so polygons are reported with their bbox only.

    python3 oa_shapes.py synth/shapes/schematic/sch.oa
"""
import struct
import sys

from oaparser.format import OaFile, parse_base_tbl, unpack_packed_uint4

SHAPE_TABLE = 0x010F
DBU = 160.0
SENTINEL = b"\x00\x00\x00\xc0"
# low nibble -> kind; verified against the SKILL oracle on vendor symbols
# low nibble -> kind; verified against SKILL on gnd (10,7,4,8,0x68 -> label,
# polygon, line, rect, rect) and xfmr (0x08 body rect, 10 x8 = the 8 labels,
# 4 x14 lines, 3 x4 ellipse, 0 x8 = the 8 arcs, 0x68 x4 rects).
CLASS = {0: "arc", 3: "ellipse", 4: "line", 7: "polygon", 8: "rect",
         10: "label", 12: "textDisplay"}
FLAGS = {0x20: "connectivity", 0x2000: "instance-owned"}
CLASS_OFFSET = 16


def _bo(oa):
    """The cellview's byte order: '<' (little) or '>' (big)."""
    return getattr(oa, "byteorder", "<")


def _sent(oa):
    """The section sentinel in this file's byte order."""
    return SENTINEL if _bo(oa) == "<" else b"\xc0\x00\x00\x00"


def members(oa, tid):
    if not oa.has(tid):
        return {}
    data = oa.table_bytes(tid)
    bt = parse_base_tbl(data)
    if not bt:
        return {}
    return {i: data[o:o + s] for i, o, s in zip(bt.ids, bt.offsets, bt.sizes)}


def count(oa):
    m = members(oa, SHAPE_TABLE)
    for mid in (0x0003, 0x0002):
        if mid in m and len(m[mid]) >= 4:
            return struct.unpack_from(f"{_bo(oa)}i", m[mid], 0)[0]
    return 0


def bboxes(oa, n):
    seg = members(oa, SHAPE_TABLE).get(0x0304)
    if not seg:
        return []
    start = seg.find(_sent(oa))
    body = seg[start + 4:] if start >= 0 else seg
    vals = [struct.unpack_from(f"{_bo(oa)}i", body, k)[0] for k in range(0, len(body) - 3, 4)]
    out = []
    k = 0
    while k < len(vals):
        group = vals[k:k + 4]
        group = [v / DBU for v in group] + [None] * (4 - len(group))
        out.append(list(group))
        k += 4
    # This writer drops the very last bbox value of the table (a known quirk).
    # It is always the last shape's y2; a pin/rect marker there is square, so
    # recover it from the width rather than silently rendering a sliver.
    if out and out[-1][3] is None:
        x1, y1, x2 = out[-1][0], out[-1][1], out[-1][2]
        if None not in (x1, y1, x2):
            out[-1][3] = y1 + (x2 - x1)
    return [tuple(b) for b in out]


def classes(oa, n):
    seg = members(oa, SHAPE_TABLE).get(0x0103)
    if not seg or len(seg) < CLASS_OFFSET + 2 * n:
        return []
    out = []
    for k in range(n):
        raw = struct.unpack_from(f"{_bo(oa)}H", seg, CLASS_OFFSET + 2 * k)[0]
        out.append(CLASS.get(raw & 0x0F, f"0x{raw:x}"))   # low nibble is the class
    return out


VERT_LEN_OFFSET = 212
VERT_DATA_OFFSET = 228


def _unzig(v):
    return -(v // 2) if v % 2 else v // 2


def polygon_points(oa, corner=None):
    """Vertex list for a polygon, from the packed data in member 0x030c.

    The run is a packed-uint4 stream of zigzag values.  The first pair is the
    FIRST VERTEX ITSELF, in DBU, relative to the cell origin (not to the bbox
    corner - pA/gnd/res disprove the corner rule).  Every later pair is a
    delta from the previous vertex.  Values are in DBU (160 per user unit).

    Verified against the SKILL oracle:
      gnd  [21,61,40,0,21,21] -> (-0.0625,-0.1875) (0.0625,-0.1875) (0,-0.25)
      pA   [0,0,320,0,321,320] -> (0,0) (1,0) (0,1)
    """
    seg = members(oa, SHAPE_TABLE).get(0x030C)
    if not seg or len(seg) < VERT_DATA_OFFSET + 2:
        return []
    vlen = struct.unpack_from(f"{_bo(oa)}i", seg, VERT_LEN_OFFSET)[0]
    if not 0 < vlen <= len(seg) - VERT_DATA_OFFSET:
        return []
    data = seg[VERT_DATA_OFFSET:VERT_DATA_OFFSET + vlen]
    vals, pos = [], 0
    # Point coordinates use the "aligned" packed variant with a width of 100:
    # synth/shapes stores x=800 DBU as tag-3 value 16 (16*100), and the same
    # width leaves pA..pD and gnd unchanged (their odd-tag values are 0).
    while pos < len(data):
        try:
            v, n = unpack_packed_uint4(data, pos, 100)
        except Exception:
            break
        vals.append(v)
        pos += n
    if len(vals) < 2:
        return []
    pts = [(_unzig(vals[0]) / DBU, _unzig(vals[1]) / DBU)]
    for i in range(2, len(vals) - 1, 2):
        x, y = pts[-1]
        pts.append((x + _unzig(vals[i]) / DBU, y + _unzig(vals[i + 1]) / DBU))
    return pts


def arc_geometry(oa, n=None):
    """Defining ellipses and sweep angles for every arc, from member 0x0306.

    Layout (verified against SKILL on xfmr and on purpose-built test cells):
      marker, then 4 int32 DBU per arc: the defining ellipse box (x1,y1,x2,y2)
      marker, then one double per arc: start angle in radians
      marker, then one double per arc: end angle in radians (last one may be
      truncated by the writer, in which case it is None)

    Cross-checked: xfmr box (-21,-38)-(-13,-30) -> centre (-17,-34) r=4 with
    angles 3pi/2 .. 1.823476 gives bbox (-18,-38)-(-13,30*), identical to the
    SKILL bbox of that arc.
    """
    seg = members(oa, SHAPE_TABLE).get(0x0306)
    if not seg:
        return []
    bo = _bo(oa)
    if n:
        # Fixed layout: [marker][4*n int32 boxes][marker][n doubles][marker]
        # [n doubles].  Scanning for every sentinel is unreliable because a
        # double's bytes can contain the sentinel sequence, which split the
        # start section and produced bogus arcs (analogLib/port).
        m0 = seg.find(_sent(oa))
        if m0 < 0:
            return []
        base = m0 + 4
        boxes = [list(struct.unpack_from(f"{bo}4i", seg, base + 16 * k))
                 for k in range(n)]
        starts_at = base + 16 * n + 4
        ends_at = starts_at + 8 * n + 4
        starts = [struct.unpack_from(f"{bo}d", seg, starts_at + 8 * k)[0]
                  if starts_at + 8 * k + 8 <= len(seg) else None
                  for k in range(n)]
        ends = [struct.unpack_from(f"{bo}d", seg, ends_at + 8 * k)[0]
                if ends_at + 8 * k + 8 <= len(seg) else None
                for k in range(n)]
        return [[tuple(v / DBU for v in b), starts[k], ends[k]]
                for k, b in enumerate(boxes)]
    marks = [i for i in range(len(seg) - 3) if seg[i:i + 4] == _sent(oa)]
    if len(marks) < 3:
        return []
    m_box, m_start, m_end = marks[0], marks[1], marks[2]
    ints = []
    for k in range(m_box + 4, m_start - 3, 4):
        ints.append(struct.unpack_from(f"{_bo(oa)}i", seg, k)[0])
    boxes = [ints[i:i + 4] for i in range(0, len(ints) - 3, 4)]
    n = len(boxes)
    starts, ends = [], []
    for k in range(m_start + 4, m_end - 7, 8):
        starts.append(struct.unpack_from(f"{_bo(oa)}d", seg, k)[0])
    for k in range(m_end + 4, len(seg) - 7, 8):
        ends.append(struct.unpack_from(f"{_bo(oa)}d", seg, k)[0])
    out = []
    for i, b in enumerate(boxes):
        st = starts[i] if i < len(starts) else None
        en = ends[i] if i < len(ends) else None
        out.append([tuple(v / DBU for v in b), st, en])
    # The writer drops the final end angle.  The start/end pairing is fixed
    # within a cell (e.g. xfmr: 3pi/2 -> 0.5804pi, pi/2 -> pi), so recover a
    # missing end angle from any arc that shares the same start angle rather
    # than leaving a gap in the coil.
    for a in out:
        if a[2] is None and a[1] is not None:
            for b in out:
                if b[1] is not None and b[2] is not None and abs(a[1] - b[1]) < 1e-6:
                    a[2] = b[2]
                    break
    return [tuple(a) for a in out]


def arc_boxes(oa):
    """Defining (circle) boxes for arcs: table 0x010f member 0x0306.

    Each arc contributes a marker 0xC0000000 followed by four int32 DBU
    coordinates.  Verified on purpose-built arc cells: a radius-1 arc stores
    (-160,-160,160,160), a radius-2 arc (-320,-320,320,320).
    """
    seg = members(oa, SHAPE_TABLE).get(0x0306)
    if not seg:
        return []
    out, i = [], 0
    while True:
        i = seg.find(_sent(oa), i)
        if i < 0 or i + 20 > len(seg):
            break
        try:
            x1, y1, x2, y2 = struct.unpack_from(f"{_bo(oa)}4i", seg, i + 4)
        except struct.error:
            break
        if all(abs(v) < 10 ** 6 for v in (x1, y1, x2, y2)):
            out.append((x1 / DBU, y1 / DBU, x2 / DBU, y2 / DBU))
        i += 4
    return out


_DECODE_CACHE = {}


def decode(path):
    """Decode a cellview's shapes, cached by path.

    A schematic with 90 instances of the same symbol used to re-decode that
    symbol 90 times; with the bbox-based arc solver that is expensive, so the
    result is memoised.  Callers must not mutate the returned list.
    """
    key = str(path)
    hit = _DECODE_CACHE.get(key)
    if hit is not None:
        return hit
    res = _decode_uncached(path)
    _DECODE_CACHE[key] = res
    return res


def _decode_uncached(path):
    oa = OaFile.open(path)
    n = count(oa)
    bb = bboxes(oa, n)
    cl = classes(oa, n)
    arcs = arc_boxes(oa)
    out, arc_i = [], 0
    for k in range(n):
        cls = cl[k] if k < len(cl) else None
        box = bb[k] if k < len(bb) else None
        pts = []
        if cls == "polygon" and box is not None and box[0] is not None:
            pts = polygon_points(oa)
        rec = {"class": cls, "bbox": box, "points": pts}
        if cls == "arc":
            rec["circle"] = arcs[arc_i] if arc_i < len(arcs) else None
            arc_i += 1
        out.append(rec)
    return out


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    path = args[0] if args else "synth/shapes/schematic/sch.oa"
    figs = decode(path)
    print(f"{path}: {len(figs)} figure(s)")
    for k, f in enumerate(figs):
        b = f["bbox"]
        if b is None:
            where = "-"
        else:
            fmt = lambda v: "?" if v is None else f"{v:g}"
            where = f"({fmt(b[0])},{fmt(b[1])})-({fmt(b[2])},{fmt(b[3])})"
        pts = f["points"]
        extra = "" if not pts else "  pts=" + " ".join(f"({x:g},{y:g})" for x, y in pts)
        print(f"   {k}: {str(f['class']):8s} {where}{extra}")


if __name__ == "__main__":
    main()
