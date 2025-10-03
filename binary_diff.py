#!/usr/bin/env python3
"""
Binary diff tool that detects insertions, deletions, and modifications
between two binary files, accounting for byte shifts.

For .oa files, this tool is table-aware and compares tables individually.
"""

import sys
import struct
from difflib import SequenceMatcher
from typing import List, Tuple, BinaryIO, Optional, Dict

def read_binary_file(filepath: str) -> bytes:
    """Read a binary file and return its contents."""
    with open(filepath, 'rb') as f:
        return f.read()

class OaFile:
    """Parser for .oa file table structure."""
    def __init__(self, filepath: str):
        self.filepath = filepath
        self.tables = {}
        try:
            with open(filepath, 'rb') as f:
                # Read the 24-byte header
                header = f.read(24)
                _, _, _, _, _, used = struct.unpack('<IHHQII', header)

                # Read the table directory (IDs, Offsets, Sizes)
                ids = list(struct.unpack(f'<{used}Q', f.read(8 * used)))
                offsets = list(struct.unpack(f'<{used}Q', f.read(8 * used)))
                sizes = list(struct.unpack(f'<{used}Q', f.read(8 * used)))

                # Store table info in a dictionary keyed by ID
                for i in range(used):
                    # Skip tables with invalid offsets
                    if offsets[i] != 0xffffffffffffffff:
                        self.tables[ids[i]] = {
                            'offset': offsets[i], 
                            'size': sizes[i], 
                            'data': None
                        }

                # Read the raw data for each table
                for table_id, info in self.tables.items():
                    f.seek(info['offset'])
                    info['data'] = f.read(info['size'])

        except Exception as e:
            raise RuntimeError(f"Error parsing {filepath}: {e}")

def is_oa_file(filepath: str) -> bool:
    """Check if a file is an .oa file by extension or header."""
    if filepath.endswith('.oa'):
        return True
    try:
        with open(filepath, 'rb') as f:
            header = f.read(24)
            if len(header) == 24:
                # Try to parse as OA header
                struct.unpack('<IHHQII', header)
                return True
    except:
        pass
    return False

def format_bytes(data: bytes, max_len: int = 16) -> str:
    """Format bytes as hex string with ASCII representation."""
    hex_str = ' '.join(f'{b:02x}' for b in data[:max_len])
    ascii_str = ''.join(chr(b) if 32 <= b < 127 else '.' for b in data[:max_len])
    if len(data) > max_len:
        hex_str += '...'
        ascii_str += '...'
    return f"{hex_str:48s} |{ascii_str}|"

def format_compact(data: bytes, max_len: int = 32) -> str:
    """Format bytes compactly."""
    s = ' '.join(f'{b:02x}' for b in data[:max_len])
    return s + '...' if len(data) > max_len else s

def binary_diff(data1: bytes, data2: bytes, context: int = 8) -> List[Tuple[str, int, int, bytes, bytes]]:
    """
    Compare two binary streams and return differences.
    
    Args:
        data1: First binary stream
        data2: Second binary stream
        context: Number of bytes of context to show around changes
    
    Returns:
        List of tuples: (operation, offset1, offset2, bytes1, bytes2)
        operation: 'equal', 'replace', 'delete', 'insert'
    """
    # Use SequenceMatcher for efficient diff
    matcher = SequenceMatcher(None, data1, data2, autojunk=False)
    
    differences = []
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        differences.append((tag, i1, i2, data1[i1:i2], data2[j1:j2]))
    
    return differences

def print_diff(differences: List[Tuple[str, int, int, bytes, bytes]], 
               show_equal: bool = False, max_equal_bytes: int = 32):
    """Print differences in a compact format."""
    total_changes = sum(1 for d in differences if d[0] != 'equal')
    print(f"Operations: {len(differences)}, Changes: {total_changes}")
    
    for tag, i1, i2, bytes1, bytes2 in differences:
        size1 = i2 - i1
        size2 = len(bytes2)
        
        if tag == 'equal':
            if show_equal:
                suffix = f" (first {max_equal_bytes})" if size1 > max_equal_bytes else ""
                print(f"[{i1:08x}] = {size1}b{suffix}: equal bytes")
                print(f"  = {format_compact(bytes1)}")
        elif tag == 'replace':
            sz = f" [{size2-size1:+d}]" if size1 != size2 else ""
            print(f"[{i1:08x}] ~ {size1}->{size2}b{sz}: replaced {size1} bytes")
            print(f"  - {format_compact(bytes1)}")
            print(f"  + {format_compact(bytes2)}")
        elif tag == 'delete':
            print(f"[{i1:08x}] - {size1}b: deleted {size1} bytes")
            print(f"  - {format_compact(bytes1)}")
        elif tag == 'insert':
            print(f"[{i1:08x}] + {size2}b: inserted {size2} bytes")
            print(f"  + {format_compact(bytes2)}")

