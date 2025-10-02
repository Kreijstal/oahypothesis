#!/usr/bin/env python3
"""
Regression test for timestamp parsing in Table 0xC.

This test verifies that the timestamp parser correctly extracts the save timestamp
from all .oa files in the repository. The timestamps are the "golden data" that
should remain consistent across parser changes.
"""

import struct
import glob
from table_c_parser import HypothesisParser

# Golden timestamps extracted from each file (Unix timestamps)
EXPECTED_TIMESTAMPS = {
    'sch_old.oa': 1759219482,      # 2025-09-30 08:04:42 UTC
    'sch_new.oa': 1759220368,      # 2025-09-30 08:19:28 UTC
    'sch2.oa': 1759220630,         # 2025-09-30 08:23:50 UTC
    'sch3.oa': 1759267303,         # 2025-09-30 21:21:43 UTC
    'sch4.oa': 1759268290,         # 2025-09-30 21:38:10 UTC
    'sch5.oa': 1759269165,         # 2025-09-30 21:52:45 UTC
    'sch6.oa': 1759269681,         # 2025-09-30 22:01:21 UTC
    'sch7.oa': 1759269898,         # 2025-09-30 22:04:58 UTC
    'sch8.oa': 1759270115,         # 2025-09-30 22:08:35 UTC
}

def extract_table_c_data(filepath):
    """Extract Table 0xC data from an .oa file."""
    with open(filepath, 'rb') as f:
        # Read header
        header = f.read(24)
        _, _, _, _, _, used = struct.unpack('<IHHQII', header)
        
        # Read table directory
        ids = list(struct.unpack(f'<{used}Q', f.read(8 * used)))
        offsets = list(struct.unpack(f'<{used}Q', f.read(8 * used)))
        sizes = list(struct.unpack(f'<{used}Q', f.read(8 * used)))
        
        # Find Table 0xC
        for i in range(used):
            if ids[i] == 0x0c and offsets[i] != 0xffffffffffffffff:
                f.seek(offsets[i])
                return f.read(sizes[i])
    
    return None

def extract_timestamp_from_table_c(data):
    """Parse Table 0xC and extract the timestamp."""
    if not data:
        return None
    
    parser = HypothesisParser(data)
    regions = parser.parse()
    
    # Find TimestampRecord in parsed regions
    from table_c_parser import TimestampRecord
    from oaparser.binary_curator import ClaimedRegion
    
    for region in regions:
        if isinstance(region, ClaimedRegion):
            if isinstance(region.parsed_value, TimestampRecord):
                return region.parsed_value.timestamp_val & 0xFFFFFFFF
    
    return None

def test_all_timestamps():
    """Test timestamp extraction for all .oa files."""
    print("Running timestamp regression test...")
    
    all_passed = True
    for filename, expected_timestamp in EXPECTED_TIMESTAMPS.items():
        table_c_data = extract_table_c_data(filename)
        if table_c_data is None:
            print(f"FAIL: {filename} - Could not extract Table 0xC")
            all_passed = False
            continue
        
        actual_timestamp = extract_timestamp_from_table_c(table_c_data)
        
        if actual_timestamp == expected_timestamp:
            print(f"PASS: {filename} - Timestamp: {actual_timestamp}")
        else:
            print(f"FAIL: {filename} - Expected: {expected_timestamp}, Got: {actual_timestamp}")
            all_passed = False
    
    return all_passed

if __name__ == '__main__':
    import sys
    success = test_all_timestamps()
    print("\n" + "="*70)
    if success:
        print("All timestamp tests PASSED!")
        sys.exit(0)
    else:
        print("Some timestamp tests FAILED!")
        sys.exit(1)
