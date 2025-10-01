# Table 0xC Parser Improvements - Summary

## Overview
This document summarizes the improvements made to the Table 0xC parser to detect and parse property value changes, such as resistance value modifications (1K → 2K).

## Problem Statement
The original issue requested:
1. Parse sch4.oa and sch5.oa to identify where the resistance value changed from 1K to 2K
2. Investigate how Table 0xC differs between sch7.oa and sch8.oa
3. Create a regression test for timestamp parsing
4. Update the parser to detect property value changes

## Changes Made

### 1. Timestamp Regression Test (`test_timestamp_regression.py`)
Created a comprehensive regression test that validates timestamp extraction from all .oa files:
- Extracts the save timestamp from Table 0xC for each file
- Compares against known golden values
- Ensures timestamp parser remains correct across code changes
- **Result**: All 9 test files pass ✓

### 2. Property Value Record Type (`table_c_parser.py`)
Added new `PropertyValueRecord` class to identify and annotate property value references:
```python
@dataclass
class PropertyValueRecord:
    offset: int
    size: int
    data: bytes
    property_value_id: int  # The ID referencing a property value
```

### 3. Property Value Detection Logic
Implemented a post-processing pass (`_annotate_property_values()`) that:
- Scans GenericRecords for property value patterns
- Looks for small integers (20-200 range) in specific contexts
- Detects marker values (0xc8000000) that indicate property structures
- Promotes matching GenericRecords to PropertyValueRecords

### 4. Comparison Tool (`compare_property_values.py`)
Created a utility to compare property values between two files:
- Extracts all PropertyValueRecords from both files
- Reports added, removed, or changed property value IDs
- Useful for understanding structural changes between revisions

### 5. Comprehensive Test Suite (`test_table_c_parser.py`)
Implemented three test categories:
1. **Timestamp Extraction**: Validates all 9 files
2. **Property Value Detection**: Confirms expected IDs in key files
3. **Property Value Change Detection**: Verifies change detection between file pairs

## Key Findings

### Resistance Value Change (sch4.oa → sch5.oa)
- **Location**: Offset 0x02ec in Table 0xC
- **Change**: Property Value ID 68 (0x44) → 70 (0x46)
- **Interpretation**: Two new property values were inserted into the system's property value table
  - ID 69 likely represents the property name "r" (resistance)
  - ID 70 represents the value "2K"
- **Table 0xb**: Remained identical, confirming this was a value change, not a property type change

### Wire Connection Change (sch7.oa → sch8.oa)
- **Location**: Multiple NetUpdateRecords changed
- **Change**: Payload sizes increased (98 → 123 bytes at offset 0x06a4)
- **Interpretation**: Adding a wire creates connectivity data in NetUpdateRecords, not property changes
- **Property Values**: No property value IDs changed (both files show ID 76)

### Component Conversion (sch5.oa → sch6.oa)
- **Change**: PropertyValueRecord moved from offset 0x02ec to 0x02cc
- **Property Value ID**: Changed from 70 to 76
- **Interpretation**: Converting a resistor to a capacitor is essentially a delete+create operation

## Usage Examples

### Parse a file and see property values:
```bash
python parser.py sch5.oa
```

### Compare property values between files:
```bash
python compare_property_values.py sch4.oa sch5.oa
```

### Run regression tests:
```bash
python test_timestamp_regression.py
python test_table_c_parser.py
```

## Technical Details

### Property Value ID Structure
Property Value IDs are small integers (typically < 256) that serve as indices into the system's property value storage. The pattern observed:
- IDs increment sequentially when new values are added
- When a property value changes, the ID reference increments by the number of new values inserted
- Common patterns: IDs appear after marker value 0xc8000000 in the data stream

### Timestamp Location
The save timestamp is consistently found in Table 0xC as:
- A SeparatorRecord with marker 0xffffffff
- The last plausible timestamp in the table (after year 2000)
- Stored as a 32-bit Unix timestamp at offset +8 within the separator block

## Test Results
All tests pass successfully:
- ✓ Timestamp Extraction: 9/9 files
- ✓ Property Value Detection: 4/4 test cases
- ✓ Property Value Change Detection: 3/3 file pairs

## Conclusion
The Table 0xC parser now successfully:
1. Maintains correct timestamp extraction (with regression test)
2. Identifies property value references in the data structure
3. Highlights property value changes in parser output
4. Provides tools for comparing property values between file revisions

The resistance value change from 1K to 2K in sch4.oa → sch5.oa is now clearly visible as Property Value ID 68 → 70 at offset 0x02ec.
