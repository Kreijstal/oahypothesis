#!/usr/bin/env python3
"""
Parser for Table 0x1 - Global Metadata and Version Information

This table contains:
- Version strings
- Counters/timestamps
- Arrays of table IDs or references
"""

import struct
from dataclasses import dataclass
from typing import List

@dataclass
class Table1Parser:
    """Parser for Table 0x1 which contains global metadata."""
    data: bytes
    
    def parse(self) -> str:
        """Parse Table 0x1 and return a formatted string representation."""
        if len(self.data) < 128:
            return f"Table 0x1 (Global Metadata): {len(self.data)} bytes (too small to parse)"
        
        lines = []
        lines.append(f"Table 0x1 (Global Metadata): {len(self.data)} bytes")
        lines.append("="*80)
        
        # Parse header section with version strings
        offset = 0
        
        # First 6 bytes appear to be padding or flags
        header_bytes = self.data[0:6]
        lines.append(f"\nHeader bytes: {' '.join(f'{b:02x}' for b in header_bytes)}")
        offset = 6
        
        # Extract null-terminated strings
        strings = []
        for i in range(3):  # Expect 3 version strings
            string_start = offset
            string_end = self.data.find(b'\x00', string_start)
            if string_end == -1:
                break
            
            string_data = self.data[string_start:string_end]
            try:
                string_val = string_data.decode('utf-8', errors='replace')
                strings.append(string_val)
                lines.append(f"\nVersion String {i+1}: \"{string_val}\"")
            except:
                pass
            
            # Move to next aligned position (strings seem to be padded to 16-byte boundaries)
            offset = ((string_end + 16) // 16) * 16
        
        # After strings, there are some important fields
        if len(self.data) >= 0x70:
            # Counters/flags at offset 0x68
            counter1 = struct.unpack_from('<I', self.data, 0x68)[0]
            counter2 = struct.unpack_from('<I', self.data, 0x6c)[0]
            lines.append(f"\nCounter 1 (offset 0x68): {counter1} (0x{counter1:x})")
            lines.append(f"Counter 2 (offset 0x6c): {counter2} (0x{counter2:x})")
        
        if len(self.data) >= 0x80:
            # Timestamps at offset 0x70 and 0x78
            ts1 = struct.unpack_from('<Q', self.data, 0x70)[0]
            ts2 = struct.unpack_from('<Q', self.data, 0x78)[0]
            
            # Extract 32-bit timestamp (lower 32 bits)
            ts1_32 = ts1 & 0xFFFFFFFF
            ts2_32 = ts2 & 0xFFFFFFFF
            
            lines.append(f"\nTimestamp 1 (offset 0x70): {ts1_32} (0x{ts1_32:x})")
            lines.append(f"Timestamp 2 (offset 0x78): {ts2_32} (0x{ts2_32:x})")
            
            # Try to interpret as Unix timestamp (only if non-zero)
            if ts1_32 > 0 or ts2_32 > 0:
                try:
                    import datetime
                    if ts1_32 > 0:
                        dt1 = datetime.datetime.fromtimestamp(ts1_32, datetime.timezone.utc)
                        lines.append(f"  TS1 → {dt1.strftime('%Y-%m-%d %H:%M:%S UTC')}")
                    if ts2_32 > 0:
                        dt2 = datetime.datetime.fromtimestamp(ts2_32, datetime.timezone.utc)
                        lines.append(f"  TS2 → {dt2.strftime('%Y-%m-%d %H:%M:%S UTC')}")
                except:
                    pass
        
        # Parse the array section (starts around offset 0x80)
        array_start = 0x80
        if len(self.data) > array_start:
            lines.append(f"\n\nArray Data (starting at offset 0x{array_start:x}):")
            lines.append("-"*80)
            
            # Parse as 32-bit integers
            num_ints = (len(self.data) - array_start) // 4
            lines.append(f"Contains {num_ints} 32-bit integers")
            
            # Show first 20 values
            lines.append("\nFirst 20 values:")
            for i in range(min(20, num_ints)):
                offset_pos = array_start + i * 4
                val = struct.unpack_from('<I', self.data, offset_pos)[0]
                lines.append(f"  [{i:03d}] offset 0x{offset_pos:04x}: {val:6d} (0x{val:04x})")
            
            if num_ints > 20:
                lines.append(f"  ... ({num_ints - 20} more values)")
            
            # Show some statistics
            all_vals = [struct.unpack_from('<I', self.data, array_start + i*4)[0] 
                       for i in range(num_ints)]
            non_zero = [v for v in all_vals if v != 0]
            
            lines.append(f"\nArray Statistics:")
            lines.append(f"  Non-zero values: {len(non_zero)}/{num_ints}")
            if non_zero:
                lines.append(f"  Min value: {min(non_zero)}")
                lines.append(f"  Max value: {max(non_zero)}")
        
        lines.append("\n" + "="*80)
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
