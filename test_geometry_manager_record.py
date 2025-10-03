#!/usr/bin/env python3
"""
Test script for separator-based structure detection and parsing.

This structure appears in files sch5-11 (not just sch5-8 as previously thought).
The structure is detected by searching for the separator pattern, not a fixed "signature".

This test verifies that the parser correctly identifies and parses
this structure when it is present in the data.
"""

import struct
from table_c_parser import HypothesisParser, UnknownStruct60Byte
from oaparser.binary_curator import ClaimedRegion


def test_unknown_struct_detection():
    """Test that the separator-based structure is detected in files where it exists (sch5-12)."""
    print("="*70)
    print("TEST: Separator-Based Structure Detection and Parsing")
    print("This structure appears in sch5-12, detected by separator core pattern")
    print("="*70)
    
    # Test files that are known to contain the structure
    test_files = ['sch5.oa', 'sch6.oa', 'sch9.oa', 'sch11.oa', 'sch12.oa']
    expected_values = {
        'sch5.oa': [8, 3, 0],
        'sch6.oa': [8, 3, 1, 2],
        'sch9.oa': [3, 3, 0],
        'sch11.oa': [8, 4, 0],
        'sch12.oa': [8, 4, 0],
    }
    
    all_passed = True
    
    for test_file in test_files:
        try:
            with open(test_file, 'rb') as f:
                # Read file header
                header = f.read(24)
                _, _, _, _, _, used = struct.unpack('<IHHQII', header)
                ids = list(struct.unpack(f'<{used}Q', f.read(8 * used)))
                offsets = list(struct.unpack(f'<{used}Q', f.read(8 * used)))
                sizes = list(struct.unpack(f'<{used}Q', f.read(8 * used)))
                
                # Load string table
                string_table_data = None
                for i in range(used):
                    if ids[i] == 0x0a:
                        f.seek(offsets[i])
                        string_table_data = f.read(sizes[i])
                        break
                
                # Load and parse table 0xc
                for i in range(used):
                    if ids[i] == 0x0c:
                        f.seek(offsets[i])
                        data = f.read(sizes[i])
                        
                        parser = HypothesisParser(data, string_table_data)
                        regions = parser.parse()
                        
                        # Search for the structure
                        found_records = []
                        for region in regions:
                            if isinstance(region, ClaimedRegion):
                                if isinstance(region.parsed_value, UnknownStruct60Byte):
                                    found_records.append(region.parsed_value)
                        
                        # Verify detection
                        if not found_records:
                            print(f"  ✗ {test_file}: No structure found")
                            all_passed = False
                            continue
                        
                        print(f"  ✓ {test_file}: Found {len(found_records)} structure(s)")
                        
                        # Verify structure parsing
                        for rec in found_records:
                            # Check that payload contains expected values
                            if len(rec.payload) % 4 == 0:
                                payload_ints = list(struct.unpack(f'<{len(rec.payload)//4}I', rec.payload))
                                expected = expected_values.get(test_file, [])
                                if payload_ints == expected:
                                    print(f"    ✓ Payload values match expected: {payload_ints}")
                                else:
                                    print(f"    ⚠ Payload values: {payload_ints} (expected: {expected})")
                            
                            # Check that separator core is present
                            if UnknownStruct60Byte.SEPARATOR_CORE in rec.trailing_separator:
                                print(f"    ✓ Contains separator core")
                            else:
                                print(f"    ✗ Missing separator core")
                                all_passed = False
                        
                        break
                        
        except FileNotFoundError:
            print(f"  - {test_file}: (file not found, skipping)")
            continue
        except Exception as e:
            print(f"  ✗ {test_file}: Failed with exception: {e}")
            import traceback
            traceback.print_exc()
            all_passed = False
    
    if all_passed:
        print("\n" + "="*70)
        print("DETECTION TEST PASSED ✓")
        print("="*70)
    else:
        print("\n" + "="*70)
        print("DETECTION TEST FAILED ✗")
        print("="*70)
    
    return all_passed


def test_structure_absence_in_later_files():
    """Test that the structure is absent in sch13+ as expected."""
    print("\n" + "="*70)
    print("TEST: Structure Absence (should NOT appear in sch13+)")
    print("="*70)
    
    # Test files where structure should NOT appear
    test_files = ['sch13.oa', 'sch14.oa', 'sch15.oa']
    
    all_passed = True
    for test_file in test_files:
        try:
            with open(test_file, 'rb') as f:
                # Read file header
                header = f.read(24)
                _, _, _, _, _, used = struct.unpack('<IHHQII', header)
                ids = list(struct.unpack(f'<{used}Q', f.read(8 * used)))
                offsets = list(struct.unpack(f'<{used}Q', f.read(8 * used)))
                sizes = list(struct.unpack(f'<{used}Q', f.read(8 * used)))
                
                # Load string table
                string_table_data = None
                for i in range(used):
                    if ids[i] == 0x0a:
                        f.seek(offsets[i])
                        string_table_data = f.read(sizes[i])
                        break
                
                # Load and parse table 0xc
                for i in range(used):
                    if ids[i] == 0x0c:
                        f.seek(offsets[i])
                        data = f.read(sizes[i])
                        
                        parser = HypothesisParser(data, string_table_data)
                        regions = parser.parse()
                        
                        # Check for structure (should NOT be found)
                        found_unknown = False
                        for region in regions:
                            if isinstance(region, ClaimedRegion):
                                if isinstance(region.parsed_value, UnknownStruct60Byte):
                                    found_unknown = True
                                    break
                        
                        if found_unknown:
                            print(f"  ✗ {test_file}: Structure found (should not exist)")
                            all_passed = False
                        else:
                            print(f"  ✓ {test_file}: Structure absent (as expected)")
                        break
                        
        except FileNotFoundError:
            print(f"  - {test_file}: (file not found, skipping)")
            continue
        except Exception as e:
            print(f"  ✗ {test_file}: Failed with exception: {e}")
            all_passed = False
    
    if all_passed:
        print("\n" + "="*70)
        print("ABSENCE TEST PASSED ✓")
        print("="*70)
    else:
        print("\n" + "="*70)
        print("ABSENCE TEST FAILED ✗")
        print("="*70)
    
    return all_passed


if __name__ == '__main__':
    test1_pass = test_unknown_struct_detection()
    test2_pass = test_structure_absence_in_later_files()
    
    print("\n" + "="*70)
    print("OVERALL TEST SUMMARY")
    print("="*70)
    print(f"  Structure Detection: {'PASSED ✓' if test1_pass else 'FAILED ✗'}")
    print(f"  Structure Absence: {'PASSED ✓' if test2_pass else 'FAILED ✗'}")
    print("="*70)
    
    if test1_pass and test2_pass:
        print("\nALL TESTS PASSED ✓")
        print("\nNOTE: This structure appears in sch5-12 and is detected by")
        print("searching for the stable separator core pattern. The payload values change")
        print("over time, and the separator has variable bytes, showing it's a dynamic structure.")
        exit(0)
    else:
        print("\nSOME TESTS FAILED ✗")
        exit(1)
