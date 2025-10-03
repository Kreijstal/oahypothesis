#!/usr/bin/env python3
"""
Test suite for Table 0xC parsing, focusing on the TransientStateRecord.
"""

import sys
import struct
from table_c_parser import HypothesisParser, TransientStateRecord
from oaparser.binary_curator import ClaimedRegion

def get_transient_state_record(filename: str) -> TransientStateRecord | None:
    """Helper function to parse a file and find the TransientStateRecord."""
    with open(filename, 'rb') as f:
        # Boilerplate to find and parse table 0xc
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
                parser = HypothesisParser(data, string_table_data)
                regions = parser.parse()

                for region in regions:
                    if isinstance(region, ClaimedRegion) and isinstance(region.parsed_value, TransientStateRecord):
                        return region.parsed_value
    return None

def test_transient_state_record_detection():
    """
    Tests the detection and correct state identification of TransientStateRecord
    across multiple files.
    """
    print("="*70)
    print("TEST: Transient State Record Detection")
    print("="*70)
    
    all_passed = True

    # Case 1: sch5.oa should have State 1
    print("  Testing sch5.oa for State 1...")
    record5 = get_transient_state_record('sch5.oa')
    if record5:
        state_desc = record5.get_state_description()
        if "State 1" in state_desc:
            print("    ✓ PASSED: Correctly identified State 1.")
        else:
            print(f"    ✗ FAILED: Expected State 1, but got '{state_desc}'.")
            all_passed = False
    else:
        print("    ✗ FAILED: Did not find any TransientStateRecord.")
        all_passed = False

    # Case 2: sch6.oa should have State 2
    print("\n  Testing sch6.oa for State 2...")
    record6 = get_transient_state_record('sch6.oa')
    if record6:
        state_desc = record6.get_state_description()
        if "State 2" in state_desc:
            print("    ✓ PASSED: Correctly identified State 2.")
        else:
            print(f"    ✗ FAILED: Expected State 2, but got '{state_desc}'.")
            all_passed = False
    else:
        print("    ✗ FAILED: Did not find any TransientStateRecord.")
        all_passed = False

    # Case 3: sch4.oa should NOT have a transient record
    print("\n  Testing sch4.oa for absence of record...")
    record4 = get_transient_state_record('sch4.oa')
    if record4 is None:
        print("    ✓ PASSED: Correctly found no TransientStateRecord.")
    else:
        print(f"    ✗ FAILED: Incorrectly found a record: {record4}")
        all_passed = False

    # Case 4: sch9.oa should NOT have a transient record
    print("\n  Testing sch9.oa for absence of record...")
    record9 = get_transient_state_record('sch9.oa')
    if record9 is None:
        print("    ✓ PASSED: Correctly found no TransientStateRecord.")
    else:
        print(f"    ✗ FAILED: Incorrectly found a record: {record9}")
        all_passed = False

    return all_passed

def main():
    print("\nSimplified Table 0xC Parser Test Suite")
    print("="*70)
    
    passed = test_transient_state_record_detection()
    
    print("\n" + "="*70)
    if passed:
        print("ALL TESTS PASSED ✓")
        return 0
    else:
        print("TESTS FAILED ✗")
        return 1

if __name__ == '__main__':
    sys.exit(main())