#!/usr/bin/env python3
"""
Compare Table 0xC property values between two .oa files.

This script specifically highlights property value ID changes, which indicate
modifications to component properties like resistance values.
"""

import sys
import struct
from table_c_parser import HypothesisParser, PropertyValueRecord

def extract_table_c(filename):
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

def extract_property_values(filename):
    """Extract all property value IDs from a file's Table 0xC."""
    data = extract_table_c(filename)
    if not data:
        return []
    
    parser = HypothesisParser(data)
    parser.parse()
    
    property_values = []
    for record in parser.records:
        if isinstance(record, PropertyValueRecord):
            property_values.append({
                'offset': record.offset,
                'value_id': record.property_value_id,
                'size': record.size
            })
    
    return property_values

def compare_files(file1, file2):
    """Compare property values between two files."""
    print(f"Comparing {file1} (OLD) with {file2} (NEW)")
    print("="*70)
    
    pv1 = extract_property_values(file1)
    pv2 = extract_property_values(file2)
    
    print(f"\nFound {len(pv1)} PropertyValueRecords in {file1}")
    print(f"Found {len(pv2)} PropertyValueRecords in {file2}")
    
    # Compare by offset
    print("\n" + "="*70)
    print("Property Value Changes by Offset:")
    print("="*70)
    
    # Create dictionaries keyed by offset
    pv1_dict = {pv['offset']: pv for pv in pv1}
    pv2_dict = {pv['offset']: pv for pv in pv2}
    
    # Find all offsets
    all_offsets = sorted(set(pv1_dict.keys()) | set(pv2_dict.keys()))
    
    changes_found = False
    for offset in all_offsets:
        old_val = pv1_dict.get(offset, {}).get('value_id', None)
        new_val = pv2_dict.get(offset, {}).get('value_id', None)
        
        if old_val is None and new_val is not None:
            print(f"\nOffset 0x{offset:04x}: [ADDED] -> Property Value ID {new_val}")
            changes_found = True
        elif old_val is not None and new_val is None:
            print(f"\nOffset 0x{offset:04x}: Property Value ID {old_val} -> [REMOVED]")
            changes_found = True
        elif old_val != new_val:
            print(f"\nOffset 0x{offset:04x}: Property Value ID {old_val} -> {new_val}")
            print(f"                Change: {new_val - old_val:+d}")
            changes_found = True
    
    if not changes_found:
        print("\nNo property value changes detected.")
    
    print("\n" + "="*70)

if __name__ == '__main__':
    if len(sys.argv) != 3:
        print("Usage: python compare_property_values.py <file1.oa> <file2.oa>")
        sys.exit(1)
    
    compare_files(sys.argv[1], sys.argv[2])
