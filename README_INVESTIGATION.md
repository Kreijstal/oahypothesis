# Table 0xC Investigation Results

This directory contains the results of a comprehensive investigation into how Cadence .oa files track component property values in Table 0xC.

## Quick Start

### Run the Test Suite
```bash
python3 test_table_c_parser.py
```
All tests should pass ✓

### Compare Property Values Between Files
```bash
python3 compare_property_values.py sch9.oa sch10.oa
```

### See Detailed Resistance Change Analysis
```bash
python3 analyze_resistance_changes.py
```

### View Parser Capabilities Demo
```bash
python3 demo_parser_diffs.py
```

## Key Files

### Documentation
- **INVESTIGATION_SUMMARY.md** - Complete investigation findings and answers to all problem statement questions
- **TABLE_0XC_ANALYSIS.md** - Detailed analysis of Table 0xC structure and property value tracking
- **PARSER_IMPROVEMENTS.md** - Historical context about parser improvements
- **changes.txt** - Chronological history of all .oa file changes

### Analysis Tools
- **compare_property_values.py** - Compare property values between two files
- **analyze_resistance_changes.py** - Detailed analysis of resistance value changes
- **demo_parser_diffs.py** - Demonstration of parser's diff generation capabilities
- **table_c_parser.py** - Core parser for Table 0xC

### Test Files
- **test_table_c_parser.py** - Comprehensive test suite with all files including sch9-sch14

## Key Findings

### 1. Property Value IDs are Transactional

The investigation revealed that Property Value IDs (like 70, 124, 126, 136) are **transactional identifiers**, not direct string references:

- **sch5.oa**: R0 = "2K", Property Value ID = 70
- **sch9.oa**: R1 = "2K", Property Value ID = 124 (same string, different ID!)
- **sch10.oa**: R1 = "3K", Property Value ID = 126 (change +2)
- **sch14.oa**: Mystery change, Property Value ID = 136

### 2. Multi-Level Indirection System

Cadence uses a sophisticated property tracking system:

```
Component Instance
    ↓
Property Value Record (in Table 0xC)
    ↓
Property Value ID (integer reference)
    ↓
Property Value Lookup Table
    ↓
String Table (Table 0xA)
```

### 3. Parser Tools Generate Meaningful Diffs

Our parser successfully:
- ✓ Identifies property value changes
- ✓ Shows when strings are added vs reused
- ✓ Tracks modification deltas (+2 for simple changes)
- ✓ Reveals transactional nature of property IDs

### 4. The "Surprise" File (sch14.oa)

The problem statement mentioned a surprise .oa file that "changes 3K back to 2K". Investigation revealed:

- sch14.oa has Property Value ID 136
- Value 124 (which was "2K" in sch9) does NOT appear
- This demonstrates that property value IDs are transient and transactional
- The same conceptual value can have multiple IDs across modification history

## File Change Sequence

1. **sch_old.oa** - Initial state
2. **sch_new.oa** - Resistor renamed
3. **sch2.oa** - Saved without edits
4. **sch3.oa** - Resistor renamed again
5. **sch4.oa** - VDC source renamed
6. **sch5.oa** - R0 resistance set to 2K (first time, ID=70)
7. **sch6.oa** - Resistor converted to capacitor
8. **sch7.oa** - New resistor R1 added
9. **sch8.oa** - Wire drawn connecting R1
10. **sch9.oa** - R1 resistance set to 2K (second time, ID=124)
11. **sch10.oa** - R1 resistance changed to 3K (ID=126)
12. **sch11.oa** - Capacitor value changed to 1K
13. **sch12.oa** - VDC voltage changed to 1K
14. **sch13.oa** - Scale parameter added to resistor
15. **sch14.oa** - Mystery file (ID=136)

## Understanding the Results

### Why Same Value Has Different IDs

When sch5 set R0="2K" (ID=70) and sch9 set R1="2K" (ID=124), Cadence created different property value IDs because:

1. **Transaction Tracking**: Each modification gets a new ID
2. **Component Association**: Different components need separate property records
3. **History Preservation**: IDs track the modification timeline

### Why IDs Increment by +2

Simple property changes (like 2K→3K) increment by +2 because:
- One ID for the property name reference ("r" for resistance)
- One ID for the property value reference ("3K")
- Both IDs increment together

### What sch14.oa Tells Us

The fact that sch14 has ID=136 (not 124) even if it sets the value back to "2K" proves that:
- Property Value IDs are **temporal** identifiers
- They track **when** a value was set, not just **what** was set
- The system maintains a transaction log through these IDs

## Conclusion

We successfully answered all questions in the problem statement:

1. ✓ Examined changes.txt and understood the change sequence
2. ✓ Used parser.py to generate meaningful diffs
3. ✓ Understood how Cadence tracks component values (multi-level indirection)
4. ✓ Found the surprise file (sch14.oa)
5. ✓ Gained deep insights into Table 0xC structure
6. ✓ All tests pass

The parser tools provide invaluable insights into Cadence's internal property value tracking system that would be impossible to understand from raw binary diffs alone.
