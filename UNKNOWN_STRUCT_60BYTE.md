# Separator-Based Structure - CORRECTED UNDERSTANDING

## ⚠️ IMPORTANT: Previous Understanding Was Wrong

This document describes a structure that was **MISUNDERSTOOD** in the original analysis. The key insight: **what we thought was a "signature" is actually DATA**.

## What Changed

### OLD (Wrong) Understanding
- Structure appears only in sch5-8
- Detected by looking for pattern `08 00 00 00 03 00 00 00`
- Mysteriously "disappears" in sch9+

### NEW (Correct) Understanding  
- Structure appears in **sch5-11** (7 files, not just 4)
- Detected by looking for **separator pattern** `00 00 00 c8 02 00 00 00 e8 00 1a 03`
- The `08 00 00 00` is **DATA**, not a signature - it changes to `03 00 00 00` in sch9+
- Structure doesn't disappear, it was just **not being detected** because we looked for the wrong thing

## Structure Layout

```
┌─────────────────────────────────────────────────────────────┐
│ Separator-Based Structure (appears in sch5-11)             │
├─────────────────────────────────────────────────────────────┤
│ Padding:  Variable (28-32 bytes, mostly zeros)             │
│ Payload:  Variable data values (12-16 bytes, 4-byte ints)  │
│ Marker:   0xffffffff (4 bytes, optional - only some files) │
│ Separator: 00 00 00 c8 02 00 00 00 e8 00 1a 03 (12 bytes)  │
└─────────────────────────────────────────────────────────────┘
```

## Observed Payload Values

The payload contains integer values that change across files:

| File    | Payload Values     | Notes                          |
|---------|--------------------|--------------------------------|
| sch5    | [8, 3, 0]          | Has 0xffffffff marker          |
| sch6    | [8, 3, 1, 2]       | No marker, 56 bytes total      |
| sch7    | [8, 3, 1, 2]       | No marker, 60 bytes total      |
| sch8    | [8, 3, 1, 2]       | No marker, 60 bytes total      |
| sch9    | [3, 3, 0]          | Has 0xffffffff marker          |
| sch10   | [3, 3, 0]          | Has 0xffffffff marker          |
| sch11   | [8, 4, 0]          | Has 0xffffffff marker          |

## Key Insights

### 1. The "Signature" Was Actually Data
The bytes `08 00 00 00 03 00 00 00` are **not** a signature for structure detection. They are **payload values**:
- First int: 8 in sch5-8,11 but **changes to 3** in sch9-10
- Second int: Always 3 (except sch11 where it's 4)

### 2. The Reliable Anchor is the Separator
The **only** reliable pattern is the separator: `00 00 00 c8 02 00 00 00 e8 00 1a 03`

This appears at the end of the structure in all files.

### 3. Variable Size
The structure is **not** a fixed 60 bytes:
- sch6: 56 bytes
- Other files: 60 bytes

The difference is due to:
- Variable padding at the start
- Optional 0xffffffff marker before separator
- Variable payload length

## Detection Method

The correct way to detect this structure:

1. **Search for separator pattern** `00 00 00 c8 02 00 00 00 e8 00 1a 03`
2. **Work backwards** from the separator
3. Check for optional 0xffffffff marker (4 bytes before separator)
4. Extract payload (non-zero values before marker/separator)
5. Extract padding (zeros at the beginning)

## Files With/Without Structure

### Files WITH Structure (7 total)
- ✓ sch5.oa
- ✓ sch6.oa
- ✓ sch7.oa
- ✓ sch8.oa
- ✓ sch9.oa
- ✓ sch10.oa
- ✓ sch11.oa

### Files WITHOUT Structure (12 total)
- sch12.oa, sch13.oa, sch14.oa, sch15.oa, sch16.oa, sch17.oa, sch18.oa
- sch_old.oa, sch_new.oa, sch2.oa, sch3.oa, sch4.oa

## What This Structure Might Be

Based on the payload values changing over time, this appears to be:
- **Dynamic metadata** that tracks some counters or state
- Related to component operations (values change when components are added/modified)
- Not a fixed configuration, but live data

The first value changes from 8 to 3 between sch8 and sch9, suggesting it might track:
- Number of components/connections
- Operation counter
- State machine value

## Implementation Details

### Parser Changes
The parser (`table_c_parser.py`) now:
1. Searches for the separator pattern (not a fixed "signature")
2. Works backwards to extract payload
3. Handles both with/without 0xffffffff marker
4. Correctly identifies the structure in all 7 files

### Class: UnknownStruct60Byte
Despite the name (kept for backward compatibility), this now:
- Stores variable-length payload (not fixed 60 bytes)
- No longer checks for a "config_pattern" (it's empty)
- Displays payload as integer values
- Shows whether 0xffffffff marker is present

## Recommendations

### DO:
- ✓ Use separator pattern for detection
- ✓ Treat payload as dynamic data that changes
- ✓ Understand this appears in sch5-11 (not just sch5-8)
- ✓ Handle variable structure size

### DO NOT:
- ❌ Assume payload values are fixed
- ❌ Look for "signature" patterns in payload
- ❌ Expect fixed 60-byte size
- ❌ Claim to understand what the values mean

## Conclusion

The original analysis was **fundamentally wrong** about how to detect this structure. By treating data values as signatures, we missed the structure in files sch9-11.

The correct understanding:
- **Separator pattern is the anchor** for detection
- **Payload values are dynamic data** that change over time
- **Structure appears in 7 files** (sch5-11), not 4
- **Size is variable** (56-60 bytes), not fixed

This is a significant correction that changes our understanding of the .oa file format.
