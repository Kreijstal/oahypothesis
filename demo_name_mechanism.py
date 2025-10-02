#!/usr/bin/env python3
"""
Demonstration of the name/value reference mechanism.

This script provides concrete examples of how property value changes
are stored in the .oa file format, with visual representation of the
string table and reference offsets.
"""

import struct
from analyze_name_references import read_oa_file, parse_string_table


def visualize_string_table_region(strings, start_offset, end_offset):
    """
    Create a visual representation of a region of the string table.
    """
    print("\n" + "="*80)
    print(f"STRING TABLE REGION (offsets 0x{start_offset:04x} - 0x{end_offset:04x})")
    print("="*80)
    
    for offset, string in sorted(strings.items()):
        if start_offset <= offset <= end_offset:
            print(f"  0x{offset:04x} ({offset:4d}): \"{string}\"")


def show_table_c_reference(table_c_data, offset, strings):
    """
    Show what a specific reference in table 0xc points to.
    """
    # Read 16-bit value at offset
    stored_value = struct.unpack_from('<H', table_c_data, offset)[0]
    
    # Apply +1 offset pattern
    actual_offset = stored_value - 1
    
    # Lookup string
    resolved_string = strings.get(actual_offset, "[NOT FOUND]")
    
    print(f"\n  Table 0xc offset 0x{offset:04x}:")
    print(f"    Stored value:  0x{stored_value:04x} ({stored_value})")
    print(f"    Actual offset: 0x{actual_offset:04x} ({actual_offset}) [stored - 1]")
    print(f"    Resolved:      \"{resolved_string}\"")
    
    return stored_value, actual_offset, resolved_string


def demo_property_value_change():
    """
    Demonstrate the property value change mechanism using sch13 and sch14.
    """
    print("="*80)
    print("DEMONSTRATION: Property Value Change (Resistance 3K → 2K)")
    print("="*80)
    print("\nFiles: sch13.oa → sch14.oa")
    print("Change: R1 resistance changed from 3K to 2K")
    
    # Load both files
    old_tables = read_oa_file('sch13.oa')
    new_tables = read_oa_file('sch14.oa')
    
    # Parse string tables
    old_strings = parse_string_table(old_tables[0x0a]['data'])
    new_strings = parse_string_table(new_tables[0x0a]['data'])
    
    # Show relevant region of string table
    print("\n" + "="*80)
    print("STEP 1: String Table Contents")
    print("="*80)
    visualize_string_table_region(old_strings, 980, 1150)
    
    # Show the reference in table 0xc
    print("\n" + "="*80)
    print("STEP 2: Reference in Table 0xC (OLD FILE)")
    print("="*80)
    old_stored, old_actual, old_string = show_table_c_reference(
        old_tables[0x0c]['data'], 
        0x0798,  # This is where the reference is
        old_strings
    )
    
    print("\n" + "="*80)
    print("STEP 3: Reference in Table 0xC (NEW FILE)")
    print("="*80)
    new_stored, new_actual, new_string = show_table_c_reference(
        new_tables[0x0c]['data'], 
        0x0798,
        new_strings
    )
    
    # Show the change
    print("\n" + "="*80)
    print("STEP 4: What Changed")
    print("="*80)
    print(f"\n  String reference at table 0xc offset 0x0798:")
    print(f"    OLD: 0x{old_stored:04x} → offset 0x{old_actual:04x} → \"{old_string}\"")
    print(f"    NEW: 0x{new_stored:04x} → offset 0x{new_actual:04x} → \"{new_string}\"")
    print(f"\n  Stored value changed by: {new_stored - old_stored:+d} bytes")
    print(f"  Actual offset changed by: {new_actual - old_actual:+d} bytes")
    
    # Show Property Value IDs
    print("\n" + "="*80)
    print("STEP 5: Property Value ID Change")
    print("="*80)
    
    old_pv_id = struct.unpack_from('<I', old_tables[0x0c]['data'], 0x0364)[0]
    new_pv_id = struct.unpack_from('<I', new_tables[0x0c]['data'], 0x0364)[0]
    
    print(f"\n  Property Value ID at offset 0x0364:")
    print(f"    OLD: {old_pv_id} (0x{old_pv_id:02x})")
    print(f"    NEW: {new_pv_id} (0x{new_pv_id:02x})")
    print(f"    DELTA: +{new_pv_id - old_pv_id}")
    
    # Summary
    print("\n" + "="*80)
    print("SUMMARY")
    print("="*80)
    print("""
When the resistance value changed from "3K" to "2K":

1. Both strings already existed in the string table at different offsets
2. The 16-bit reference at table 0xc offset 0x0798 was updated:
   - Changed from 0x0476 (pointing to "3K" at offset 0x0475)
   - Changed to 0x03de (pointing to "2K" at offset 0x03dd)
3. The Property Value ID was incremented from 133 to 136 (+3)
4. No new strings were added to the string table (both values already existed)

This demonstrates the core mechanism: property values are referenced by
16-bit offsets (with +1 encoding) in table 0xc, and changing a value
simply updates the offset to point to the new string's location.
""")


