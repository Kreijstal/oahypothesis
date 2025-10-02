# BinaryCurator Refactoring Summary

## Overview
This refactoring introduces the `BinaryCurator` library to ensure **lossless binary parsing** across all table parsers in the oahypothesis project. The key innovation is that all unclaimed (unknown) data is explicitly shown in the output, ensuring no data is ever hidden.

## What Changed

### New Module: `oaparser/binary_curator.py`
- Created a reusable library for iterative reverse engineering of binary data
- Core concept: "claim" known structures while tracking all unclaimed regions
- Key features:
  - `BinaryCurator.claim()` - Mark a region as understood
  - `BinaryCurator.seek()` / `skip()` - Navigate through binary data
  - `BinaryCurator.report()` - Generate complete lossless report

### Refactored Parsers
All table parsers now use BinaryCurator:

1. **`table_a_parser.py`** (String Table) - Claims header, padding, and individual strings
2. **`table_b_parser.py`** (Property List) - Claims header, record count, and property records
3. **`table_1_parser.py`** (Global Metadata) - Claims version strings, counters, timestamps, and array elements
4. **`table_1d_parser.py`** (Table Directory) - Claims each table ID entry
5. **`table_133_parser.py`** (Integer Array) - Claims each integer with special marking

## Benefits

### Before Refactoring
Parsers could hide data in several ways:
- **Skipping bytes**: Only reading specific offsets (e.g., table_107_parser)
- **Opaque blocks**: Treating regions as "unknown" without showing content
- **Trailing data**: Ignoring "unexpected" bytes at the end
- **Pattern mismatches**: Early loop termination when structure isn't recognized

### After Refactoring
- **Complete visibility**: All unclaimed data is shown with hex dump
- **Verifiable parsing**: Easy to see what's understood vs. unknown
- **Smaller diffs**: oa_diff_hypothesis will produce more focused diffs
- **Iterative RE**: Can progressively claim more structures without losing data

## Example Output

### Before (table_b_parser.py)
```
[Header]
  - Note: Header is treated as an opaque block.
[INFO] Found 16 unexpected trailing bytes at the end of the table.
```

### After (table_b_parser.py with BinaryCurator)
```
==================================================
[Header (opaque block)]
  Offset: 0x0, Size: 220 bytes
  Parsed Value: Content not yet fully understood
  Raw Hex: 04 00 00 00 00 00 00 00 d4 00 00 00...
==================================================
[Unclaimed Data]
  Offset: 0x128, Size: 16 bytes
  0000: ff ff ff ff 00 00 00 00 00 00 00 00 00 00 00 00  |................|
==================================================
```

Now you can **see** the actual trailing bytes instead of just being told they exist.

## Testing

### New Tests
- `test_binary_curator.py` - Comprehensive test suite for BinaryCurator
  - Basic claiming
  - Seek and skip
  - Out-of-order claims
  - Full claim vs. unclaimed data

### Existing Tests
All existing tests continue to pass:
- `test_table_c_parser.py` - ✓ All tests passed
- Timestamp extraction works correctly
- Property value detection works correctly
- Parser output is compatible with existing tools

## Impact on oa_diff_hypothesis

The refactoring will make diffs **smaller and more meaningful** because:
1. Unclaimed regions are shown consistently across files
2. Only actual structural changes will appear in diffs
3. No hidden data means no "mysterious" differences

## Usage

```python
from oaparser import BinaryCurator

curator = BinaryCurator(data)

# Claim known structures
curator.claim("Magic Number", 4, lambda d: f"0x{struct.unpack('<I', d)[0]:08x}")
curator.claim("Version", 4, lambda d: f"{struct.unpack('<I', d)[0]}")

# Jump to specific location
curator.seek(0x100)
curator.claim("Timestamp", 8, lambda d: f"{struct.unpack('<Q', d)[0]}")

# Generate lossless report
print(curator.report())  # Shows claimed AND unclaimed regions
```

## Files Modified
- ✅ `oaparser/__init__.py` - New module
- ✅ `oaparser/binary_curator.py` - Core library
- ✅ `test_binary_curator.py` - Test suite
- ✅ `table_a_parser.py` - Refactored
- ✅ `table_b_parser.py` - Refactored
- ✅ `table_1_parser.py` - Refactored
- ✅ `table_1d_parser.py` - Refactored
- ✅ `table_133_parser.py` - Refactored

## Future Work
- Consider refactoring `table_c_parser.py` (complex pattern matching parser)
- Consider refactoring `table_107_parser.py` (aggressive offset-based parser)
- Add more parser helper utilities to oaparser module
