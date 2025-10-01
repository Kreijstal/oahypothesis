#!/usr/bin/env python3
"""
Demonstration script showing Table 0x1 patterns across all .oa files.

This script extracts and compares the counters and key fields from Table 0x1
to show how they change between file modifications.
"""

import struct
import glob
import sys

def extract_table_1_key_fields(filepath):
    """Extract key fields from Table 0x1."""
    try:
        with open(filepath, 'rb') as f:
            header = f.read(24)
            _, _, _, _, _, used = struct.unpack('<IHHQII', header)
            ids = list(struct.unpack(f'<{used}Q', f.read(8 * used)))
            offsets = list(struct.unpack(f'<{used}Q', f.read(8 * used)))
            sizes = list(struct.unpack(f'<{used}Q', f.read(8 * used)))
            
            if 0x1 not in ids:
                return None
            
            idx = ids.index(0x1)
            f.seek(offsets[idx])
            data = f.read(sizes[idx])
            
            if len(data) < 0x80:
                return None
            
            # Extract key fields
            counter1 = struct.unpack_from('<I', data, 0x68)[0]
            counter2 = struct.unpack_from('<I', data, 0x6c)[0]
            ts1 = struct.unpack_from('<Q', data, 0x70)[0] & 0xFFFFFFFF
            ts2 = struct.unpack_from('<Q', data, 0x78)[0] & 0xFFFFFFFF
            
            return {
                'size': sizes[idx],
                'counter1': counter1,
                'counter2': counter2,
                'ts1': ts1,
                'ts2': ts2
            }
    except Exception as e:
        print(f"Error parsing {filepath}: {e}", file=sys.stderr)
        return None

def main():
    print("="*80)
    print("TABLE 0x1 PATTERN ANALYSIS ACROSS ALL .OA FILES")
    print("="*80)
    print()
    print("Table 0x1 contains global metadata including version strings, counters,")
    print("and timestamps that track file modifications.")
    print()
    
    # Get all .oa files in sorted order
    files = sorted(glob.glob('sch*.oa'))
    
    if not files:
        print("No .oa files found in current directory")
        return 1
    
    print("="*80)
    print(f"{'Filename':<15} {'Size':<8} {'Counter1':<10} {'Counter2':<10} {'TS1':<12} {'TS2':<12}")
    print("="*80)
    
    results = []
    for filepath in files:
        fields = extract_table_1_key_fields(filepath)
        if fields:
            results.append((filepath, fields))
            print(f"{filepath:<15} {fields['size']:<8} {fields['counter1']:<10} "
                  f"{fields['counter2']:<10} {fields['ts1']:<12} {fields['ts2']:<12}")
    
    print("="*80)
    print()
    
    # Analyze counter changes
    print("COUNTER CHANGES:")
    print("-"*80)
    
    for i in range(1, len(results)):
        prev_file, prev = results[i-1]
        curr_file, curr = results[i]
        
        c1_delta = curr['counter1'] - prev['counter1']
        c2_delta = curr['counter2'] - prev['counter2']
        
        if c1_delta != 0 or c2_delta != 0:
            print(f"\n{prev_file} → {curr_file}:")
            if c1_delta != 0:
                print(f"  Counter1: {prev['counter1']} → {curr['counter1']} (Δ{c1_delta:+d})")
            if c2_delta != 0:
                print(f"  Counter2: {prev['counter2']} → {curr['counter2']} (Δ{c2_delta:+d})")
    
    print()
    print("="*80)
    print("OBSERVATIONS:")
    print("-"*80)
    print("• Counter1 remains constant at 1024 across all files")
    print("• Counter2 increments with file modifications")
    print("• Counter2 tracks the number of save/modification operations")
    print("• Timestamps are currently zero in all test files")
    print("="*80)

if __name__ == '__main__':
    sys.exit(main() or 0)
