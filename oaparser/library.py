"""Library resolution: find the .oa file for a master cellview.

A schematic's figures are only half the drawing -- instances reference master
cellviews by ``lib.cell.view``, and those live in other files. This module maps
that reference to a path.

Resolution order
----------------
1. An explicit library root registered for the name
   (``DEFINE name dir`` in cds.lib, or added programmatically).
2. Any registered search directory, treating each subdirectory as a library:
   ``<dir>/<lib>/<cell>/<view>/``. This is how the vendor layout works -- the
   libraries sit side by side under one artist directory, so a schematic in
   ``analogLib`` can reference ``basic.iopin.symbolr`` which lives in a sibling.
3. The parent library of the cellview that referenced it, which covers masters
   inside the same library.

The view directory usually holds one ``.oa`` file named after the view
(``symbol.oa``), but a schematic is ``sch.oa``, so the file name is discovered
rather than assumed.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Dict, List, Optional

# views whose file name does not match the view name
_VIEW_FILENAMES = {"schematic": ("sch.oa",)}


class LibraryResolver:
    """Maps ``lib.cell.view`` to a cellview file path."""

    def __init__(self, cds_lib: Optional[str] = None) -> None:
        self.roots: Dict[str, Path] = {}
        self.search_dirs: List[Path] = []
        self._misses: set = set()
        if cds_lib:
            self.add_cds_lib(cds_lib)

    # ---------------------------------------------------------------- setup

    def add_cds_lib(self, path: str) -> None:
        """Read ``DEFINE <name> <dir>`` lines (and ``SOFTINCLUDE``/``INCLUDE``
        are ignored -- only DEFINE matters here)."""
        p = Path(path)
        if not p.is_file():
            return
        for line in p.read_text(errors="replace").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or line.startswith(";"):
                continue
            parts = line.split()
            if len(parts) >= 3 and parts[0].upper() == "DEFINE":
                self.roots[parts[1]] = Path(parts[2])

    def add_root(self, name: str, directory: str) -> None:
        self.roots[name] = Path(directory)

    def add_search_dir(self, directory: str) -> None:
        d = Path(directory)
        if d.is_dir() and d not in self.search_dirs:
            self.search_dirs.append(d)

    def infer_from_cellview(self, path: str) -> None:
        """Register the library and sibling libraries of a cellview file.

        ``<artist>/<lib>/<cell>/<view>/<file>.oa`` -> registers ``<lib>`` with
        root ``<artist>/<lib>`` and ``<artist>`` as a search directory, so
        masters in sibling libraries also resolve.
        """
        p = Path(path).resolve()
        if len(p.parents) < 3:
            return
        view_dir = p.parent
        cell_dir = view_dir.parent
        lib_dir = cell_dir.parent
        self.roots.setdefault(lib_dir.name, lib_dir)
        # libraries need not be siblings: in the vendor tree `analogLib` sits
        # under artist/ while `basic` sits under cdslib/, one level higher
        self.add_search_dir(str(lib_dir.parent))
        if len(lib_dir.parents) >= 2:
            self.add_search_dir(str(lib_dir.parent.parent))

    # ------------------------------------------------------------- lookup

    @staticmethod
    def _encoded_name(name: str) -> str:
        """OA stores awkward characters in cell/view names as #XX (hex).

        e.g. the master spec `pllMMLib.one-z_inv.symbol` is the directory
        `one#2dz_inv`, because '-' is 0x2d.
        """
        out = []
        for ch in name:
            if ch.isalnum() or ch in "_":
                out.append(ch)
            else:
                out.append("#%02x" % ord(ch))
        return "".join(out)

    def _candidates(self, lib: str, cell: str, view: str):
        names = _VIEW_FILENAMES.get(view, ()) + (f"{view}.oa",)
        cells = [cell]
        enc = self._encoded_name(cell)
        if enc != cell:
            cells.append(enc)
        if self._encoded_name(view) != view:
            names = names + (f"{self._encoded_name(view)}.oa",)
        roots = []
        if lib in self.roots:
            roots.append(self.roots[lib])
        for d in self.search_dirs:
            roots.append(d / lib)
        for root in roots:
            for cell_name in cells:
                for name in names:
                    yield root / cell_name / view / name
                yield root / cell_name / view   # directory: any .oa inside

    def resolve(self, lib: str, cell: str, view: str) -> Optional[Path]:
        key = (lib, cell, view)
        if key in self._misses:
            return None
        for cand in self._candidates(lib, cell, view):
            if cand.is_file():
                return cand
            if cand.is_dir():
                oa = sorted(
                    f for f in cand.glob("*.oa")
                    if not f.name.endswith(".cdslck")
                )
                if oa:
                    return oa[0]
        self._misses.add(key)
        return None

    def resolve_spec(self, spec: str) -> Optional[Path]:
        """Resolve a dotted ``lib.cell.view`` string."""
        parts = (spec or "").split(".")
        if len(parts) != 3:
            return None
        return self.resolve(parts[0], parts[1], parts[2])


def resolver_for(path: str, cds_lib: Optional[str] = None,
                 search_dirs: Optional[List[str]] = None) -> LibraryResolver:
    """Convenience: a resolver pre-seeded from one cellview's own location."""
    r = LibraryResolver(cds_lib=cds_lib or os.environ.get("CDS_LIB"))
    for d in search_dirs or []:
        r.add_search_dir(d)
    r.infer_from_cellview(path)
    return r
