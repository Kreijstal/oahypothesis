# Table 0xC Parser Enhancement - Quick Start Guide

## What Was Done

Enhanced the Table 0xC parser to identify and track property value changes (like resistance values changing from 1K to 2K) in OpenAccess .oa files.

## Key Features

1. **Property Value Detection**: Automatically identifies property value IDs in parsed data
2. **Timestamp Regression Test**: Ensures timestamp parsing remains correct
3. **Comparison Tools**: Easy comparison of property values between file versions
4. **Comprehensive Test Suite**: Validates all functionality

## Quick Examples

### 1. Parse a file and see property values
```bash
python parser.py sch5.oa
```
Look for `[IDENTIFIED: Property Value Record]` sections showing property value IDs.

### 2. Compare property values between two files
```bash
python compare_property_values.py sch4.oa sch5.oa
```
Output:
```
Offset 0x02ec: Property Value ID 68 -> 70
                Change: +2
```

### 3. Run regression tests
```bash
# Timestamp extraction test
python test_timestamp_regression.py

# Full test suite
python test_table_c_parser.py
```

## Key Finding: Resistance Value Change

**sch4.oa → sch5.oa (1K → 2K resistance change)**
- Location: Table 0xC, offset 0x02ec
- Property Value ID changed from 68 to 70 (+2)
- The +2 change indicates two new values were added:
  - ID 69: Property name "r" (resistance)  
  - ID 70: Property value "2K"

## Files Added

- `test_timestamp_regression.py` - Regression test for timestamps
- `test_table_c_parser.py` - Comprehensive test suite
- `compare_property_values.py` - Property value comparison tool
- `PARSER_IMPROVEMENTS.md` - Detailed technical documentation

## Files Modified

- `table_c_parser.py` - Added PropertyValueRecord class and detection logic

## Test Results

✅ All 9 .oa files parse successfully  
✅ Timestamp extraction: 9/9 PASS  
✅ Property value detection: 4/4 PASS  
✅ Change detection: 3/3 PASS  

## Architecture

The parser uses a three-pass approach:
1. **Pass 1**: Parse raw data into record objects
2. **Pass 2**: Identify and promote timestamp records
3. **Pass 3**: Annotate property value references

Property values are detected by finding small integers (20-200 range) in specific structural contexts, typically near marker values like `0xc8000000`.

## For More Details

See `PARSER_IMPROVEMENTS.md` for complete technical documentation.
