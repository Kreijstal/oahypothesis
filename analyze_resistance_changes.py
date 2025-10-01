#!/usr/bin/env python3
"""
Detailed analysis of resistance value changes across sch5, sch9, sch10, and sch14.

This script examines:
1. Property value IDs and their locations
2. String table contents  
3. Raw byte comparisons
4. Patterns in table 0xc structure
"""

import struct
from table_c_parser import HypothesisParser, PropertyValueRecord

def get_table_0xc(filename):
    """Extract Table 0xC data from an .oa file."""
    with open(filename, 'rb') as f:
        header = f.read(24)
        _, _, _, _, _, used = struct.unpack('<IHHQII', header)
        ids = list(struct.unpack(f'<{used}Q', f.read(8 * used)))
        offsets = list(struct.unpack(f'<{used}Q', f.read(8 * used)))
        sizes = list(struct.unpack(f'<{used}Q', f.read(8 * used)))
        
        for i in range(used):
            if ids[i] == 0x0c:
                f.seek(offsets[i])
                return f.read(sizes[i])
    return None

def get_property_values(filename):
    """Get property value records from a file."""
    data = get_table_0xc(filename)
    if not data:
        return []
    
    parser = HypothesisParser(data)
    parser.parse()
    
    result = []
    for record in parser.records:
        if isinstance(record, PropertyValueRecord):
            result.append({
                'offset': record.offset,
                'value_id': record.property_value_id,
                'size': record.size
            })
    return result

def find_value_in_bytes(data, target_val):
    """Find where a specific 32-bit value appears in the data."""
    locations = []
    for i in range(0, len(data) - 3, 4):
        val = struct.unpack_from('<I', data, i)[0]
        if val == target_val:
            locations.append(i)
    return locations

def main():
    print("="*80)
    print("RESISTANCE VALUE CHANGE ANALYSIS")
    print("="*80)
    
    files = [
        ('sch5.oa', 'R0 = 2K (first time)', 70),
        ('sch9.oa', 'R1 = 2K (string exists)', 124),
        ('sch10.oa', 'R1 = 3K (new string)', 126),
        ('sch14.oa', 'Mystery file', 136),
    ]
    
    print("\n" + "="*80)
    print("PROPERTY VALUE ID SUMMARY")
    print("="*80)
    
    for filename, description, expected_id in files:
        pvs = get_property_values(filename)
        print(f"\n{filename} - {description}")
        print(f"  Expected Property Value ID: {expected_id}")
        print(f"  Found {len(pvs)} PropertyValueRecords:")
        for pv in pvs:
            marker = " <-- TARGET" if pv['value_id'] == expected_id else ""
            print(f"    Offset 0x{pv['offset']:04x}: ID {pv['value_id']:3d}{marker}")
    
    print("\n" + "="*80)
    print("RAW BYTE LOCATIONS OF PROPERTY VALUE IDs")
    print("="*80)
    
    for filename, description, expected_id in files:
        data = get_table_0xc(filename)
        locations = find_value_in_bytes(data, expected_id)
        print(f"\n{filename} - Property Value ID {expected_id}:")
        for loc in locations:
            context_start = max(0, loc - 12)
            context_end = min(len(data), loc + 16)
            hex_str = ' '.join(f'{b:02x}' for b in data[context_start:context_end])
            print(f"  Offset 0x{loc:04x}: {hex_str}")
    
    print("\n" + "="*80)
    print("BYTE-LEVEL DIFF: sch9 (2K) → sch10 (3K)")
    print("="*80)
    
    data9 = get_table_0xc('sch9.oa')
    data10 = get_table_0xc('sch10.oa')
    
    print(f"\nTable sizes: sch9={len(data9)} bytes, sch10={len(data10)} bytes")
    
    if len(data9) == len(data10):
        print("Tables are same size - checking differences:")
        diffs = []
        for i in range(len(data9)):
            if data9[i] != data10[i]:
                diffs.append((i, data9[i], data10[i]))
        
        print(f"Found {len(diffs)} byte differences:")
        for offset, old_val, new_val in diffs[:20]:  # Show first 20
            context_start = max(0, offset - 8)
            context_end = min(len(data9), offset + 8)
            old_context = ' '.join(f'{b:02x}' for b in data9[context_start:context_end])
            new_context = ' '.join(f'{b:02x}' for b in data10[context_start:context_end])
            print(f"\n  Offset 0x{offset:04x}:")
            print(f"    sch9:  {old_context}")
            print(f"    sch10: {new_context}")
            print(f"    Change: 0x{old_val:02x} → 0x{new_val:02x} (124=0x7c, 126=0x7e)")
    
    print("\n" + "="*80)
    print("PATTERN ANALYSIS: Property Value ID Increments")
    print("="*80)
    
    print("\nObserved sequence:")
    print("  sch5:  ID  70 - R0 = 2K (new string added)")
    print("  sch9:  ID 124 - R1 = 2K (string reused, but NEW property value ID)")
    print("  sch10: ID 126 - R1 = 3K (delta +2 from 124)")
    print("  sch14: ID 136 - Mystery (delta +10 from 126)")
    
    print("\nKey insights:")
    print("  1. Property Value IDs are NOT string offsets")
    print("  2. Same string value can have different Property Value IDs")
    print("  3. IDs increment by +2 for simple property changes")
    print("  4. IDs track modification history, not just final values")
    
    print("\n" + "="*80)

if __name__ == '__main__':
    main()