def print_summary(differences: List[Tuple[str, int, int, bytes, bytes]]):
    """Print a compact summary of changes."""
    stats = {'replace': 0, 'delete': 0, 'insert': 0, 
             'bytes_replaced': 0, 'bytes_deleted': 0, 'bytes_inserted': 0}
    
    for tag, i1, i2, bytes1, bytes2 in differences:
        if tag == 'replace':
            stats['replace'] += 1
            stats['bytes_replaced'] += len(bytes1)
        elif tag == 'delete':
            stats['delete'] += 1
            stats['bytes_deleted'] += len(bytes1)
        elif tag == 'insert':
            stats['insert'] += 1
            stats['bytes_inserted'] += len(bytes2)
    
    print(f"\nReplace: {stats['replace']} ops, {stats['bytes_replaced']} bytes")
    print(f"Delete:  {stats['delete']} ops, {stats['bytes_deleted']} bytes")
    print(f"Insert:  {stats['insert']} ops, {stats['bytes_inserted']} bytes")
    print(f"Net:     {stats['bytes_inserted'] - stats['bytes_deleted']:+d} bytes")

def diff_oa_files(file1: str, file2: str, show_equal: bool = False):
    """Diff two .oa files table by table."""
    print(f"--- Table-aware diff: {file1} (OLD) vs {file2} (NEW) ---\n")
    
    try:
        oa_old = OaFile(file1)
        oa_new = OaFile(file2)
    except Exception as e:
        print(f"Error parsing OA files: {e}")
        sys.exit(1)
    
    # Get all table IDs from both files
    all_ids = sorted(list(set(oa_old.tables.keys()) | set(oa_new.tables.keys())))
    
    total_tables = len(all_ids)
    changed_tables = 0
    
    for table_id in all_ids:
        table_old = oa_old.tables.get(table_id)
        table_new = oa_new.tables.get(table_id)
        
        # Handle missing tables
        if table_old is None:
            print(f"[*] Table 0x{table_id:x} - ADDED in NEW")
            print(f"    Size: {table_new['size']}b\n")
            changed_tables += 1
            continue
        
        if table_new is None:
            print(f"[*] Table 0x{table_id:x} - REMOVED in OLD")
            print(f"    Size: {table_old['size']}b\n")
            changed_tables += 1
            continue
        
        # Compare table data
        data_old = table_old['data']
        data_new = table_new['data']
        
        if data_old == data_new:
            continue  # Skip identical tables
        
        changed_tables += 1
        print(f"[*] Table 0x{table_id:x} - MODIFIED")
        print(f"    OLD: offset=0x{table_old['offset']:x}, size={table_old['size']}b")
        print(f"    NEW: offset=0x{table_new['offset']:x}, size={table_new['size']}b")
        print(f"    Diff: {len(data_new) - len(data_old):+d}b")
        
        # Run binary diff on table data
        differences = binary_diff(data_old, data_new)
        print_diff(differences, show_equal=show_equal)
        print_summary(differences)
        print()
    
    print(f"Summary: {changed_tables}/{total_tables} tables changed")

def main():
    if len(sys.argv) < 3:
        print("Usage: python binary_diff.py <file1> <file2> [--show-equal]")
        print()
        print("For .oa files: performs table-aware comparison")
        print("For other files: performs byte-level comparison")
        sys.exit(1)
    
    file1, file2 = sys.argv[1], sys.argv[2]
    show_equal = '--show-equal' in sys.argv
    
    try:
        # Check if both files are .oa files
        if is_oa_file(file1) and is_oa_file(file2):
            diff_oa_files(file1, file2, show_equal)
        else:
            # Standard binary diff
            data1 = read_binary_file(file1)
            data2 = read_binary_file(file2)
            print(f"{file1}: {len(data1)}b, {file2}: {len(data2)}b, diff: {len(data2)-len(data1):+d}b")
            differences = binary_diff(data1, data2)
            print_diff(differences, show_equal=show_equal)
            print_summary(differences)
    except FileNotFoundError as e:
        print(f"Error: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)

if __name__ == '__main__':
    main()
