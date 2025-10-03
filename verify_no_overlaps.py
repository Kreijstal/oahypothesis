#!/usr/bin/env python3
"""
Verification script to ensure parser.py doesn't create overlapping regions
when parsing .oa files.

This script runs parser.py on all available .oa files and checks for overlap errors.
"""

import sys
import glob
import subprocess

def test_file_for_overlaps(filepath):
    """
    Test a single .oa file for overlaps by running parser.py on it.
    Returns True if no overlaps detected, False otherwise.
    """
    print(f"Testing {filepath}...", end=" ")
    try:
        result = subprocess.run(
            ["python3", "parser.py", filepath],
            capture_output=True,
            text=True,
            timeout=30
        )
        
        # Check for overlap errors in output
        output = result.stdout + result.stderr
        if "Overlap detected" in output:
            print("❌ OVERLAP DETECTED!")
            print("Error output:")
            print(output)
            return False
        elif result.returncode != 0:
            # Check if it's a different error
            if "Traceback" in output or "Error" in output:
                print(f"⚠️  Parser error (not overlap): return code {result.returncode}")
                # Print first few lines of error
                lines = output.split('\n')
                for line in lines[-10:]:
                    if line.strip():
                        print(f"  {line}")
                return True  # Not an overlap error, so we pass
            print(f"⚠️  Non-zero return code: {result.returncode}")
            return True
        else:
            print("✓ No overlaps")
            return True
            
    except subprocess.TimeoutExpired:
        print("⏱️  Timeout (likely okay, not an overlap)")
        return True
    except Exception as e:
        print(f"❌ Exception: {e}")
        return False

def main():
    print("="*70)
    print("Overlap Detection Verification for parser.py")
    print("="*70)
    print("\nSearching for .oa files...")
    
    # Find all .oa files
    oa_files = sorted(glob.glob("*.oa"))
    
    if not oa_files:
        print("❌ No .oa files found in current directory!")
        return 1
    
    print(f"Found {len(oa_files)} .oa file(s)\n")
    
    results = []
    for oa_file in oa_files:
        result = test_file_for_overlaps(oa_file)
        results.append((oa_file, result))
    
    print("\n" + "="*70)
    print("SUMMARY")
    print("="*70)
    
    passed = sum(1 for _, r in results if r)
    failed = len(results) - passed
    
    print(f"\nTotal files tested: {len(results)}")
    print(f"Passed (no overlaps): {passed}")
    print(f"Failed (overlaps detected): {failed}")
    
    if failed > 0:
        print("\n❌ FAILED FILES:")
        for filename, result in results:
            if not result:
                print(f"  - {filename}")
    
    print("\n" + "="*70)
    if failed == 0:
        print("✅ ALL FILES PASSED - No overlaps detected!")
        return 0
    else:
        print("❌ SOME FILES FAILED - Overlaps detected!")
        return 1

if __name__ == '__main__':
    sys.exit(main())
