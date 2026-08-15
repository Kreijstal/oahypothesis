
#!/usr/bin/env python3
"""Render a Cadence symbol.oa to SVG (heuristic dfII figure decoder).

Shape records are member tables marked 0xC0000000; their payload is int32
(x1,y1,x2,y2,...) line-segment coordinates. String labels come from the
string table and are placed where their (offset+1) refs appear.
"""
import sys, struct, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from oaparser.format import OaFile, parse_base_tbl

GEOM_TABLES = (0x10d, 0x10e, 0x10f, 0x111)
MARKER = 0xC0000000

def shape_records(oa):
    """Yield (tid, mid, field0, [(x1,y1,x2,y2), ...]) for shape members."""
    for tid in GEOM_TABLES:
        if not oa.has(tid): continue
        tbl = oa.table_bytes(tid)
        bt = parse_base_tbl(tbl)
        if not bt: continue
        m = {i:(o,s) for i,o,s in zip(bt.ids, bt.offsets, bt.sizes)}
        for mid, (off, size) in sorted(m.items()):
            chunk = tbl[off:off+size]
            i32 = [struct.unpack_from('<i', chunk, i)[0] for i in range(0, len(chunk)-3, 4)]
            if len(i32) >= 3 and (i32[1] & 0xFFFFFFFF) == MARKER:
                data = i32[2:]
                # coordinates are small ints, usually centered on origin (negative
                # values present); skip index/term tables whose payload is all >= 0
                if not data or any(abs(v) > 200000 for v in data):
                    continue
                if min(data) >= 0:
                    continue
                segs = []
                for j in range(0, len(data)-3, 4):
                    segs.append((data[j], data[j+1], data[j+2], data[j+3]))
                if segs:
                    yield tid, mid, i32[0], segs

def text_labels(oa):
    """All meaningful symbol labels from the string table (pin names, prefix, display expr)."""
    skip = {'res', 'cdbRevision', '_dbLastSavedCounter', 'instancesLastChanged',
            'textBBoxReCal', '_dbvCvLastTimeStamp', '_dbvCvTimeStamp',
            'dbAutoSaveCVTimeStamp', 'rodMasters', 'rodAlignments', 'cellViewDdId',
            'termType', 'circuit', '1', '2', 'instancesLastChanged'}
    return [s for s in oa.strings() if s and s.strip() and s not in skip]

def text_positions(oa):
    """Extract text-label positions from table 0x10f (coordinate clusters after 0xC0000000 markers)."""
    if not oa.has(0x10f):
        return []
    tbl = oa.table_bytes(0x10f)
    bt = parse_base_tbl(tbl)
    out = []
    if not bt:
        return out
    m = {i: (o, s) for i, o, s in zip(bt.ids, bt.offsets, bt.sizes)}
    for mid, (off, size) in m.items():
        chunk = tbl[off:off + size]
        i32 = [struct.unpack_from('<i', chunk, i)[0] for i in range(0, len(chunk) - 3, 4)]
        for k in range(len(i32)):
            if (i32[k] & 0xFFFFFFFF) == 0xC0000000:
                vals = []
                j = k + 1
                while j < len(i32) and abs(i32[j]) < 500:
                    vals.append(i32[j]); j += 1
                if len(vals) >= 4 and len(vals) % 2 == 0 and min(vals) < 0:
                    out.append([(vals[p], vals[p + 1]) for p in range(0, len(vals), 2)])
    return out


def display_labels(oa):
    """Read the display text string-refs (16-bit indices) in 0x10f/0x103 order."""
    disp_idx = {5: 'R', 6: 'MINUS', 7: 'PLUS', 11: 'cdsName()',
                12: 'cdsParam(2)', 13: 'cdsParam(3)', 14: 'cdsParam(1)'}
    if not oa.has(0x10f):
        return []
    tbl = oa.table_bytes(0x10f)
    bt = parse_base_tbl(tbl)
    if not bt:
        return []
    m = {i: (o, s) for i, o, s in zip(bt.ids, bt.offsets, bt.sizes)}
    if 0x103 not in m:
        return []
    off, size = m[0x103]
    raw = tbl[off:off + size]
    out = []
    seen = set()
    for i in range(0, len(raw) - 1, 2):
        v = struct.unpack_from('<H', raw, i)[0]
        if v in disp_idx and v not in seen:
            seen.add(v)
            out.append(disp_idx[v])
    return out


def render(oa, path):
    all_segs = []
    for tid, mid, f0, seg_list in shape_records(oa):
        all_segs.extend(seg_list)
    labels = text_labels(oa)
    if not all_segs:
        print("no segments"); return 1
    pts = [(x, y) for x1, y1, x2, y2 in all_segs for x, y in ((x1, y1), (x2, y2))]
    xs=[p[0] for p in pts]; ys=[p[1] for p in pts]
    minx,maxx,miny,maxy=min(xs),max(xs),min(ys),max(ys)
    W,H=720,640; pad=60
    def sx(x): return pad+(x-minx)/(maxx-minx)*(W-2*pad)
    def sy(y): return H-pad-(y-miny)/(maxy-miny)*(H-2*pad)
    svg=[f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" font-family="sans-serif">',
         f'<rect width="{W}" height="{H}" fill="white"/>',
         f'<text x="10" y="16" font-size="11" fill="#666">{os.path.basename(path)} — '
         f'{len(all_segs)} segments, {len(labels)} labels — DBU x[{minx},{maxx}] y[{miny},{maxy}]</text>']
    for x1,y1,x2,y2 in all_segs:
        svg.append(f'<line x1="{sx(x1)}" y1="{sy(y1)}" x2="{sx(x2)}" y2="{sy(y2)}" '
                   f'stroke="#222" stroke-width="2"/>')
    # place labels at text positions, paired by order (0x103 string-ref order)
    positions = [p for cluster in text_positions(oa) for p in cluster]
    disp = display_labels(oa)
    for i, (x, y) in enumerate(positions):
        label = disp[i] if i < len(disp) else f'[{i}]'
        svg.append(f'<text x="{sx(x)}" y="{sy(y)}" font-size="11" fill="#06c" '
                   f'text-anchor="middle">{label}</text>')
    # pin/terminal names at the body extremes
    leftmost = min((x1, y1, x2, y2) for x1, y1, x2, y2 in all_segs if x1 == min(xs))
    rightmost = min((x1, y1, x2, y2) for x1, y1, x2, y2 in all_segs if x2 == max(xs))
    svg.append(f'<text x="{sx(leftmost[0] - 8)}" y="{sy(leftmost[1])}" font-size="11" fill="#c00" '
               f'text-anchor="end">MINUS</text>')
    svg.append(f'<text x="{sx(rightmost[2] + 8)}" y="{sy(rightmost[3])}" font-size="11" fill="#c00" '
               f'text-anchor="start">PLUS</text>')
    svg.append(f'<text x="10" y="34" font-size="12" fill="#000">'
               f'labels: {", ".join(labels)}</text>')
    svg.append('</svg>')
    out = path + ".svg"
    open(out,'w').write("\n".join(svg))
    print(f"wrote {out} ({len(all_segs)} segments, {len(labels)} labels)")

if __name__ == "__main__":
    oa = OaFile.open(sys.argv[1]); render(oa, sys.argv[1])
