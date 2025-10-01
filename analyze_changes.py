#!/usr/bin/env python3
"""
Analyze meaningful data changes between sch_old.oa and sch_new.oa
"""
import sys
import struct

def analyze_table_0xa(data1, data2):
    """Analyze string table changes"""
    print("\n=== Table 0xa (String Table) Analysis ===")
    print(f"Size: {len(data1)} -> {len(data2)} (diff: {len(data2)-len(data1)})")
    
    # Parse header
    header1 = struct.unpack('<IIII', data1[:16])
    header2 = struct.unpack('<IIII', data2[:16])
    
    print(f"\nHeader changes:")
    print(f"  Entry count: {header1[1]} -> {header2[1]} (diff: {header2[1]-header1[1]})")
    
    # Extract strings
    def get_strings(data):
        strings = []
        buffer = data[20:]  # Skip 20-byte header
        pos = 0
        while pos < len(buffer):
            try:
                null_pos = buffer.index(b'\0', pos)
                if buffer[pos:null_pos]:
                    strings.append((pos, buffer[pos:null_pos].decode('utf-8', 'ignore')))
                pos = null_pos + 1
            except ValueError:
                break
        return strings
    
    strings1 = get_strings(data1)
    strings2 = get_strings(data2)
    
    print(f"\nStrings: {len(strings1)} -> {len(strings2)}")
    
    # Find new strings
    str_set1 = set(s[1] for s in strings1)
    str_set2 = set(s[1] for s in strings2)
    
    new_strings = str_set2 - str_set1
    if new_strings:
        print(f"\nNew strings added ({len(new_strings)}):")
        for s in new_strings:
            print(f"  - '{s}'")
    
    removed_strings = str_set1 - str_set2
    if removed_strings:
        print(f"\nStrings removed ({len(removed_strings)}):")
        for s in removed_strings:
            print(f"  - '{s}'")

def analyze_table_0x1(data1, data2):
    """Analyze metadata table changes"""
    print("\n=== Table 0x1 (Metadata) Analysis ===")
    print(f"Size: {len(data1)} -> {len(data2)} (same size)")
    
    # Find timestamp changes (timestamps are 32-bit unix timestamps)
    print("\nLooking for timestamp changes...")
    
    # Check specific offsets that changed
    changed_offsets = [0x6c, 0x7c, 0x7d, 0x998, 0x9b4, 0x9b5, 0x9c8, 0xa38]
    
    for offset in changed_offsets:
        if offset + 4 <= len(data1):
            old_val = struct.unpack('<I', data1[offset:offset+4])[0]
            new_val = struct.unpack('<I', data2[offset:offset+4])[0]
            
            # Check if it looks like a timestamp (year 2000+)
            if old_val > 946684800 and new_val > 946684800:
                from datetime import datetime
                old_time = datetime.utcfromtimestamp(old_val).strftime('%Y-%m-%d %H:%M:%S')
                new_time = datetime.utcfromtimestamp(new_val).strftime('%Y-%m-%d %H:%M:%S')
                print(f"  Offset 0x{offset:04x}: {old_time} -> {new_time}")

def analyze_table_0xb(data1, data2):
    """Analyze property list changes"""
    print("\n=== Table 0xb (Property Lists) Analysis ===")
    print(f"Size: {len(data1)} -> {len(data2)} (same size)")
    
    # Check the changed offsets
    changed_offsets = [0xdc, 0xfb, 0x122, 0x123]
    
    print("\nChanged values (possibly string references):")
    for offset in changed_offsets:
        if offset < len(data1):
            old_val = data1[offset]
            new_val = data2[offset]
            print(f"  Offset 0x{offset:04x}: 0x{old_val:02x} -> 0x{new_val:02x} (decimal: {old_val} -> {new_val})")
    
    # Check if 0x0736 (string ID for THISISNOWTHERESISTOR) appears
    # String IDs are typically 32-bit values
    for i in range(0, len(data2)-4, 4):
        val = struct.unpack('<I', data2[i:i+4])[0]
        if val == 0x0736:
            print(f"\n  Found string ID 0x0736 at offset 0x{i:04x}!")

def analyze_table_0x107(data1, data2):
    """Analyze version counter changes"""
    print("\n=== Table 0x107 (Version Counters) Analysis ===")
    print(f"Size: {len(data1)} -> {len(data2)} (same size)")
    
    # Check the changed offsets
    changed_offsets = [0x2b9, 0x2e8]
    
    print("\nVersion counter changes:")
    for offset in changed_offsets:
        if offset < len(data1):
            old_val = data1[offset]
            new_val = data2[offset]
            print(f"  Offset 0x{offset:04x}: {old_val} -> {new_val} (incremented by {new_val-old_val})")
            print(f"    This likely tracks modifications to a specific component")

def main():
    if len(sys.argv) != 3:
        print(f"Usage: {sys.argv[0]} <file1.oa> <file2.oa>")
        sys.exit(1)
    
    file1, file2 = sys.argv[1], sys.argv[2]
    
    # Read both files
    def read_tables(filepath):
        tables = {}
        with open(filepath, 'rb') as f:
            header = f.read(24)
            _, _, _, _, _, used = struct.unpack('<IHHQII', header)
            ids = list(struct.unpack(f'<{used}Q', f.read(8 * used)))
            offsets = list(struct.unpack(f'<{used}Q', f.read(8 * used)))
            sizes = list(struct.unpack(f'<{used}Q', f.read(8 * used)))
            
            for i in range(used):
                if offsets[i] != 0xffffffffffffffff:
                    f.seek(offsets[i])
                    tables[ids[i]] = f.read(sizes[i])
        return tables
    
    print(f"Analyzing changes between {file1} and {file2}\n")
    
    tables1 = read_tables(file1)
    tables2 = read_tables(file2)
    
    # Analyze each changed table
    if 0xa in tables1 and 0xa in tables2:
        analyze_table_0xa(tables1[0xa], tables2[0xa])
    
    if 0x1 in tables1 and 0x1 in tables2:
        analyze_table_0x1(tables1[0x1], tables2[0x1])
    
    if 0xb in tables1 and 0xb in tables2:
        analyze_table_0xb(tables1[0xb], tables2[0xb])
    
    if 0x107 in tables1 and 0x107 in tables2:
        analyze_table_0x107(tables1[0x107], tables2[0x107])
    
    print("\n" + "="*70)
    print("Summary of Meaningful Changes:")
    print("="*70)
    print("""
1. String Table (0xa): New string "THISISNOWTHERESISTOR" added
   - This is the new resistor name after renaming from "popop"
   
2. Metadata (0x1): Timestamps updated
   - Multiple timestamp fields updated to reflect the save time
   
3. Property Lists (0xb): String references updated  
   - References to string IDs modified to point to new string
   - This links the resistor component to its new name
   
4. Version Counters (0x107): Component version incremented
   - Tracks that the resistor component was modified
   - Used for change tracking and consistency checks
   
All changes are consistent with a simple rename operation:
- Add new string to string table
- Update property references to use new string
- Increment version counter for modified component
- Update timestamps to reflect save time
""")

if __name__ == '__main__':
    main()
