#!/usr/bin/env python3
"""
Binary diff tool that detects insertions, deletions, and modifications
between two binary files, accounting for byte shifts.
"""

import sys
from difflib import SequenceMatcher
from typing import List, Tuple, BinaryIO

def read_binary_file(filepath: str) -> bytes:
    """Read a binary file and return its contents."""
    with open(filepath, 'rb') as f:
        return f.read()

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

def main():
    if len(sys.argv) < 3:
        print("Usage: python binary_diff.py <file1> <file2> [--show-equal]")
        sys.exit(1)
    
    file1, file2 = sys.argv[1], sys.argv[2]
    show_equal = '--show-equal' in sys.argv
    
    try:
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
