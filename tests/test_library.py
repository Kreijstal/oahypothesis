"""Tests for oaparser.library -- resolving lib.cell.view to a cellview file."""

import os
import tempfile
import unittest
from pathlib import Path

from oaparser.library import LibraryResolver, resolver_for


def make_cellview(root: Path, lib: str, cell: str, view: str,
                  filename: str = None) -> Path:
    d = root / lib / cell / view
    d.mkdir(parents=True, exist_ok=True)
    f = d / (filename or f"{view}.oa")
    f.write_bytes(b"\x00")
    return f


class LibraryResolverTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.artist = self.root / "artist"
        self.analog = make_cellview(self.artist, "analogLib", "nmos4", "symbol")
        self.basic = make_cellview(self.root, "basic", "iopin", "symbolr")
        self.sch = make_cellview(self.artist, "analogLib", "ideal_balun",
                                 "schematic", "sch.oa")

    def tearDown(self):
        self.tmp.cleanup()

    def test_infers_own_library(self):
        r = resolver_for(str(self.sch))
        self.assertEqual(r.resolve("analogLib", "nmos4", "symbol"), self.analog)

    def test_resolves_sibling_library(self):
        # basic sits beside artist/, one level up from analogLib
        r = resolver_for(str(self.sch))
        self.assertEqual(r.resolve("basic", "iopin", "symbolr"), self.basic)

    def test_schematic_file_name(self):
        r = resolver_for(str(self.sch))
        self.assertEqual(r.resolve("analogLib", "ideal_balun", "schematic"),
                         self.sch)

    def test_cds_lib_define(self):
        cds = self.root / "cds.lib"
        cds.write_text("DEFINE other %s\n" % (self.root / "other"))
        make_cellview(self.root, "other", "x", "symbol")
        r = LibraryResolver(cds_lib=str(cds))
        self.assertIsNotNone(r.resolve("other", "x", "symbol"))

    def test_search_dir_treats_children_as_libraries(self):
        r = LibraryResolver()
        r.add_search_dir(str(self.artist))
        self.assertEqual(r.resolve("analogLib", "nmos4", "symbol"), self.analog)

    def test_missing_returns_none_and_is_cached(self):
        r = resolver_for(str(self.sch))
        self.assertIsNone(r.resolve("nope", "none", "symbol"))
        self.assertIn(("nope", "none", "symbol"), r._misses)

    def test_resolve_spec(self):
        r = resolver_for(str(self.sch))
        self.assertEqual(r.resolve_spec("analogLib.nmos4.symbol"), self.analog)
        self.assertIsNone(r.resolve_spec("not-a-spec"))


if __name__ == "__main__":
    unittest.main()
