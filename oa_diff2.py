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

def format_hex_ascii(data: bytes, max_len: int = 32) -> str:
    """Format bytes as hex with ASCII, like hexdump."""
    s = ' '.join(f'{b:02x}' for b in data[:max_len])
    ascii_str = ''.join(chr(b) if 32 <= b < 127 else '.' for b in data[:max_len])
    if len(data) > max_len:
        s += '...'
        ascii_str += '...'
    return f"{s:<96} |{ascii_str}|"

def binary_diff(data1: bytes, data2: bytes) -> List[Tuple[str, int, int, bytes, bytes]]:
    """
    Compare two binary streams and return differences.
    
    Returns:
        List of tuples: (operation, offset1, offset2, bytes1, bytes2)
        operation: 'equal', 'replace', 'delete', 'insert'
    """
    matcher = SequenceMatcher(None, data1, data2, autojunk=False)
    differences = []
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        differences.append((tag, i1, i2, data1[i1:i2], data2[j1:j2]))
    return differences

def print_diff(differences: List[Tuple[str, int, int, bytes, bytes]], 
               context: str = 'none', context_bytes: int = 16):
    """
    Print differences in a compact format.
    
    Args:
        context: 'none', 'medium', or 'full'
        context_bytes: Number of bytes to show around changes for 'medium' context
    """
    total_changes = sum(1 for d in differences if d[0] != 'equal')
    print(f"Operations: {len(differences)}, Changes: {total_changes}")
    
    for tag, i1, i2, bytes1, bytes2 in differences:
        size1 = i2 - i1
        size2 = len(bytes2)
        
        if tag == 'equal':
            if context == 'full':
                # Show all equal bytes in full context mode
                chunk_size = 32
                for offset in range(0, size1, chunk_size):
                    chunk = bytes1[offset:offset + chunk_size]
                    print(f"[{i1+offset:08x}]   {format_hex_ascii(chunk)}")
            elif context == 'medium':
                # Show limited context around changes
                if size1 <= context_bytes * 2:
                    # Show all if small enough
                    print(f"[{i1:08x}]   {format_hex_ascii(bytes1[:context_bytes])}")
                else:
                    # Show first and last context_bytes
                    print(f"[{i1:08x}]   {format_hex_ascii(bytes1[:context_bytes])}")
                    if size1 > context_bytes * 2:
                        print(f"         ... ({size1 - context_bytes * 2} bytes omitted) ...")
                    print(f"[{i2-context_bytes:08x}]   {format_hex_ascii(bytes1[-context_bytes:])}")
        
        elif tag == 'replace':
            sz = f" [{size2-size1:+d}]" if size1 != size2 else ""
            print(f"[{i1:08x}] ~ {size1}->{size2}b{sz}: replaced {size1} bytes")
            print(f"  - {format_hex_ascii(bytes1)}")
            print(f"  + {format_hex_ascii(bytes2)}")
        
        elif tag == 'delete':
            print(f"[{i1:08x}] - {size1}b: deleted {size1} bytes")
            print(f"  - {format_hex_ascii(bytes1)}")
        
        elif tag == 'insert':
            print(f"[{i1:08x}] + {size2}b: inserted {size2} bytes")
            print(f"  + {format_hex_ascii(bytes2)}")

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

def diff_oa_files(file1: str, file2: str, context: str = 'none', context_bytes: int = 16):
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
        print_diff(differences, context=context, context_bytes=context_bytes)
        print_summary(differences)
        print()
    
    print(f"Summary: {changed_tables}/{total_tables} tables changed")

def main():
    if len(sys.argv) < 3:
        print("Usage: python oa_diff2.py <file1> <file2> [options]")
        print()
        print("Options:")
        print("  --context=none     No context (default, only show changes)")
        print("  --context=medium   Show context around changes")
        print("  --context=full     Show all bytes including unchanged")
        print("  --context-bytes=N  Context size for medium mode (default: 16)")
        print()
        print("For .oa files: performs table-aware comparison")
        print("For other files: performs byte-level comparison")
        sys.exit(1)
    
    file1, file2 = sys.argv[1], sys.argv[2]
    
    # Parse options
    context = 'full'
    context_bytes = 16
    
    for arg in sys.argv[3:]:
        if arg.startswith('--context='):
            context = arg.split('=')[1]
            if context not in ['none', 'medium', 'full']:
                print(f"Invalid context mode: {context}")
                sys.exit(1)
        elif arg.startswith('--context-bytes='):
            try:
                context_bytes = int(arg.split('=')[1])
            except ValueError:
                print(f"Invalid context-bytes value: {arg}")
                sys.exit(1)
    
    try:
        # Check if both files are .oa files
        if is_oa_file(file1) and is_oa_file(file2):
            diff_oa_files(file1, file2, context=context, context_bytes=context_bytes)
        else:
            # Standard binary diff
            data1 = read_binary_file(file1)
            data2 = read_binary_file(file2)
            print(f"{file1}: {len(data1)}b, {file2}: {len(data2)}b, diff: {len(data2)-len(data1):+d}b")
            differences = binary_diff(data1, data2)
            print_diff(differences, context=context, context_bytes=context_bytes)
            print_summary(differences)
    except FileNotFoundError as e:
        print(f"Error: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)

if __name__ == '__main__':
    main()
