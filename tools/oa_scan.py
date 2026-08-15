
#!/usr/bin/env python3
"""Batch-parse all .oa files under a path and summarize the table inventory."""
import os, sys, struct
from collections import Counter
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from oaparser.format import OaFile, MAGIC

def scan(paths):
    ok = fail = 0
    table_ids = Counter()
    sizes = []
    files = []
    for p in paths:
        try:
            oa = OaFile.open(p)
            ok += 1
            ids = [e.id for e in oa.entries if not e.deleted]
            table_ids.update(ids)
            sizes.append(len(oa.data))
            files.append((p, oa.header.num_used, len(oa.strings()), len(oa.data)))
        except Exception as e:
            fail += 1
            print(f"FAIL {p}: {e}")
    print(f"parsed {ok} files, {fail} failed")
    print(f"total bytes: {sum(sizes)}")
    print(f"unique table ids: {len(table_ids)}")
    print(f"table id histogram (hex: count):")
    for tid, n in sorted(table_ids.items()):
        print(f"  0x{tid:04x}: {n}")
    return files, table_ids

if __name__ == "__main__":
    verbose = "-v" in sys.argv or "--verbose" in sys.argv
    roots = [a for a in sys.argv[1:] if not a.startswith("-")] or ["."]
    paths = []
    for r in roots:
        if os.path.isfile(r):
            paths.append(r)
        else:
            for dirpath, _, fns in os.walk(r):
                for fn in fns:
                    if fn.endswith(".oa"):
                        paths.append(os.path.join(dirpath, fn))
    print(f"found {len(paths)} .oa files")
    if verbose:
        for p in sorted(paths):
            try:
                oa = OaFile.open(p)
                print(f"{oa.header.num_used:>3} tbl  {len(oa.strings()):>4} str  "
                      f"{oa.byteorder}  {len(oa.data):>7}B  {p}")
            except Exception as e:
                print(f"FAIL {p}: {e}")
    else:
        scan(paths)
