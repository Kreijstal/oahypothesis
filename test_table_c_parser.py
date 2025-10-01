#!/usr/bin/env python3
"""
Comprehensive test suite for Table 0xC parsing improvements.

Tests:
1. Timestamp extraction (regression test)
2. Property value detection and parsing
3. Comparison between known file pairs
"""

import sys
import struct
from table_c_parser import HypothesisParser, PropertyValueRecord, TimestampRecord

def test_timestamps():
    """Test that timestamps are correctly extracted from all files."""
    print("="*70)
    print("TEST 1: Timestamp Extraction")
    print("="*70)
    
    expected = {
        'sch_old.oa': 1759219482,
        'sch_new.oa': 1759220368,
        'sch2.oa': 1759220630,
        'sch3.oa': 1759267303,
        'sch4.oa': 1759268290,
        'sch5.oa': 1759269165,
        'sch6.oa': 1759269681,
        'sch7.oa': 1759269898,
        'sch8.oa': 1759270115,
        'sch9.oa': 1759354688,
        'sch10.oa': 1759354769,
        'sch11.oa': 1759354797,
        'sch12.oa': 1759354903,
        'sch13.oa': 1759354958,
        'sch14.oa': 1759356124,
    }
    
    all_passed = True
    for filename, expected_ts in expected.items():
        try:
            with open(filename, 'rb') as f:
                header = f.read(24)
                _, _, _, _, _, used = struct.unpack('<IHHQII', header)
                ids = list(struct.unpack(f'<{used}Q', f.read(8 * used)))
                offsets = list(struct.unpack(f'<{used}Q', f.read(8 * used)))
                sizes = list(struct.unpack(f'<{used}Q', f.read(8 * used)))
                
                for i in range(used):
                    if ids[i] == 0x0c:
                        f.seek(offsets[i])
                        data = f.read(sizes[i])
                        parser = HypothesisParser(data)
                        parser.parse()
                        
                        found_ts = None
                        for record in parser.records:
                            if isinstance(record, TimestampRecord):
                                found_ts = record.timestamp_val & 0xFFFFFFFF
                                break
                        
                        if found_ts == expected_ts:
                            print(f"  ✓ {filename}: {found_ts}")
                        else:
                            print(f"  ✗ {filename}: Expected {expected_ts}, got {found_ts}")
                            all_passed = False
                        break
        except Exception as e:
            print(f"  ✗ {filename}: Error - {e}")
            all_passed = False
    
    return all_passed

def test_property_value_detection():
    """Test that property values are correctly detected."""
    print("\n" + "="*70)
    print("TEST 2: Property Value Detection")
    print("="*70)
    
    test_cases = [
        ('sch4.oa', 68),   # Resistance at 1K
        ('sch5.oa', 70),   # Resistance at 2K (ID changed by +2)
        ('sch6.oa', 76),   # Changed to capacitor
        ('sch7.oa', 76),   # Added R1
        ('sch9.oa', 124),  # R1 set to 2K (reusing string)
        ('sch10.oa', 126), # R1 changed to 3K (ID changed by +2)
        ('sch14.oa', 136), # Mystery file
    ]
    
    all_passed = True
    for filename, expected_id in test_cases:
        try:
            with open(filename, 'rb') as f:
                header = f.read(24)
                _, _, _, _, _, used = struct.unpack('<IHHQII', header)
                ids = list(struct.unpack(f'<{used}Q', f.read(8 * used)))
                offsets = list(struct.unpack(f'<{used}Q', f.read(8 * used)))
                sizes = list(struct.unpack(f'<{used}Q', f.read(8 * used)))
                
                for i in range(used):
                    if ids[i] == 0x0c:
                        f.seek(offsets[i])
                        data = f.read(sizes[i])
                        parser = HypothesisParser(data)
                        parser.parse()
                        
                        prop_vals = [r.property_value_id for r in parser.records 
                                    if isinstance(r, PropertyValueRecord)]
                        
                        if expected_id in prop_vals:
                            print(f"  ✓ {filename}: Found property value ID {expected_id}")
                        else:
                            print(f"  ✗ {filename}: Expected ID {expected_id}, found {prop_vals}")
                            all_passed = False
                        break
        except Exception as e:
            print(f"  ✗ {filename}: Error - {e}")
            all_passed = False
    
    return all_passed

def test_property_value_changes():
    """Test that property value changes are detected between file pairs."""
    print("\n" + "="*70)
    print("TEST 3: Property Value Change Detection")
    print("="*70)
    
    test_cases = [
        # (file1, file2, expected_change)
        ('sch4.oa', 'sch5.oa', True),   # Resistance changed
        ('sch_old.oa', 'sch_new.oa', False),  # Just rename, no value change
        ('sch7.oa', 'sch8.oa', False),  # Wire added, no property change
        ('sch9.oa', 'sch10.oa', True),  # R1: 2K → 3K (124 → 126)
        ('sch10.oa', 'sch11.oa', True), # Different component changed
        ('sch13.oa', 'sch14.oa', True), # Mystery change
    ]
    
    all_passed = True
    for file1, file2, expected_change in test_cases:
        try:
            # Extract property values from both files
            def get_prop_vals(filename):
                with open(filename, 'rb') as f:
                    header = f.read(24)
                    _, _, _, _, _, used = struct.unpack('<IHHQII', header)
                    ids = list(struct.unpack(f'<{used}Q', f.read(8 * used)))
                    offsets = list(struct.unpack(f'<{used}Q', f.read(8 * used)))
                    sizes = list(struct.unpack(f'<{used}Q', f.read(8 * used)))
                    
                    for i in range(used):
                        if ids[i] == 0x0c:
                            f.seek(offsets[i])
                            data = f.read(sizes[i])
                            parser = HypothesisParser(data)
                            parser.parse()
                            return [(r.offset, r.property_value_id) for r in parser.records 
                                   if isinstance(r, PropertyValueRecord)]
                return []
            
            vals1 = get_prop_vals(file1)
            vals2 = get_prop_vals(file2)
            
            # Check if property values at same offsets changed
            dict1 = dict(vals1)
            dict2 = dict(vals2)
            common_offsets = set(dict1.keys()) & set(dict2.keys())
            
            has_change = any(dict1[off] != dict2[off] for off in common_offsets)
            
            if has_change == expected_change:
                status = "change detected" if has_change else "no change"
                print(f"  ✓ {file1} → {file2}: {status} (as expected)")
            else:
                print(f"  ✗ {file1} → {file2}: Expected change={expected_change}, got {has_change}")
                all_passed = False
                
        except Exception as e:
            print(f"  ✗ {file1} → {file2}: Error - {e}")
            all_passed = False
    
    return all_passed

def main():
    print("\nTable 0xC Parser Test Suite")
    print("="*70)
    
    results = []
    results.append(("Timestamp Extraction", test_timestamps()))
    results.append(("Property Value Detection", test_property_value_detection()))
    results.append(("Property Value Changes", test_property_value_changes()))
    
    print("\n" + "="*70)
    print("TEST SUMMARY")
    print("="*70)
    for name, passed in results:
        status = "PASSED" if passed else "FAILED"
        print(f"  {name}: {status}")
    
    all_passed = all(r[1] for r in results)
    print("\n" + "="*70)
    if all_passed:
        print("ALL TESTS PASSED ✓")
        return 0
    else:
        print("SOME TESTS FAILED ✗")
        return 1

if __name__ == '__main__':
    sys.exit(main())
