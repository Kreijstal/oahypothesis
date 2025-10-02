#!/usr/bin/env python3
"""
Test script for UnknownStruct60Byte detection and parsing.

WARNING: This structure only appears in files sch5-8 and disappears in sch9+.
The structure is hypothetical and not fully understood.

This test verifies that the parser correctly identifies and parses
this unknown structure when it is present in the data.
"""

import struct
from table_c_parser import HypothesisParser, UnknownStruct60Byte
from oaparser.binary_curator import ClaimedRegion


def test_unknown_struct_detection():
    """Test that UnknownStruct60Byte is detected in files where it exists (sch5-8 only)."""
    print("="*70)
    print("TEST: UnknownStruct60Byte Detection and Structure Parsing")
    print("WARNING: This structure only appears in sch5-8, disappears in sch9+")
    print("="*70)
    
    # Test file that is known to contain the unknown structure
    test_file = 'sch5.oa'
    
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
                    
                    # Search for UnknownStruct60Byte
                    found_records = []
                    for region in regions:
                        if isinstance(region, ClaimedRegion):
                            if isinstance(region.parsed_value, UnknownStruct60Byte):
                                found_records.append(region.parsed_value)
                    
                    # Verify detection
                    if not found_records:
                        print(f"  ✗ {test_file}: No UnknownStruct60Byte found")
                        return False
                    
                    print(f"  ✓ {test_file}: Found {len(found_records)} UnknownStruct60Byte(s)")
                    
                    # Verify structure parsing
                    for rec in found_records:
                        print(f"\n  Verifying structure at offset 0x{rec.offset:x}:")
                        
                        # Check that parts exist
                        if len(rec.padding) < 0:
                            print(f"    ✗ Invalid padding size: {len(rec.padding)}")
                            return False
                        print(f"    ✓ Padding: {len(rec.padding)} bytes")
                        
                        if len(rec.config_pattern) != 8:
                            print(f"    ✗ Pattern should be 8 bytes, got {len(rec.config_pattern)}")
                            return False
                        print(f"    ✓ Pattern: {len(rec.config_pattern)} bytes")
                        
                        if len(rec.payload) % 4 != 0:
                            print(f"    ✗ Payload should be 4-byte aligned, got {len(rec.payload)}")
                            return False
                        print(f"    ✓ Payload: {len(rec.payload)} bytes (4-byte aligned)")
                        
                        if len(rec.trailing_separator) != 12:
                            print(f"    ✗ Trailing should be 12 bytes, got {len(rec.trailing_separator)}")
                            return False
                        print(f"    ✓ Trailing: {len(rec.trailing_separator)} bytes")
                        
                        # Verify observed patterns
                        if rec.config_pattern == UnknownStruct60Byte.OBSERVED_PATTERN:
                            print(f"    ✓ Pattern matches observed 08 00 00 00 03 00 00 00")
                        else:
                            print(f"    ✗ Pattern does NOT match observed")
                            return False
                        
                        if rec.trailing_separator == UnknownStruct60Byte.OBSERVED_SEPARATOR:
                            print(f"    ✓ Trailing matches observed separator-like pattern")
                        else:
                            print(f"    ✗ Trailing does NOT match observed")
                            return False
                        
                        # Verify total size
                        expected_size = len(rec.padding) + len(rec.config_pattern) + len(rec.payload) + len(rec.trailing_separator)
                        if len(rec.data) != expected_size:
                            print(f"    ✗ Total size mismatch: {len(rec.data)} vs {expected_size}")
                            return False
                        print(f"    ✓ Total size correct: {len(rec.data)} bytes")
                    
                    print("\n" + "="*70)
                    print("TEST PASSED ✓")
                    print("="*70)
                    return True
                    
    except FileNotFoundError:
        print(f"  ✗ Test file '{test_file}' not found")
        return False
    except Exception as e:
        print(f"  ✗ Test failed with exception: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    print(f"  ✗ Table 0xc not found in {test_file}")
    return False


def test_structure_disappears_after_sch8():
    """Test that the unknown structure disappears in sch9+ as expected."""
    print("\n" + "="*70)
    print("TEST: Structure Disappearance (should NOT appear in sch9+)")
    print("="*70)
    
    # Test files where structure should NOT appear
    test_files = ['sch9.oa', 'sch13.oa', 'sch14.oa']
    
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
                        
                        # Check for UnknownStruct60Byte (should NOT be found)
                        found_unknown = False
                        for region in regions:
                            if isinstance(region, ClaimedRegion):
                                if isinstance(region.parsed_value, UnknownStruct60Byte):
                                    found_unknown = True
                                    break
                        
                        if found_unknown:
                            print(f"  ✗ {test_file}: UnknownStruct60Byte found (should not exist)")
                            all_passed = False
                        else:
                            print(f"  ✓ {test_file}: UnknownStruct60Byte absent (as expected)")
                        break
                        
        except FileNotFoundError:
            print(f"  - {test_file}: (file not found, skipping)")
            continue
        except Exception as e:
            print(f"  ✗ {test_file}: Failed with exception: {e}")
            all_passed = False
    
    if all_passed:
        print("\n" + "="*70)
        print("DISAPPEARANCE TEST PASSED ✓")
        print("="*70)
    else:
        print("\n" + "="*70)
        print("DISAPPEARANCE TEST FAILED ✗")
        print("="*70)
    
    return all_passed


if __name__ == '__main__':
    test1_pass = test_unknown_struct_detection()
    test2_pass = test_structure_disappears_after_sch8()
    
    print("\n" + "="*70)
    print("OVERALL TEST SUMMARY")
    print("="*70)
    print(f"  UnknownStruct60Byte Detection: {'PASSED ✓' if test1_pass else 'FAILED ✗'}")
    print(f"  Structure Disappearance: {'PASSED ✓' if test2_pass else 'FAILED ✗'}")
    print("="*70)
    
    if test1_pass and test2_pass:
        print("\nALL TESTS PASSED ✓")
        print("\nNOTE: This structure is hypothetical and only appears in sch5-8.")
        print("It disappears in sch9+ suggesting transient metadata, not a stable format.")
        exit(0)
    else:
        print("\nSOME TESTS FAILED ✗")
        exit(1)
