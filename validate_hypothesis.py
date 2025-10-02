#!/usr/bin/env python3
"""
Validation script to test the hypothesis about table 0xc string references.

Hypothesis: The values in table 0xc are property value IDs that map to records
in table 0xb, which in turn reference strings in table 0xa.

The formula appears to be:
- Each record in table 0xb represents a property assignment
- The property value ID in table 0xc = (number of records in table 0xb) * 4 - 1
  Or more precisely: property_value_id increases by 3 with each new record
"""

import struct
import sys

def parse_table(filename, table_id):
    """Extract a specific table from an .oa file"""
    with open(filename, 'rb') as f:
        header = f.read(24)
        _, _, _, _, _, used = struct.unpack('<IHHQII', header)
        ids = list(struct.unpack(f'<{used}Q', f.read(8 * used)))
        offsets = list(struct.unpack(f'<{used}Q', f.read(8 * used)))
        sizes = list(struct.unpack(f'<{used}Q', f.read(8 * used)))
        
        for i in range(used):
            if ids[i] == table_id:
                f.seek(offsets[i])
                return f.read(sizes[i])
    return None

def parse_string_table(filename):
    """Extract all strings from table 0xa"""
    data = parse_table(filename, 0xa)
    if not data or len(data) < 20:
        return []
    
    # Skip 20-byte header
    string_buffer = data[20:]
    strings = []
    current_offset = 0
    
    while current_offset < len(string_buffer):
        try:
            null_pos = string_buffer.index(b'\x00', current_offset)
        except ValueError:
            break
        
        string_data = string_buffer[current_offset:null_pos]
        if string_data:
            try:
                decoded = string_data.decode('utf-8')
                strings.append((current_offset, decoded))
            except UnicodeDecodeError:
                pass
        
        current_offset = null_pos + 1
    
    return strings

def count_property_records(filename):
    """Count the number of records in table 0xb"""
    data = parse_table(filename, 0xb)
    if not data or len(data) < 0xdc + 4:
        return None
    
    # Record count is at offset 0xdc
    count = struct.unpack('<I', data[0xdc:0xdc+4])[0]
    return count

def find_property_value_in_table_c(filename):
    """Find property value IDs in table 0xc"""
    data = parse_table(filename, 0xc)
    if not data:
        return []
    
    # Search for the pattern at offset 0x6a0 (where we saw the change)
    # The pattern is: XX 00 00 00 <property_value_id> 00 00 00
    values = []
    
    # Check the specific location we know about
    if len(data) > 0x6a4:
        val = data[0x6a4]  # Byte at offset 0x6a4
        values.append(('0x6a4', val))
    
    # Also check for repeating patterns
    if len(data) > 0x6ac:
        val = data[0x6ac]  # Byte at offset 0x6ac (8 bytes later)
        values.append(('0x6ac', val))
    
    return values

def validate_file(filename):
    """Validate hypothesis for a single file"""
    print(f"\n{'='*70}")
    print(f"Validating: {filename}")
    print('='*70)
    
    # Get data
    strings = parse_string_table(filename)
    record_count = count_property_records(filename)
    property_values = find_property_value_in_table_c(filename)
    
    print(f"String table: {len(strings)} strings")
    print(f"Table 0xb: {record_count} property records")
    
    # Calculate expected property value ID
    if record_count:
        expected_id = record_count * 4 - 1
        print(f"Expected property value ID: {expected_id} (0x{expected_id:02x})")
    
    print(f"\nProperty value IDs found in table 0xc:")
    for location, value in property_values:
        print(f"  At {location}: {value} (0x{value:02x})")
        
        # Try to resolve this to a string
        if value < len(strings):
            offset, string = strings[value]
            print(f"    -> String at index {value}: \"{string}\"")
        else:
            print(f"    -> Index {value} out of range (max {len(strings)-1})")
    
    # Check if the formula holds
    if record_count and property_values:
        for location, value in property_values:
            expected = record_count * 4 - 1
            if value == expected:
                print(f"\n✓ HYPOTHESIS CONFIRMED: {value} == {record_count} * 4 - 1")
            else:
                print(f"\n✗ HYPOTHESIS FAILED: {value} != {record_count} * 4 - 1 = {expected}")
                print(f"  Difference: {value - expected}")

if __name__ == '__main__':
    test_files = [
        'sch_old.oa',
        'sch_new.oa',
        'sch2.oa',
        'sch3.oa',
        'sch4.oa',
    ]
    
    for filename in test_files:
        try:
            validate_file(filename)
        except Exception as e:
            print(f"Error processing {filename}: {e}")
            import traceback
            traceback.print_exc()
