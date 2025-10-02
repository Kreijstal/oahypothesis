#!/usr/bin/env python3
"""
Parser for Table 0x1 - Global Metadata and Version Information

This table contains:
- Version strings
- Counters/timestamps
- Arrays of table IDs or references
"""

import struct
import datetime
from dataclasses import dataclass
from typing import List
from oaparser import BinaryCurator

@dataclass
class Table1Parser:
    """Parser for Table 0x1 which contains global metadata."""
    data: bytes
    
    def parse(self) -> str:
        """Parse Table 0x1 and return a formatted string representation."""
        if len(self.data) < 128:
            return f"Table 0x1 (Global Metadata): {len(self.data)} bytes (too small to parse)"
        
        curator = BinaryCurator(self.data)
        
        # Claim the 6-byte header
        curator.claim("Header bytes", 6, lambda d: ' '.join(f'{b:02x}' for b in d))
        
        # Extract and claim version strings (expecting 3)
        for i in range(3):
            if curator.cursor >= len(self.data):
                break
                
            string_start = curator.cursor
            string_end = self.data.find(b'\x00', string_start)
            if string_end == -1:
                break
            
            string_len = string_end - string_start + 1  # Include null terminator
            
            def make_string_parser(data):
                try:
                    return f'"{data.rstrip(b"\\x00").decode("utf-8", errors="replace")}"'
                except:
                    return "[DECODE ERROR]"
            
            curator.claim(f"Version String {i+1}", string_len, make_string_parser)
            
            # Strings are padded to 16-byte boundaries
            next_aligned = ((string_end + 16) // 16) * 16
            padding_needed = next_aligned - curator.cursor
            if padding_needed > 0 and curator.cursor < len(self.data):
                curator.claim(f"Padding after String {i+1}", padding_needed, 
                            lambda d: f"{len(d)} bytes")
        
        # Jump to known locations for counters/timestamps
        if len(self.data) >= 0x70:
            # Claim any gap before counters
            if curator.cursor < 0x68:
                gap_size = 0x68 - curator.cursor
                curator.seek(curator.cursor)
                curator.claim("Gap before counters", gap_size, lambda d: f"{len(d)} bytes")
            
            # Claim the two counters at 0x68 and 0x6c
            curator.seek(0x68)
            curator.claim("Counter 1", 4, lambda d: f"{struct.unpack('<I', d)[0]} (0x{struct.unpack('<I', d)[0]:x})")
            curator.claim("Counter 2", 4, lambda d: f"{struct.unpack('<I', d)[0]} (0x{struct.unpack('<I', d)[0]:x})")
        
        if len(self.data) >= 0x80:
            # Claim the two timestamps at 0x70 and 0x78
            curator.seek(0x70)
            
            def timestamp_parser(data):
                ts = struct.unpack('<Q', data)[0]
                ts_32 = ts & 0xFFFFFFFF
                result = f"{ts_32} (0x{ts_32:x})"
                if ts_32 > 0:
                    try:
                        dt = datetime.datetime.fromtimestamp(ts_32, datetime.timezone.utc)
                        result += f" → {dt.strftime('%Y-%m-%d %H:%M:%S UTC')}"
                    except:
                        pass
                return result
            
            curator.claim("Timestamp 1", 8, timestamp_parser)
            curator.claim("Timestamp 2", 8, timestamp_parser)
        
        # Claim the array section starting at 0x80
        array_start = 0x80
        if len(self.data) > array_start:
            curator.seek(array_start)
            remaining = len(self.data) - array_start
            num_ints = remaining // 4
            
            # Claim each integer in the array
            for i in range(num_ints):
                curator.claim(
                    f"Array[{i}]",
                    4,
                    lambda d, idx=i: f"{struct.unpack('<I', d)[0]} (0x{struct.unpack('<I', d)[0]:x})"
                )
        
        # Generate report
        lines = [f"Table 0x1 (Global Metadata): {len(self.data)} bytes"]
        lines.append("="*80)
        lines.append("")
        lines.append(curator.report())
        
        # Add summary statistics
        if len(self.data) > array_start:
            num_ints = (len(self.data) - array_start) // 4
            all_vals = [struct.unpack_from('<I', self.data, array_start + i*4)[0] 
                       for i in range(num_ints)]
            non_zero = [v for v in all_vals if v != 0]
            
            lines.append("")
            lines.append("="*80)
            lines.append(f"Array Statistics:")
            lines.append(f"  Total integers: {num_ints}")
            lines.append(f"  Non-zero values: {len(non_zero)}/{num_ints}")
            if non_zero:
                lines.append(f"  Min value: {min(non_zero)}")
                lines.append(f"  Max value: {max(non_zero)}")
        
        lines.append("="*80)
        return "\n".join(lines)

def parse_table_1(data: bytes) -> str:
    """Convenience function to parse Table 0x1."""
    parser = Table1Parser(data)
    return parser.parse()

if __name__ == '__main__':
    import sys
    
    if len(sys.argv) != 2:
        print("Usage: python3 table_1_parser.py <oa_file>")
        sys.exit(1)
    
    filepath = sys.argv[1]
    
    try:
        with open(filepath, 'rb') as f:
            # Read header and table directory
            header = f.read(24)
            _, _, _, _, _, used = struct.unpack('<IHHQII', header)
            ids = list(struct.unpack(f'<{used}Q', f.read(8 * used)))
            offsets = list(struct.unpack(f'<{used}Q', f.read(8 * used)))
            sizes = list(struct.unpack(f'<{used}Q', f.read(8 * used)))
            
            # Find Table 0x1
            if 0x1 in ids:
                idx = ids.index(0x1)
                f.seek(offsets[idx])
                data = f.read(sizes[idx])
                
                parser = Table1Parser(data)
                print(parser.parse())
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
