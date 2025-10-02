#!/usr/bin/env python3
"""
Test suite for BinaryCurator class
"""

import struct
from oaparser import BinaryCurator, render_regions_to_string, UnclaimedRegion, ClaimedRegion

def test_basic_claiming():
    """Test basic claim functionality"""
    print("="*70)
    print("TEST 1: Basic Claiming")
    print("="*70)
    
    # Create a simple binary structure
    data = struct.pack('<IIHH', 0x12345678, 0xABCDEF00, 0x1234, 0x5678)
    data += b"Hello World\x00"
    data += b"\xFF" * 10  # Some unclaimed bytes
    
    curator = BinaryCurator(data)
    
    # Claim the first integer
    curator.claim("Magic Number", 4, lambda b: f"0x{struct.unpack('<I', b)[0]:08x}")
    
    # Claim the second integer
    curator.claim("Version ID", 4, lambda b: f"0x{struct.unpack('<I', b)[0]:08x}")
    
    # Claim the two shorts
    curator.claim("Counter 1", 2, lambda b: f"{struct.unpack('<H', b)[0]}")
    curator.claim("Counter 2", 2, lambda b: f"{struct.unpack('<H', b)[0]}")
    
    # Claim the string (but not the unclaimed bytes)
    curator.claim("Name String", 12, lambda b: f'"{b.decode("utf-8", errors="ignore").rstrip(chr(0))}"')
    
    # Get regions and render report
    regions = curator.get_regions()
    report = render_regions_to_string(regions, "Test 1: Basic Claiming")
    print(report)
    
    # Verify that unclaimed data is shown
    if "[UNCLAIMED DATA]" in report and "ff ff ff" in report:
        print("\n✓ PASSED: Unclaimed data is visible in report")
        return True
    else:
        print("\n✗ FAILED: Unclaimed data not properly reported")
        return False

def test_seek_and_skip():
    """Test seek and skip functionality"""
    print("\n" + "="*70)
    print("TEST 2: Seek and Skip")
    print("="*70)
    
    data = b"\x00" * 100
    data = data[:10] + struct.pack('<I', 0xDEADBEEF) + data[14:]
    
    curator = BinaryCurator(data)
    
    # Skip to offset 10
    curator.seek(10)
    curator.claim("Magic at offset 10", 4, lambda b: f"0x{struct.unpack('<I', b)[0]:08x}")
    
    # Skip 20 bytes
    curator.skip(20)
    curator.claim("4 bytes at offset 34", 4, lambda b: f"0x{struct.unpack('<I', b)[0]:08x}")
    
    regions = curator.get_regions()
    report = render_regions_to_string(regions, "Test 2: Seek and Skip")
    print(report)
    
    # Verify that we have unclaimed regions before, between, and after
    if report.count("[UNCLAIMED DATA]") == 3:
        print("\n✓ PASSED: Seek and skip work correctly")
        return True
    else:
        print(f"\n✗ FAILED: Expected 3 unclaimed regions, found {report.count('[UNCLAIMED DATA]')}")
        return False

def test_no_claims():
    """Test that fully unclaimed data is reported"""
    print("\n" + "="*70)
    print("TEST 3: No Claims (Fully Lossless)")
    print("="*70)
    
    data = b"Test data that is never claimed"
    curator = BinaryCurator(data)
    
    regions = curator.get_regions()
    report = render_regions_to_string(regions, "Test 3: No Claims")
    print(report)
    
    if "[UNCLAIMED DATA]" in report and "Size: 31 bytes" in report:
        print("\n✓ PASSED: Unclaimed-only data is properly reported")
        return True
    else:
        print("\n✗ FAILED: Unclaimed-only data not properly reported")
        return False

def test_full_claim():
    """Test that fully claimed data has no unclaimed sections"""
    print("\n" + "="*70)
    print("TEST 4: Full Claim (No Unclaimed Data)")
    print("="*70)
    
    data = struct.pack('<II', 0x11111111, 0x22222222)
    curator = BinaryCurator(data)
    
    curator.claim("First Int", 4, lambda b: f"0x{struct.unpack('<I', b)[0]:08x}")
    curator.claim("Second Int", 4, lambda b: f"0x{struct.unpack('<I', b)[0]:08x}")
    
    regions = curator.get_regions()
    report = render_regions_to_string(regions, "Test 4: Full Claim")
    print(report)
    
    if "[UNCLAIMED DATA]" not in report:
        print("\n✓ PASSED: No unclaimed data when everything is claimed")
        return True
    else:
        print("\n✗ FAILED: Found unclaimed data when everything should be claimed")
        return False

def test_out_of_order_claims():
    """Test that out-of-order claims are sorted correctly"""
    print("\n" + "="*70)
    print("TEST 5: Out-of-Order Claims")
    print("="*70)
    
    data = b"\x00" * 100
    curator = BinaryCurator(data)
    
    # Claim regions out of order
    curator.seek(50)
    curator.claim("Middle region", 10, lambda b: f"{len(b)} bytes")
    
    curator.seek(10)
    curator.claim("Early region", 10, lambda b: f"{len(b)} bytes")
    
    curator.seek(80)
    curator.claim("Late region", 10, lambda b: f"{len(b)} bytes")
    
    regions = curator.get_regions()
    report = render_regions_to_string(regions, "Test 5: Out-of-Order Claims")
    print(report)
    
    # Check that regions are reported in order
    early_pos = report.find("Early region")
    middle_pos = report.find("Middle region")
    late_pos = report.find("Late region")
    
    if early_pos < middle_pos < late_pos:
        print("\n✓ PASSED: Out-of-order claims are sorted correctly")
        return True
    else:
        print("\n✗ FAILED: Regions not in correct order")
        return False

def main():
    print("\nBinaryCurator Test Suite")
    print("="*70)
    
    results = []
    results.append(("Basic Claiming", test_basic_claiming()))
    results.append(("Seek and Skip", test_seek_and_skip()))
    results.append(("No Claims (Lossless)", test_no_claims()))
    results.append(("Full Claim", test_full_claim()))
    results.append(("Out-of-Order Claims", test_out_of_order_claims()))
    
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
    import sys
    sys.exit(main())
