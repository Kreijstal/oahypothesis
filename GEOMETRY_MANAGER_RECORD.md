# GeometryManagerRecord Implementation

## Overview

This document describes the implementation of the `GeometryManagerRecord` parser, which teaches the parser to recognize and structure "Geometry Manager" records instead of treating them as generic blobs.

## Problem Statement

Previously, the parser treated Geometry Manager records (identified by the string `sch.ds.gm.1.4`) as `GenericRecord` instances. This resulted in:

- **Index-based output**: Display as a flat array of integers with arbitrary indexes
- **Diff noise**: Changes in padding or payload position caused unnecessary diff noise
- **Lost structure**: The internal multi-part structure (Padding, Config, Payload, Footer) was not recognized

## Solution

A specialized `GeometryManagerRecord` dataclass that understands the internal structure:

```
┌─────────────────────────────────────────────────────────┐
│ GeometryManagerRecord                                   │
├─────────────────────────────────────────────────────────┤
│ Padding:  Variable (0-N bytes of zeros)                │
│ Config:   8 bytes (stable pattern: 0800000003000000)    │
│ Payload:  Variable (4-byte aligned, the changing part)  │
│ Footer:   12 bytes (stable: 000000c802000000e8001a03)   │
└─────────────────────────────────────────────────────────┘
```

## Implementation Details

### 1. GeometryManagerRecord Dataclass

Located in `table_c_parser.py`, this dataclass:

- Parses the multi-part structure
- Validates Config and Footer against expected patterns
- Highlights the Payload as the variable part
- Uses `_generate_diff()` to show any pattern violations (Binary Curator principle)

### 2. Detection Logic

The `_check_and_claim_geometry_manager()` method:

1. Searches for the Config signature within the data
2. Verifies the Footer signature is at the end
3. Extracts all four components with correct boundaries
4. Claims the record if both signatures match

### 3. Integration

Modified `_claim_as_generic_or_property_value()` to check for GeometryManagerRecord BEFORE falling back to GenericRecord, implementing a chain of responsibility pattern.

## Benefits

### 1. Structured Output
**Before (GenericRecord):**
```
Strings: "sch.ds.gm.1.4"
Content (summarized as 32-bit integers):
- Index[000]: 0 (0x0) (repeats 8 times)
- Index[008]: 8 (0x8)
- Index[009]: 3 (0x3)
- Index[010]: 0 (0x0)
- Index[011]: 4294967295 (0xffffffff)
- Index[012]: 3355443200 (0xc8000000)
- Index[013]: 2 (0x2)
- Index[014]: 52035816 (0x31a00e8)
```

**After (GeometryManagerRecord):**
```
Geometry Manager Record (Size: 60 bytes)
  - Padding: 32 bytes
  - Config: 8 bytes (OK, matches expected pattern)
  - Payload: 8 bytes, Values: {0x0, 0xffffffff}
  - Footer: 12 bytes (OK, matches expected pattern)
```

### 2. Stable Across Files

The new parser normalizes padding variations and validates static patterns:

| File     | Padding | Config | Payload           | Footer |
|----------|---------|--------|-------------------|--------|
| sch5.oa  | 32 bytes| ✓ OK   | {0x0, 0xffffffff} | ✓ OK   |
| sch6.oa  | 28 bytes| ✓ OK   | {0x1, 0x2}        | ✓ OK   |
| sch7.oa  | 32 bytes| ✓ OK   | {0x1, 0x2}        | ✓ OK   |
| sch8.oa  | 32 bytes| ✓ OK   | {0x1, 0x2}        | ✓ OK   |

### 3. Pattern Validation

When patterns don't match, the parser shows exactly what's different:

```
Geometry Manager Record (Size: 44 bytes)
  - Padding: 16 bytes
  - Config: 8 bytes (MODIFIED - VIOLATES EXPECTED PATTERN)
    0000:
      - Expected: 08 00 00 00 03 00 00 00
      - Actual:   09 00 00 00 04 00 00 00
  - Payload: 8 bytes, Values: {0x78563412, 0xabefcdab}
  - Footer: 12 bytes (MODIFIED - VIOLATES EXPECTED PATTERN)
    0000:
      - Expected: 00 00 00 c8 02 00 00 00 e8 00 1a 03
      - Actual:   01 00 00 c8 03 00 00 00 e9 00 1b 04
```

## Testing

### Test Coverage

1. **Detection Test** (`test_geometry_manager_record.py`):
   - Verifies GeometryManagerRecord is detected in files containing the pattern
   - Validates structure parsing (padding, config, payload, footer)
   - Checks pattern matching works correctly

2. **Backward Compatibility Test**:
   - Confirms files without GeometryManagerRecord parse correctly
   - No regressions in existing functionality

3. **Original Tests** (`test_table_c_parser.py`):
   - All existing tests continue to pass
   - Timestamp extraction, PropertyValue detection, ComponentPropertyRecord detection all work

### Test Results

```
✓ GeometryManagerRecord Detection: PASSED
✓ Backward Compatibility: PASSED
✓ All Original Tests: PASSED
```

## File Coverage

The GeometryManagerRecord pattern appears in:
- ✓ sch5.oa
- ✓ sch6.oa
- ✓ sch7.oa
- ✓ sch8.oa

Files without this pattern continue to work normally:
- sch9.oa, sch13.oa, sch14.oa, etc.

## Binary Curator Compliance

The implementation strictly follows the Binary Curator principle:

1. ✓ **All claimed bytes are visible**: Padding, Config, Payload, and Footer are all displayed
2. ✓ **No data hiding**: When patterns don't match, `_generate_diff()` shows the exact differences
3. ✓ **Lossless representation**: The full structure can be reconstructed from the output
4. ✓ **Explicit assertions**: Pattern matching is validated and reported

## Future Enhancements

Potential improvements:

1. **Payload interpretation**: If the payload structure becomes known, parse it further
2. **Additional patterns**: Detect other multi-part structures in the file format
3. **Version detection**: If Config/Footer patterns vary by version, detect and handle

## Conclusion

The GeometryManagerRecord implementation successfully:
- ✓ Reduces parser output noise
- ✓ Provides stable, structured output
- ✓ Validates expected patterns
- ✓ Maintains full backward compatibility
- ✓ Upholds the Binary Curator principle

This refactoring demonstrates the value of promoting specific record types from generic parsing when their internal structure is understood.
