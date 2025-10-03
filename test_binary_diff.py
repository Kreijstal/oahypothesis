#!/usr/bin/env python3
"""
Test suite for binary_diff.py tool.
"""

import os
import sys
import tempfile
from binary_diff import (
    read_binary_file, 
    format_bytes, 
    format_compact, 
    binary_diff, 
    print_diff,
    print_summary
)

def test_read_binary_file():
    """Test reading binary files."""
    print("Testing read_binary_file...")
    with tempfile.NamedTemporaryFile(delete=False) as f:
        test_data = b'\x00\x01\x02\x03\x04'
        f.write(test_data)
        f.flush()
        filename = f.name
    
    try:
        result = read_binary_file(filename)
        assert result == test_data, f"Expected {test_data}, got {result}"
        print("  ✓ read_binary_file works correctly")
    finally:
        os.unlink(filename)

def test_format_bytes():
    """Test byte formatting with ASCII."""
    print("Testing format_bytes...")
    data = b'Hello World'
    result = format_bytes(data)
    assert '48 65 6c 6c 6f' in result, f"Hex not found in {result}"
    assert '|Hello World|' in result, f"ASCII not found in {result}"
    print("  ✓ format_bytes works correctly")

def test_format_compact():
    """Test compact byte formatting."""
    print("Testing format_compact...")
    data = b'\x01\x02\x03\x04'
    result = format_compact(data)
    assert result == '01 02 03 04', f"Expected '01 02 03 04', got '{result}'"
    
    # Test with truncation
    long_data = bytes(range(40))
    result = format_compact(long_data, max_len=8)
    assert result.endswith('...'), f"Expected truncation marker, got '{result}'"
    print("  ✓ format_compact works correctly")

def test_binary_diff_equal():
    """Test binary diff with equal files."""
    print("Testing binary_diff with equal files...")
    data = b'Same data'
    differences = binary_diff(data, data)
    assert len(differences) == 1, f"Expected 1 operation, got {len(differences)}"
    assert differences[0][0] == 'equal', f"Expected 'equal', got {differences[0][0]}"
    print("  ✓ binary_diff correctly identifies equal files")

def test_binary_diff_insert():
    """Test binary diff with insertion."""
    print("Testing binary_diff with insertion...")
    data1 = b'Hello World'
    data2 = b'Hello Python World'
    differences = binary_diff(data1, data2)
    
    # Should have equal, insert, equal operations
    found_insert = any(d[0] == 'insert' for d in differences)
    assert found_insert, "Expected to find insert operation"
    print("  ✓ binary_diff correctly identifies insertions")

def test_binary_diff_delete():
    """Test binary diff with deletion."""
    print("Testing binary_diff with deletion...")
    data1 = b'Hello Python World'
    data2 = b'Hello World'
    differences = binary_diff(data1, data2)
    
    # Should have equal, delete, equal operations
    found_delete = any(d[0] == 'delete' for d in differences)
    assert found_delete, "Expected to find delete operation"
    print("  ✓ binary_diff correctly identifies deletions")

def test_binary_diff_replace():
    """Test binary diff with replacement."""
    print("Testing binary_diff with replacement...")
    data1 = b'Hello World'
    data2 = b'Hello Earth'
    differences = binary_diff(data1, data2)
    
    # Should have equal and replace operations
    found_replace = any(d[0] == 'replace' for d in differences)
    assert found_replace, "Expected to find replace operation"
    print("  ✓ binary_diff correctly identifies replacements")

def test_print_diff():
    """Test diff printing (just verify it doesn't crash)."""
    print("Testing print_diff...")
    data1 = b'ABC'
    data2 = b'ADC'
    differences = binary_diff(data1, data2)
    
    # Should not crash
    print_diff(differences, show_equal=False)
    print("  ✓ print_diff works without crashing")

def test_print_summary():
    """Test summary printing (just verify it doesn't crash)."""
    print("Testing print_summary...")
    data1 = b'Hello World'
    data2 = b'Hello Python World'
    differences = binary_diff(data1, data2)
    
    # Should not crash
    print_summary(differences)
    print("  ✓ print_summary works without crashing")

def main():
    """Run all tests."""
    print("="*70)
    print("Running binary_diff.py test suite")
    print("="*70)
    
    tests = [
        test_read_binary_file,
        test_format_bytes,
        test_format_compact,
        test_binary_diff_equal,
        test_binary_diff_insert,
        test_binary_diff_delete,
        test_binary_diff_replace,
        test_print_diff,
        test_print_summary,
    ]
    
    passed = 0
    failed = 0
    
    for test in tests:
        try:
            test()
            passed += 1
        except AssertionError as e:
            print(f"  ✗ {test.__name__} failed: {e}")
            failed += 1
        except Exception as e:
            print(f"  ✗ {test.__name__} raised exception: {e}")
            failed += 1
    
    print("\n" + "="*70)
    print(f"Test Results: {passed} passed, {failed} failed")
    print("="*70)
    
    return 0 if failed == 0 else 1

if __name__ == '__main__':
    sys.exit(main())
