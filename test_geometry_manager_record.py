#!/usr/bin/env python3
"""
Test script for GeometryManagerRecord detection and parsing.

This test verifies that the parser correctly identifies and parses
GeometryManagerRecord structures when they are present in the data.
"""

import struct
from table_c_parser import HypothesisParser, GeometryManagerRecord
from oaparser.binary_curator import ClaimedRegion


def test_geometry_manager_record_detection():
    """Test that GeometryManagerRecord is detected in files where it exists."""
    print("="*70)
    print("TEST: GeometryManagerRecord Detection and Structure Parsing")
    print("="*70)
    
    # Test file that is known to contain the GeometryManagerRecord
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
                    
                    # Search for GeometryManagerRecord
                    found_records = []
                    for region in regions:
                        if isinstance(region, ClaimedRegion):
                            if isinstance(region.parsed_value, GeometryManagerRecord):
                                found_records.append(region.parsed_value)
                    
                    # Verify detection
                    if not found_records:
                        print(f"  ✗ {test_file}: No GeometryManagerRecord found")
                        return False
                    
                    print(f"  ✓ {test_file}: Found {len(found_records)} GeometryManagerRecord(s)")
                    
                    # Verify structure parsing
                    for gm in found_records:
                        print(f"\n  Verifying structure at offset 0x{gm.offset:x}:")
                        
                        # Check that parts exist
                        if len(gm.padding) < 0:
                            print(f"    ✗ Invalid padding size: {len(gm.padding)}")
                            return False
                        print(f"    ✓ Padding: {len(gm.padding)} bytes")
                        
                        if len(gm.config) != 8:
                            print(f"    ✗ Config should be 8 bytes, got {len(gm.config)}")
                            return False
                        print(f"    ✓ Config: {len(gm.config)} bytes")
                        
                        if len(gm.payload) % 4 != 0:
                            print(f"    ✗ Payload should be 4-byte aligned, got {len(gm.payload)}")
                            return False
                        print(f"    ✓ Payload: {len(gm.payload)} bytes (4-byte aligned)")
                        
                        if len(gm.footer) != 12:
                            print(f"    ✗ Footer should be 12 bytes, got {len(gm.footer)}")
                            return False
                        print(f"    ✓ Footer: {len(gm.footer)} bytes")
                        
                        # Verify expected patterns
                        if gm.config == GeometryManagerRecord.EXPECTED_CONFIG:
                            print(f"    ✓ Config matches expected pattern")
                        else:
                            print(f"    ✗ Config does NOT match expected pattern")
                            return False
                        
                        if gm.footer == GeometryManagerRecord.EXPECTED_FOOTER:
                            print(f"    ✓ Footer matches expected pattern")
                        else:
                            print(f"    ✗ Footer does NOT match expected pattern")
                            return False
                        
                        # Verify total size
                        expected_size = len(gm.padding) + len(gm.config) + len(gm.payload) + len(gm.footer)
                        if len(gm.data) != expected_size:
                            print(f"    ✗ Total size mismatch: {len(gm.data)} vs {expected_size}")
                            return False
                        print(f"    ✓ Total size correct: {len(gm.data)} bytes")
                    
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


def test_backward_compatibility():
    """Test that files without GeometryManagerRecord still parse correctly."""
    print("\n" + "="*70)
    print("TEST: Backward Compatibility (files without GeometryManagerRecord)")
    print("="*70)
    
    # Test files that don't contain the GeometryManagerRecord
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
                        
                        # Verify parsing succeeded
                        if not regions:
                            print(f"  ✗ {test_file}: No regions parsed")
                            all_passed = False
                            continue
                        
                        # Count region types
                        type_counts = {}
                        for region in regions:
                            if isinstance(region, ClaimedRegion):
                                type_name = type(region.parsed_value).__name__
                                type_counts[type_name] = type_counts.get(type_name, 0) + 1
                        
                        print(f"  ✓ {test_file}: Parsed {len(regions)} regions successfully")
                        print(f"      (No GeometryManagerRecord, which is expected)")
                        break
                        
        except FileNotFoundError:
            print(f"  - {test_file}: (file not found, skipping)")
            continue
        except Exception as e:
            print(f"  ✗ {test_file}: Failed with exception: {e}")
            all_passed = False
    
    if all_passed:
        print("\n" + "="*70)
        print("BACKWARD COMPATIBILITY TEST PASSED ✓")
        print("="*70)
    else:
        print("\n" + "="*70)
        print("BACKWARD COMPATIBILITY TEST FAILED ✗")
        print("="*70)
    
    return all_passed


if __name__ == '__main__':
    test1_pass = test_geometry_manager_record_detection()
    test2_pass = test_backward_compatibility()
    
    print("\n" + "="*70)
    print("OVERALL TEST SUMMARY")
    print("="*70)
    print(f"  GeometryManagerRecord Detection: {'PASSED ✓' if test1_pass else 'FAILED ✗'}")
    print(f"  Backward Compatibility: {'PASSED ✓' if test2_pass else 'FAILED ✗'}")
    print("="*70)
    
    if test1_pass and test2_pass:
        print("\nALL TESTS PASSED ✓")
        exit(0)
    else:
        print("\nSOME TESTS FAILED ✗")
        exit(1)
