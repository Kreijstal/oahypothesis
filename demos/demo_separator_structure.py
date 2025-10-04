#!/usr/bin/env python3
"""
Demonstration of the corrected understanding of the separator-based structure.

This script shows:
1. The structure appears in sch5-11 (7 files), not just sch5-8
2. Detection is based on separator pattern, not a "signature"
3. Payload values are dynamic data that change over time
4. The "signature" we thought was fixed is actually variable data
"""

import sys
import os
# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import struct
from parsers.table_c_parser import HypothesisParser

def extract_table_0xc(filename):
    """Extract table 0xc and string table from .oa file"""
    try:
        with open(filename, 'rb') as f:
            header = f.read(24)
            _, _, _, _, _, used = struct.unpack('<IHHQII', header)
            ids = list(struct.unpack(f'<{used}Q', f.read(8 * used)))
            offsets = list(struct.unpack(f'<{used}Q', f.read(8 * used)))
            sizes = list(struct.unpack(f'<{used}Q', f.read(8 * used)))
            
            string_table_data = None
            for i in range(used):
                if ids[i] == 0x0a:
                    f.seek(offsets[i])
                    string_table_data = f.read(sizes[i])
                    break
            
            for i in range(used):
                if ids[i] == 0x0c:
                    f.seek(offsets[i])
                    return f.read(sizes[i]), string_table_data
        return None, None
    except:
        return None, None


def main():
    print("="*80)
    print("SEPARATOR-BASED STRUCTURE: CORRECTED UNDERSTANDING")
    print("="*80)
    print()
    
    print("OLD (WRONG) UNDERSTANDING:")
    print("  • Structure appears only in sch5-8")
    print("  • Detected by looking for 'signature' bytes: 08 00 00 00 03 00 00 00")
    print("  • Mysteriously 'disappears' in sch9+")
    print()
    
    print("NEW (CORRECT) UNDERSTANDING:")
    print("  • Structure appears in sch5-11 (7 files total)")
    print("  • Detected by separator pattern: 00 00 00 c8 02 00 00 00 e8 00 1a 03")
    print("  • The '08 00 00 00' is DATA, not a signature - it changes!")
    print("  • Structure was there all along, just not detected correctly")
    print()
    
    print("="*80)
    print("PAYLOAD VALUES ACROSS FILES")
    print("="*80)
    print()
    
    # Files to check
    files_to_check = [
        ('files/rc/sch5.oa', 'First appearance'),
        ('files/rc/sch6.oa', 'Resistor -> Capacitor'),
        ('files/rc/sch7.oa', 'New resistor added'),
        ('files/rc/sch8.oa', 'Wire drawn'),
        ('files/rc/sch9.oa', 'R1 resistance changed'),
        ('files/rc/sch10.oa', 'R1 resistance changed again'),
        ('files/rc/sch11.oa', 'Additional change'),
        ('files/rc/sch12.oa', 'Structure disappears'),
    ]
    
    print(f"{'File':<15} {'Description':<30} {'Payload Values':<20} {'Size':<6} {'Marker'}")
    print("-" * 80)
    
    for filename, description in files_to_check:
        data, string_table = extract_table_0xc(filename)
        if data:
            parser = HypothesisParser(data, string_table)
            regions = parser.parse()
            
            found = False
            for region in regions:
                if hasattr(region, 'parsed_value') and type(region.parsed_value).__name__ == 'UnknownStruct60Byte':
                    rec = region.parsed_value
                    if len(rec.payload) % 4 == 0:
                        payload_ints = list(struct.unpack(f'<{len(rec.payload)//4}I', rec.payload))
                    else:
                        payload_ints = []
                    
                    has_marker = b'\xff\xff\xff\xff' in rec.trailing_separator
                    marker_str = "0xffffffff" if has_marker else "None"
                    
                    payload_str = str(payload_ints)
                    print(f"{filename:<15} {description:<30} {payload_str:<20} {len(rec.data):<6} {marker_str}")
                    found = True
                    break
            
            if not found:
                print(f"{filename:<15} {description:<30} {'NOT FOUND':<20} {'-':<6} {'-'}")
    
    print()
    print("="*80)
    print("KEY INSIGHTS")
    print("="*80)
    print()
    print("1. SIGNATURE WAS ACTUALLY DATA:")
    print("   The bytes we thought were a 'signature' (08 00 00 00) are the FIRST")
    print("   payload value. It changes from 8 to 3 between sch8 and sch9!")
    print()
    print("2. SEPARATOR IS THE ANCHOR:")
    print("   The reliable pattern is the separator: 00 00 00 c8 02 00 00 00 e8 00 1a 03")
    print("   This appears at the END of the structure in all files.")
    print()
    print("3. VARIABLE STRUCTURE SIZE:")
    print("   Size is not fixed at 60 bytes:")
    print("   - sch6: 56 bytes (no 0xffffffff marker, more payload)")
    print("   - Others: 60 bytes (with marker or more padding)")
    print()
    print("4. DYNAMIC PAYLOAD VALUES:")
    print("   [8, 3, 0] -> [8, 3, 1, 2] -> [3, 3, 0] -> [8, 4, 0]")
    print("   These values track some state/counter that changes as components are modified.")
    print()
    print("="*80)
    print("CONCLUSION")
    print("="*80)
    print()
    print("The original parser was FUNDAMENTALLY WRONG about detection.")
    print()
    print("By treating dynamic data as a fixed signature, we missed the structure")
    print("in files sch9-11. The correct approach is to search for the separator")
    print("pattern and work backwards to extract the variable payload.")
    print()
    print("This correction changes our understanding of when this structure appears")
    print("and what it represents in the .oa file format.")
    print()


if __name__ == '__main__':
    main()
