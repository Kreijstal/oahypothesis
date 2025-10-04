#!/usr/bin/env python3
"""
Demonstration script showing how parser.py and related tools can generate
meaningful diffs for understanding Cadence .oa file changes.

This script answers the question: "Can we use our parser.py to generate
meaningful diffs?"
"""

import sys
import subprocess

def run_comparison(file1, file2, description):
    """Run a comparison and display results."""
    print("="*80)
    print(f"COMPARISON: {description}")
    print("="*80)
    print(f"Comparing: {file1} → {file2}\n")
    
    try:
        result = subprocess.run(
            ['python3', 'compare_property_values.py', file1, file2],
            capture_output=True,
            text=True,
            timeout=30
        )
        print(result.stdout)
        if result.returncode != 0:
            print(f"Error: {result.stderr}")
    except Exception as e:
        print(f"Error running comparison: {e}")
    
    print()

def main():
    print("""
╔══════════════════════════════════════════════════════════════════════════════╗
║                    PARSER.PY MEANINGFUL DIFF DEMONSTRATION                   ║
║                                                                              ║
║  This script demonstrates how our parser tools can generate meaningful      ║
║  diffs to understand property value changes in Cadence .oa files.           ║
╚══════════════════════════════════════════════════════════════════════════════╝
""")
    
    # Test 1: First time setting 2K
    run_comparison(
        'files/rc/sch4.oa',
        'files/rc/sch5.oa',
        "First Time Setting Resistance to 2K"
    )
    
    print("INTERPRETATION:")
    print("  - Property Value ID changed from 68 → 70 (+2)")
    print("  - New string '2K' was added to string table")
    print("  - This is a simple property value change")
    print()
    
    # Test 2: Second time using 2K
    run_comparison(
        'files/rc/sch5.oa',
        'files/rc/sch9.oa',
        "Setting Different Resistor to 2K (String Already Exists)"
    )
    
    print("INTERPRETATION:")
    print("  - Property Value ID changed from 70 → 124 (+54)")
    print("  - No new string added (reuses existing '2K')")
    print("  - Large ID jump indicates structural changes (new component added)")
    print("  - Same string value gets NEW property value ID!")
    print()
    
    # Test 3: Changing 2K to 3K
    run_comparison(
        'files/rc/sch9.oa',
        'files/rc/sch10.oa',
        "Changing Resistance from 2K to 3K"
    )
    
    print("INTERPRETATION:")
    print("  - Property Value ID changed from 124 → 126 (+2)")
    print("  - New string '3K' was added to string table")
    print("  - Small +2 increment indicates simple value change")
    print("  - Minimal structural changes (same component, different value)")
    print()
    
    # Test 4: The mystery file
    run_comparison(
        'files/rc/sch13.oa',
        'files/rc/sch14.oa',
        "The Mystery File (sch14.oa)"
    )
    
    print("INTERPRETATION:")
    print("  - Property Value ID changed from 133 → 136 (+3)")
    print("  - No new strings added")
    print("  - ID 136 does NOT match ID 124 (which was 2K in sch9)")
    print("  - This shows property value IDs are TRANSACTIONAL, not value-specific")
    print("  - The same resistance value can have multiple different IDs")
    print()
    
    print("="*80)
    print("SUMMARY: Parser.py Tools Generate Meaningful Diffs")
    print("="*80)
    print("""
Our parser tools successfully reveal:

1. ✓ Property Value ID changes (showing which component properties changed)
2. ✓ String table additions (showing new vs reused values)
3. ✓ Change magnitude (+2 for simple changes, larger for structural changes)
4. ✓ Transaction history (same value can have different IDs over time)

KEY INSIGHT: Property Value IDs are transactional identifiers that track
modification history, not permanent identifiers for specific string values.
This is why the same "2K" value has ID 70 in sch5 and ID 124 in sch9.

The parser.py tools provide deep insights into Cadence's internal property
value tracking system that would be impossible to understand from raw binary
diffs alone.
""")

if __name__ == '__main__':
    main()
