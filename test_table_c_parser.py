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
import traceback
from table_c_parser import HypothesisParser, PropertyValueRecord, TimestampRecord
from oaparser.binary_curator import ClaimedRegion

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
                        regions = parser.parse()
                        
                        found_ts = None
                        for region in regions:
                            if isinstance(region, ClaimedRegion):
                                if isinstance(region.parsed_value, TimestampRecord):
                                    found_ts = region.parsed_value.timestamp_val & 0xFFFFFFFF
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

from table_c_parser import GenericRecord

def test_property_value_detection():
    """Test that true PropertyValueRecords are detected (with new strict logic)."""
    print("\n" + "="*70)
    print("TEST 2: Strict Property Value Detection")
    print("="*70)
    
    # This list is now focused only on records that should match the strict
    # signature of a PropertyValueRecord. Others are now GenericRecords.
    # Based on analysis, the sch13/14 change involves a true PVR.
    test_cases = [
        ('sch13.oa', 133),
        ('sch14.oa', 136),
    ]
    
    all_passed = True
    for filename, expected_id in test_cases:
        try:
            with open(filename, 'rb') as f:
                # Boilerplate to find and parse table 0xc
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
                        regions = parser.parse()
                        
                        prop_vals = []
                        for region in regions:
                            if isinstance(region, ClaimedRegion) and isinstance(region.parsed_value, PropertyValueRecord):
                                prop_vals.append(region.parsed_value.property_value_id)
                        
                        if expected_id in prop_vals:
                            print(f"  ✓ {filename}: Found expected PropertyValue ID {expected_id}")
                        else:
                            print(f"  ✗ {filename}: Expected PropertyValue ID {expected_id}, found {prop_vals}")
                            all_passed = False
                        break
        except Exception as e:
            print(f"  ✗ {filename}: Error - {e}")
            all_passed = False
    
    return all_passed

def test_generic_record_string_change():
    """Test that the 3K -> 2K resistance string change is detected in a GenericRecord."""
    print("\n" + "="*70)
    print("TEST 3: Generic Record String Change Detection (3K -> 2K)")
    print("="*70)

    def get_generic_strings(filename):
        """Helper to get all string references from a file's table 0xc."""
        string_refs = set()
        with open(filename, 'rb') as f:
            # Boilerplate to find table 0xa (strings) and 0xc (netlist)
            header = f.read(24)
            _, _, _, _, _, used = struct.unpack('<IHHQII', header)
            ids = list(struct.unpack(f'<{used}Q', f.read(8 * used)))
            offsets = list(struct.unpack(f'<{used}Q', f.read(8 * used)))
            sizes = list(struct.unpack(f'<{used}Q', f.read(8 * used)))
            
            string_table_data = None
            for i in range(used):
                if ids[i] == 0x0a:
                    f.seek(offsets[i])
                    string_table_data = f.read(sizes[i])
                    break
            
            for i in range(used):
                if ids[i] == 0x0c:
                    f.seek(offsets[i])
                    data = f.read(sizes[i])
                    # Crucially, pass the string table to the parser
                    parser = HypothesisParser(data, string_table_data)
                    regions = parser.parse()
                    for region in regions:
                        # Check GenericRecords for string references
                        if isinstance(region, ClaimedRegion) and isinstance(region.parsed_value, GenericRecord):
                            if hasattr(region.parsed_value, 'string_references'):
                                for _, _, resolved_str in region.parsed_value.string_references:
                                    string_refs.add(resolved_str)
                    return string_refs
        return string_refs

    try:
        strings13 = get_generic_strings('sch13.oa')
        strings14 = get_generic_strings('sch14.oa')

        # Check that '3K' was replaced by '2K'
        change_present = '3K' in strings13 and '3K' not in strings14
        change_absent = '2K' not in strings13 and '2K' in strings14

        if change_present and change_absent:
            print("  ✓ sch13.oa -> sch14.oa: Correctly detected '3K' -> '2K' change.")
            return True
        else:
            print("  ✗ sch13.oa -> sch14.oa: Failed to detect change.")
            print(f"    - Strings in sch13: {sorted(list(strings13))}")
            print(f"    - Strings in sch14: {sorted(list(strings14))}")
            return False
            
    except Exception as e:
        import traceback
        print(f"  ✗ Test failed with exception: {e}")
        traceback.print_exc()
        return False

from table_c_parser import ComponentPropertyRecord

def test_component_property_record_detection():
    """Test that the 132-byte ComponentPropertyRecord is correctly identified."""
    print("\n" + "="*70)
    print("TEST 4: Component Property Record Detection")
    print("="*70)

    filename = 'sch5.oa'
    expected_ids = {12, 16, 28} # The value_ids we expect to find in this file

    try:
        with open(filename, 'rb') as f:
            # Boilerplate to find and parse table 0xc
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
                    regions = parser.parse()

                    found_records = [
                        region.parsed_value
                        for region in regions
                        if isinstance(region, ClaimedRegion) and isinstance(region.parsed_value, ComponentPropertyRecord)
                    ]

                    found_ids = {rec.value_id for rec in found_records}

                    # Verify all found records have matching static parts
                    all_patterns_match = all(rec.config_matches and rec.padding_matches for rec in found_records)

                    if found_ids == expected_ids and all_patterns_match:
                        print(f"  ✓ {filename}: Found all expected IDs and all static patterns match.")
                        return True
                    else:
                        print(f"  ✗ {filename}: Test failed.")
                        if found_ids != expected_ids:
                            print(f"    - ID Mismatch: Expected {sorted(list(expected_ids))}, Found {sorted(list(found_ids))}")
                        if not all_patterns_match:
                            print("    - Pattern Mismatch: One or more records did not match expected static patterns.")
                            for rec in found_records:
                                if not rec.config_matches or not rec.padding_matches:
                                    print(f"      - Record at offset 0x{rec.offset:x} (Value ID: {rec.value_id}) failed assertion.")
                        return False
    except Exception as e:
        print(f"  ✗ {filename}: Error - {e}")
        traceback.print_exc()
        return False

def main():
    print("\nTable 0xC Parser Test Suite")
    print("="*70)
    
    results = []
    results.append(("Timestamp Extraction", test_timestamps()))
    results.append(("Strict Property Value Detection", test_property_value_detection()))
    results.append(("Generic Record String Change", test_generic_record_string_change()))
    results.append(("Component Property Record Detection", test_component_property_record_detection()))
    
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