def demo_string_reuse():
    """
    Demonstrate how the format reuses existing strings.
    """
    print("\n" + "="*80)
    print("DEMONSTRATION: String Reuse Mechanism")
    print("="*80)
    
    # Compare sch13 and sch14 string tables
    old_tables = read_oa_file('sch13.oa')
    new_tables = read_oa_file('sch14.oa')
    
    old_strings = parse_string_table(old_tables[0x0a]['data'])
    new_strings = parse_string_table(new_tables[0x0a]['data'])
    
    print(f"\nString table in sch13.oa: {len(old_strings)} strings")
    print(f"String table in sch14.oa: {len(new_strings)} strings")
    
    if old_strings == new_strings:
        print("\n✓ String tables are IDENTICAL")
        print("\nThis proves that when changing from '3K' to '2K', the format")
        print("did NOT add a new string. Instead, it reused the existing '2K'")
        print("string that was already in the table from a previous operation.")
        print("\nBenefit: This minimizes file size growth by avoiding duplicates.")


def demo_offset_pattern():
    """
    Demonstrate the +1 offset pattern.
    """
    print("\n" + "="*80)
    print("DEMONSTRATION: +1 Offset Pattern")
    print("="*80)
    
    print("""
The .oa format uses a "+1 offset pattern" for string references.

WHY? To distinguish between:
  - 0x0000: A null/invalid reference
  - 0x0001: A valid reference to offset 0 in the string table

ENCODING:
  stored_value = actual_string_offset + 1

DECODING:
  actual_string_offset = stored_value - 1

EXAMPLE:
  String "2K" is at offset 0x03dd (989) in the string table.
  In table 0xc, it's stored as 0x03de (990).
  
  To decode: 990 - 1 = 989 → lookup string at offset 989 → "2K"
  
This prevents confusion when a string happens to be at the very
beginning of the string heap (offset 0).
""")


if __name__ == '__main__':
    print("""
╔══════════════════════════════════════════════════════════════════════════════╗
║                                                                              ║
║   OA FILE FORMAT: Name/Value Reference Mechanism Demonstration              ║
║                                                                              ║
║   This demo shows exactly how component property values are stored           ║
║   and updated in Cadence .oa files.                                          ║
║                                                                              ║
╚══════════════════════════════════════════════════════════════════════════════╝
""")
    
    # Run demonstrations
    demo_property_value_change()
    demo_string_reuse()
    demo_offset_pattern()
    
    print("\n" + "="*80)
    print("DEMONSTRATION COMPLETE")
    print("="*80)
    print("\nFor more details, see:")
    print("  - NAME_REFERENCE_MECHANISM.md")
    print("  - analyze_name_references.py")
    print("\nTo analyze other file pairs:")
    print("  python3 analyze_name_references.py <old_file.oa> <new_file.oa>")
    print()
