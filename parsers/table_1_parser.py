#!/usr/bin/env python3
"""
Parser for Table 0x1 - Global Metadata and Version Information

This table contains:
- Version strings
- Platform and compiler information
- Counters and timestamps at fixed offsets
- A global 'last saved' timestamp at offset 0x9b4
- Other unknown data structures
"""

import struct
import datetime
from dataclasses import dataclass
from typing import List
from oaparser import BinaryCurator, Region

def parse_unix_timestamp(data: bytes, label: str = "") -> str:
    """Parses a 4-byte little-endian Unix timestamp."""
    if len(data) != 4:
        return "[Invalid data length for timestamp]"
    ts = struct.unpack('<I', data)[0]
    result = f"{label}{ts} (0x{ts:x})"
    if ts > 0:
        try:
            dt = datetime.datetime.fromtimestamp(ts, datetime.timezone.utc)
            result += f" → {dt.strftime('%Y-%m-%d %H:%M:%S UTC')}"
        except (ValueError, OSError):
            result += " → [Invalid Timestamp]"
    return result

def parse_integer(data: bytes) -> str:
    """Parses a 4-byte little-endian integer."""
    val = struct.unpack('<I', data)[0]
    return f"{val} (0x{val:x})"

@dataclass
class Table1Parser:
    """Parser for Table 0x1 which contains global metadata."""
    data: bytes

    def parse(self) -> List[Region]:
        """Parse Table 0x1 and return regions."""
        curator = BinaryCurator(self.data)

        # --- Sequentially claim known fields from the start ---
        curator.claim("Header bytes", 6, lambda d: ' '.join(f'{b:02x}' for b in d))

        for i in range(3):
            if curator.cursor >= len(self.data): break
            string_start = curator.cursor
            string_end = self.data.find(b'\x00', string_start)
            if string_end == -1: string_end = len(self.data)

            string_len = string_end - string_start + 1
            curator.claim(f"Version String {i+1}", string_len, lambda d: f'"{d.rstrip(b"\\x00").decode("utf-8", "replace")}"')

            next_aligned = ((curator.cursor + 15) // 16) * 16
            padding_needed = next_aligned - curator.cursor
            if padding_needed > 0 and curator.cursor + padding_needed <= len(self.data):
                curator.claim(f"Padding after String {i+1}", padding_needed, lambda d: f"{len(d)} bytes")

        # --- Claim the Platform/Compiler Info block at 0x40 ---
        if curator.cursor == 0x40 and len(self.data) >= 0x68:
            def platform_info_parser(data):
                header = struct.unpack('<Q', data[:8])[0]
                platform_string = data[8:].split(b'\x00', 1)[0].decode('utf-8', 'replace')
                return f"Platform: '{platform_string}', Header: {header} (0x{header:x})"

            curator.claim("Platform Info", 40, platform_info_parser)

        # --- Use absolute offsets to claim known, non-contiguous fields ---

        # Claim Counters at 0x68
        if len(self.data) >= 0x68 + 8:
            curator.seek(0x68)
            curator.claim("Counter 1", 4, parse_integer)
            curator.claim("Counter 2", 4, parse_integer)

        # Claim 64-bit Timestamps at 0x70
        if len(self.data) >= 0x70 + 16:
            curator.seek(0x70)
            def wide_timestamp_parser(data):
                lo, hi = struct.unpack('<II', data)
                return f"Lo: {lo} (0x{lo:x}), Hi: {parse_unix_timestamp(data[4:])}"

            curator.claim("Timestamp 1 (64-bit)", 8, wide_timestamp_parser)
            curator.claim("Timestamp 2 (64-bit)", 8, wide_timestamp_parser)

        # Claim the known repeating save counters
        known_counter_offsets = [0x998, 0x9c8, 0xa38]
        for i, offset in enumerate(known_counter_offsets):
            if len(self.data) >= offset + 4:
                curator.seek(offset)
                curator.claim(f"Save Counter Group {i+1}", 4, parse_integer)

        # Claim the single known Global Timestamp at 0x9B4
        if len(self.data) >= 0x9B4 + 4:
            curator.seek(0x9B4)
            curator.claim("Global Timestamp", 4, lambda d: parse_unix_timestamp(d))

        return curator.get_regions()


if __name__ == '__main__':
    import sys
    from oaparser.main import OAParser

    if len(sys.argv) != 2:
        print("Usage: python3 table_1_parser.py <oa_file>")
        sys.exit(1)

    filepath = sys.argv[1]

    try:
        oa_parser = OAParser(filepath)
        table_1 = oa_parser.get_table_by_id(0x1)

        if table_1:
            print(f"--- Parsing Table 0x1 (Size: {len(table_1.data)} bytes) ---")
            parser = Table1Parser(table_1.data)
            regions = parser.parse()
            for region in regions:
                print(region)
        else:
            print("Table 0x1 not found in file")

    except FileNotFoundError:
        print(f"ERROR: File not found at '{filepath}'")
        sys.exit(1)
    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
