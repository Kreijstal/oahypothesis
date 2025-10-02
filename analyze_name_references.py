#!/usr/bin/env python3
"""
Analyze where component names and property values are referenced in .oa files.

This script answers the question: "What is the mechanism that updates a name??? 
Where is the name of the component referenced?!"

It traces how string offsets are stored and updated in table 0xc when property 
values change (like resistance changing from "3K" to "2K").
"""

import struct
import sys
from typing import Dict, List, Tuple, Optional


def read_oa_file(filepath: str) -> Dict:
    """Parse an .oa file and extract all tables."""
    with open(filepath, 'rb') as f:
        # Read header
        header = f.read(24)
        magic, _, _, _, _, used = struct.unpack('<IHHQII', header)
        
        if magic != 0x01234567:
            raise ValueError(f"Invalid .oa file magic: 0x{magic:08x}")
        
        # Read table directory
        ids = list(struct.unpack(f'<{used}Q', f.read(8 * used)))
        offsets = list(struct.unpack(f'<{used}Q', f.read(8 * used)))
        sizes = list(struct.unpack(f'<{used}Q', f.read(8 * used)))
        
        # Read all tables
        tables = {}
        for i in range(used):
            if offsets[i] != 0xffffffffffffffff and sizes[i] > 0:
                f.seek(offsets[i])
                tables[ids[i]] = {
                    'offset': offsets[i],
                    'size': sizes[i],
                    'data': f.read(sizes[i])
                }
        
        return tables


def parse_string_table(data: bytes) -> Dict[int, str]:
    """Parse table 0xa and return a dict mapping offsets to strings."""
    # Skip 20-byte header
    string_buffer = data[20:]
    
    strings = {}
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
                strings[current_offset] = decoded
            except UnicodeDecodeError:
                strings[current_offset] = f'[DECODE ERROR: {string_data!r}]'
        
        current_offset = null_pos + 1
    
    return strings


def find_string_references_in_table(table_data: bytes, strings: Dict[int, str], 
                                    min_offset: int = 100) -> List[Tuple[int, int, str]]:
    """
    Scan a table for 16-bit values that could be string offsets.
    Returns list of (table_offset, string_offset, resolved_string) tuples.
    
    Note: The .oa format uses a "+1 offset pattern" where stored values are
    actual_offset + 1, so we check both offset and offset-1.
    """
    references = []
    
    for table_offset in range(0, len(table_data) - 1, 2):
        # Read 16-bit little-endian value
        stored_value = struct.unpack_from('<H', table_data, table_offset)[0]
        
        # Skip small values that are unlikely to be string offsets
        if stored_value < min_offset or stored_value > 4096:
            continue
        
        # Try both the exact offset and offset-1 (accounting for +1 pattern)
        for test_offset in [stored_value, stored_value - 1]:
            if test_offset in strings:
                string = strings[test_offset]
                # Only report meaningful strings (length > 1)
                if len(string) > 1:
                    references.append((table_offset, stored_value, string))
                    break  # Found a match, don't check offset-1
    
    return references


def compare_string_references(old_refs: List[Tuple[int, int, str]], 
                               new_refs: List[Tuple[int, int, str]]) -> None:
    """Compare string references between two files and print differences."""
    # Build dicts for easier comparison
    old_dict = {table_off: (str_off, string) for table_off, str_off, string in old_refs}
    new_dict = {table_off: (str_off, string) for table_off, str_off, string in new_refs}
    
    # Find all unique table offsets
    all_offsets = sorted(set(old_dict.keys()) | set(new_dict.keys()))
    
    changes_found = False
    
    for table_offset in all_offsets:
        old_info = old_dict.get(table_offset)
        new_info = new_dict.get(table_offset)
        
        if old_info != new_info:
            changes_found = True
            print(f"\n[CHANGE] At table offset 0x{table_offset:04x}:")
            
            if old_info and new_info:
                old_str_off, old_str = old_info
                new_str_off, new_str = new_info
                print(f"  OLD: String offset 0x{old_str_off:04x} → '{old_str}'")
                print(f"  NEW: String offset 0x{new_str_off:04x} → '{new_str}'")
                
                offset_diff = new_str_off - old_str_off
                print(f"  DELTA: {offset_diff:+d} bytes (0x{abs(offset_diff):04x})")
            elif old_info:
                old_str_off, old_str = old_info
                print(f"  REMOVED: String offset 0x{old_str_off:04x} → '{old_str}'")
            else:
                new_str_off, new_str = new_info
                print(f"  ADDED: String offset 0x{new_str_off:04x} → '{new_str}'")
    
    if not changes_found:
        print("\n  No changes found in string references.")


