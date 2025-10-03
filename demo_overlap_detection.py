#!/usr/bin/env python3
"""
Demonstration of BinaryCurator overlap detection feature.

This script shows how the overlap detection prevents common mistakes
in binary reverse engineering.
"""

from oaparser import BinaryCurator
import struct

def demo_basic_overlap():
    """Demonstrate basic overlap detection"""
    print("="*70)
    print("DEMO 1: Basic Overlap Detection")
    print("="*70)
    
    data = b'\x00' * 100
    curator = BinaryCurator(data)
    
    # Claim a region
    curator.seek(10)
    curator.claim('Header', 20, lambda b: f'{len(b)} bytes')
    print("✓ Claimed 'Header' at offset 10-29 (size 20 bytes)")
    
    # Try to claim an overlapping region
    print("\nAttempting to claim overlapping region at offset 15-24...")
    try:
        curator.seek(15)
        curator.claim('Overlapping Field', 10, lambda b: f'{len(b)} bytes')
        print("❌ ERROR: Overlap was not detected!")
    except ValueError as e:
        print(f"✓ Overlap correctly detected:")
        print(f"  {e}")

def demo_adjacent_regions():
    """Demonstrate that adjacent regions are allowed"""
    print("\n" + "="*70)
    print("DEMO 2: Adjacent Regions (Non-overlapping)")
    print("="*70)
    
    data = b'\x00' * 100
    curator = BinaryCurator(data)
    
    # Claim consecutive regions
    curator.seek(0)
    curator.claim('Region A', 10, lambda b: f'{len(b)} bytes')
    print("✓ Claimed 'Region A' at offset 0-9")
    
    curator.seek(10)  # Exactly where Region A ends
    curator.claim('Region B', 10, lambda b: f'{len(b)} bytes')
    print("✓ Claimed 'Region B' at offset 10-19")
    
    curator.seek(20)
    curator.claim('Region C', 10, lambda b: f'{len(b)} bytes')
    print("✓ Claimed 'Region C' at offset 20-29")
    
    print("\n✓ Adjacent regions are allowed (no overlap)")

def demo_complex_overlap_scenarios():
    """Demonstrate various overlap scenarios"""
    print("\n" + "="*70)
    print("DEMO 3: Complex Overlap Scenarios")
    print("="*70)
    
    # Scenario 1: New region starts before and extends into existing
    print("\nScenario 1: New region starts before existing and overlaps")
    data = b'\x00' * 100
    curator = BinaryCurator(data)
    curator.seek(20)
    curator.claim('Existing', 10, lambda b: f'{len(b)} bytes')
    print("✓ Claimed 'Existing' at offset 20-29")
    
    try:
        curator.seek(15)
        curator.claim('Before-overlap', 10, lambda b: f'{len(b)} bytes')
        print("❌ ERROR: Overlap not detected!")
    except ValueError:
        print("✓ Overlap detected: New region (15-24) overlaps with Existing (20-29)")
    
    # Scenario 2: New region completely contains existing
    print("\nScenario 2: New region completely contains existing region")
    curator2 = BinaryCurator(data)
    curator2.seek(30)
    curator2.claim('Small Region', 5, lambda b: f'{len(b)} bytes')
    print("✓ Claimed 'Small Region' at offset 30-34")
    
    try:
        curator2.seek(25)
        curator2.claim('Large Region', 15, lambda b: f'{len(b)} bytes')
        print("❌ ERROR: Overlap not detected!")
    except ValueError:
        print("✓ Overlap detected: Large region (25-39) contains Small Region (30-34)")
    
    # Scenario 3: Exact overlap (same position and size)
    print("\nScenario 3: Exact overlap (same position and size)")
    curator3 = BinaryCurator(data)
    curator3.seek(40)
    curator3.claim('Region X', 10, lambda b: f'{len(b)} bytes')
    print("✓ Claimed 'Region X' at offset 40-49")
    
    try:
        curator3.seek(40)
        curator3.claim('Region Y', 10, lambda b: f'{len(b)} bytes')
        print("❌ ERROR: Exact overlap not detected!")
    except ValueError:
        print("✓ Overlap detected: Region Y exactly matches Region X (40-49)")

def demo_out_of_order_claims():
    """Demonstrate overlap detection with out-of-order claims"""
    print("\n" + "="*70)
    print("DEMO 4: Out-of-Order Claims with Overlap Detection")
    print("="*70)
    
    data = b'\x00' * 100
    curator = BinaryCurator(data)
    
    # Claim regions out of order
    curator.seek(50)
    curator.claim('Middle', 10, lambda b: f'{len(b)} bytes')
    print("✓ Claimed 'Middle' at offset 50-59")
    
    curator.seek(20)
    curator.claim('Early', 10, lambda b: f'{len(b)} bytes')
    print("✓ Claimed 'Early' at offset 20-29")
    
    curator.seek(80)
    curator.claim('Late', 10, lambda b: f'{len(b)} bytes')
    print("✓ Claimed 'Late' at offset 80-89")
    
    # Now try to claim something that overlaps with 'Early'
    print("\nAttempting to claim region that overlaps with 'Early'...")
    try:
        curator.seek(25)
        curator.claim('Overlap with Early', 10, lambda b: f'{len(b)} bytes')
        print("❌ ERROR: Overlap not detected!")
    except ValueError:
        print("✓ Overlap detected with 'Early' even though it was claimed out of order")

def main():
    print("\n" + "="*70)
    print("BinaryCurator Overlap Detection Demonstration")
    print("="*70)
    print("\nThis demonstrates the overlap detection feature added to")
    print("BinaryCurator to prevent common reverse engineering mistakes.\n")
    
    demo_basic_overlap()
    demo_adjacent_regions()
    demo_complex_overlap_scenarios()
    demo_out_of_order_claims()
    
    print("\n" + "="*70)
    print("Summary")
    print("="*70)
    print("\nThe BinaryCurator now enforces strict non-overlapping regions.")
    print("This prevents:")
    print("  • Accidentally claiming the same bytes twice")
    print("  • Overlapping structure definitions")
    print("  • Incorrect offset calculations")
    print("\nAdjacent regions (touching but not overlapping) are still allowed.")
    print("\n✅ All demonstrations completed successfully!")
    print("="*70)

if __name__ == '__main__':
    main()
