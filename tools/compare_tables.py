#!/usr/bin/env python3
"""
Compare tables between two .oa files to identify changes
"""
import sys
import os
# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import struct
from parsers.table_a_parser import TableAParser

def read_oa_file(filepath):
    """Read .oa file and return table information"""
    tables = {}
    
    with open(filepath, 'rb') as f:
        # Read header
        header = f.read(24)
        _, _, _, _, _, used = struct.unpack('<IHHQII', header)
        
        # Read table directory
        ids = list(struct.unpack(f'<{used}Q', f.read(8 * used)))
        offsets = list(struct.unpack(f'<{used}Q', f.read(8 * used)))
        sizes = list(struct.unpack(f'<{used}Q', f.read(8 * used)))
        
        # Store table info
        for i in range(used):
            if offsets[i] != 0xffffffffffffffff and sizes[i] > 0:
                f.seek(offsets[i])
                data = f.read(sizes[i])
                tables[ids[i]] = {
                    'offset': offsets[i],
                    'size': sizes[i],
                    'data': data
                }
    
    return tables

def compare_tables(file1, file2):
    """Compare tables between two .oa files"""
    print(f"Comparing: {file1} vs {file2}\n")
    
    tables1 = read_oa_file(file1)
    tables2 = read_oa_file(file2)
    
    all_table_ids = sorted(set(tables1.keys()) | set(tables2.keys()))
    
    print(f"Total unique tables: {len(all_table_ids)}")
    print(f"Tables in {file1}: {len(tables1)}")
    print(f"Tables in {file2}: {len(tables2)}")
    print()
    
    # Find tables that only exist in one file
    only_in_1 = set(tables1.keys()) - set(tables2.keys())
    only_in_2 = set(tables2.keys()) - set(tables1.keys())
    
    if only_in_1:
        print(f"Tables only in {file1}:")
        for tid in sorted(only_in_1):
            print(f"  0x{tid:x} (size: {tables1[tid]['size']})")
        print()
    
    if only_in_2:
        print(f"Tables only in {file2}:")
        for tid in sorted(only_in_2):
            print(f"  0x{tid:x} (size: {tables2[tid]['size']})")
        print()
    
    # Find tables that changed
    changed_tables = []
    unchanged_tables = []
    
    for tid in sorted(set(tables1.keys()) & set(tables2.keys())):
        t1 = tables1[tid]
        t2 = tables2[tid]
        
        if t1['data'] != t2['data']:
            changed_tables.append({
                'id': tid,
                'size1': t1['size'],
                'size2': t2['size'],
                'size_diff': t2['size'] - t1['size']
            })
        else:
            unchanged_tables.append(tid)
    
    print(f"Tables that changed: {len(changed_tables)}")
    print(f"Tables unchanged: {len(unchanged_tables)}")
    print()
    
    if changed_tables:
        print("Changed tables (sorted by size difference):")
        print(f"{'Table ID':<12} {'Size Old':<12} {'Size New':<12} {'Diff':<12} {'Notes'}")
        print("="*70)
        
        for entry in sorted(changed_tables, key=lambda x: abs(x['size_diff']), reverse=True):
            tid = entry['id']
            table_name = get_table_name(tid)
            
            print(f"0x{tid:<10x} {entry['size1']:<12} {entry['size2']:<12} "
                  f"{entry['size_diff']:+12} {table_name}")

            # If this is the string table, show the added strings
            if tid == 0xa:
                parser1 = TableAParser(tables1[tid]['data'])
                parser1.parse()
                strings1 = {s['string'] for s in parser1.strings}

                parser2 = TableAParser(tables2[tid]['data'])
                parser2.parse()
                strings2 = {s['string'] for s in parser2.strings}

                added_strings = strings2 - strings1
                if added_strings:
                    print(f"    {'':<12} {'Added strings:'}")
                    for s in sorted(list(added_strings))[:5]: # Show first 5
                        print(f"    {'':<14} - \"{s}\"")

    return changed_tables, unchanged_tables

def get_table_name(tid):
    """Get a human-readable name for known table IDs"""
    known_tables = {
        0x1: "Metadata",
        0xa: "String Table",
        0xb: "Property Lists",
        0xc: "Netlist Data",
        0xd: "Unknown",
        0xe: "Unknown",
        0x101: "Unknown",
        0x105: "Component Instances",
        0x107: "Version Counters",
        0x109: "Unknown"
    }
    return known_tables.get(tid, "")

if __name__ == '__main__':
    if len(sys.argv) != 3:
        print(f"Usage: {sys.argv[0]} <file1.oa> <file2.oa>")
        sys.exit(1)
    
    compare_tables(sys.argv[1], sys.argv[2])