def analyze_property_value_changes(old_data: bytes, new_data: bytes) -> None:
    """Analyze property value ID changes in table 0xc."""
    print("\n" + "="*80)
    print("PROPERTY VALUE ID CHANGES")
    print("="*80)
    
    # Property Value Records in table 0xc have a specific structure
    # We scan for any 4-byte integer changes that could be property value IDs
    
    changes = []
    min_len = min(len(old_data), len(new_data))
    
    # Scan for changed 4-byte values
    for offset in range(0, min_len - 3, 1):  # Check every byte, not just aligned
        if old_data[offset:offset+4] == new_data[offset:offset+4]:
            continue
            
        old_val = struct.unpack_from('<I', old_data, offset)[0]
        new_val = struct.unpack_from('<I', new_data, offset)[0]
        
        # Look for small positive integer changes (likely property value IDs)
        # Property value IDs are typically in range 50-200 based on observations
        if 50 <= old_val <= 300 and 50 <= new_val <= 300:
            delta = new_val - old_val
            # Property value IDs typically change by small amounts (1-10)
            if 1 <= abs(delta) <= 10:
                changes.append((offset, old_val, new_val))
    
    if changes:
        # Remove duplicates (same value, different byte alignment)
        seen = set()
        unique_changes = []
        for offset, old_id, new_id in changes:
            key = (old_id, new_id)
            if key not in seen:
                seen.add(key)
                unique_changes.append((offset, old_id, new_id))
        
        print(f"\nFound {len(unique_changes)} property value ID change(s):")
        for offset, old_id, new_id in unique_changes:
            print(f"\n  At offset 0x{offset:04x}:")
            print(f"    OLD ID: {old_id} (0x{old_id:02x})")
            print(f"    NEW ID: {new_id} (0x{new_id:02x})")
            print(f"    DELTA: {new_id - old_id:+d}")
    else:
        print("\nNo property value ID changes detected.")


def main():
    if len(sys.argv) != 3:
        print("Usage: python3 analyze_name_references.py <old_file.oa> <new_file.oa>")
        print("\nExample:")
        print("  python3 analyze_name_references.py sch13.oa sch14.oa")
        print("\nThis script analyzes how component names and property values are")
        print("referenced in table 0xc and shows what changes when values are updated.")
        sys.exit(1)
    
    old_file = sys.argv[1]
    new_file = sys.argv[2]
    
    print("="*80)
    print(f"ANALYZING NAME/VALUE REFERENCE MECHANISM")
    print("="*80)
    print(f"\nComparing: {old_file} → {new_file}")
    
    # Parse both files
    print("\n[1/5] Reading files...")
    old_tables = read_oa_file(old_file)
    new_tables = read_oa_file(new_file)
    
    # Parse string tables
    print("[2/5] Parsing string tables...")
    old_strings = parse_string_table(old_tables[0x0a]['data'])
    new_strings = parse_string_table(new_tables[0x0a]['data'])
    
    print(f"  OLD: {len(old_strings)} strings")
    print(f"  NEW: {len(new_strings)} strings")
    
    # Check if string tables are identical
    if old_strings == new_strings:
        print("  ✓ String tables are IDENTICAL (no new strings added)")
    else:
        print("  ✗ String tables differ")
        # Show new strings
        new_only = set(new_strings.values()) - set(old_strings.values())
        if new_only:
            print(f"    New strings added: {new_only}")
    
    # Find string references in multiple tables
    print("[3/5] Finding string references in key tables...")
    
    # Check table 0xc (Core Netlist Data)
    old_refs_c = find_string_references_in_table(
        old_tables[0x0c]['data'], 
        old_strings
    )
    new_refs_c = find_string_references_in_table(
        new_tables[0x0c]['data'], 
        new_strings
    )
    
    print(f"  Table 0xc: {len(old_refs_c)} → {len(new_refs_c)} string references")
    
    # Check table 0x1 (metadata table with property references)
    old_refs_1 = find_string_references_in_table(
        old_tables[0x1]['data'], 
        old_strings
    )
    new_refs_1 = find_string_references_in_table(
        new_tables[0x1]['data'], 
        new_strings
    )
    
    print(f"  Table 0x1: {len(old_refs_1)} → {len(new_refs_1)} string references")
    
    # Compare references
    print("[4/5] Comparing references...")
    
    print("\n" + "="*80)
    print("STRING REFERENCE CHANGES IN TABLE 0xC (Core Netlist Data)")
    print("="*80)
    compare_string_references(old_refs_c, new_refs_c)
    
    print("\n" + "="*80)
    print("STRING REFERENCE CHANGES IN TABLE 0x1 (Metadata)")
    print("="*80)
    compare_string_references(old_refs_1, new_refs_1)
    
    # Analyze property value IDs
    print("[5/5] Analyzing property value IDs...")
    analyze_property_value_changes(
        old_tables[0x0c]['data'],
        new_tables[0x0c]['data']
    )
    
    print("\n" + "="*80)
    print("SUMMARY: HOW NAME/VALUE UPDATES WORK")
    print("="*80)
    print("""
The mechanism for updating component property values (like resistance):

1. **String Storage**: All strings (including property values like "2K", "3K")
   are stored in Table 0xa (String Table) as null-terminated strings.

2. **String References**: Table 0xc (Core Netlist Data) contains 16-bit offsets
   that point to strings in the string table. These offsets use a "+1 pattern"
   where the stored value is (actual_string_offset + 1).

3. **Property Value IDs**: Each property assignment gets a unique Property Value
   ID that increments with each modification. These IDs appear in Property Value
   Records within table 0xc.

4. **Update Mechanism**: When a property value changes (e.g., "3K" → "2K"):
   a) The string reference offset in table 0xc is updated to point to the new
      string's offset in the string table.
   b) The Property Value ID is incremented to track the modification.
   c) If the new string doesn't exist, it's added to table 0xa first.

5. **String Reuse**: The format reuses existing strings when possible. If "2K"
   already exists in the string table, it's referenced rather than duplicated.

This explains why string table offsets must be updated when property values
change, and why the offset delta corresponds to the position difference between
the old and new strings in the string table heap.
""")


if __name__ == '__main__':
    main()
