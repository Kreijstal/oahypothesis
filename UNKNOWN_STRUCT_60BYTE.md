# UnknownStruct60Byte - HYPOTHETICAL STRUCTURE

## ⚠️ WARNING: LIMITED UNDERSTANDING

This document describes a **HYPOTHETICAL** structure that we do NOT fully understand. It should be treated with extreme caution.

## Critical Limitations

### 1. **Appears Only in sch5-8, Disappears After**
The structure is detected in files sch5, sch6, sch7, and sch8, but **completely disappears** in sch9 and all subsequent files.

This suggests:
- It may be **transient metadata** created during certain operations
- It is NOT a stable format feature
- Our understanding is incomplete

### 2. **"Footer" is Actually a Separator**
What we initially thought was a stable "footer" pattern is actually a **separator record** (0xffffffff marker). This is NOT a structural boundary.

### 3. **"Config" Pattern is Unstable**
The pattern `08 00 00 00 03 00 00 00` appears in sch5-8 but disappears in sch9+, confirming it's not a reliable identifier.

## What We Actually Observed

### Structure Layout (60 bytes in sch5-8)
```
┌─────────────────────────────────────────────────────────────┐
│ UnknownStruct60Byte (HYPOTHETICAL)                         │
├─────────────────────────────────────────────────────────────┤
│ Padding:  Variable (~32 bytes, mostly zeros)               │
│ Pattern:  08 00 00 00 03 00 00 00 (8 bytes) - UNSTABLE!    │
│ Payload:  Variable (4-byte aligned)                        │
│ Trailing: ff ff ff ff 00 00 00 c8 02 00 00 00 e8 00 1a 03 │
│           (16 bytes - actually a SEPARATOR, not a footer!) │
└─────────────────────────────────────────────────────────────┘
```

### Appearance Timeline (from changes.txt)
- **sch5**: First appearance (resistor resistance set to 2K)
- **sch6**: Still present (resistor converted to capacitor)
- **sch7**: Still present (new resistor added)
- **sch8**: Last appearance (wire drawn)
- **sch9**: GONE (R1 resistance changed to 2K)

### Why It Disappears
After sch8, when connectivity changes happen (wire drawing), the structure disappears. This suggests it may be:
- Temporary metadata during property setting operations
- Replaced by a different structure after connectivity is established
- Not a permanent part of the file format

## Implementation Details

### Detection Logic
The parser uses `_check_and_claim_unknown_struct()` to detect this pattern, but the detection is fragile:

1. Searches for pattern `08 00 00 00 03 00 00 00`
2. Checks if data ends with `00 00 00 c8 02 00 00 00 e8 00 1a 03`
3. Both conditions MUST match (fails in sch9+)

### Why We Renamed It
Originally called `GeometryManagerRecord` (based on a string reference `sch.ds.gm.1.4`), but:
- The string reference is NOT in the structure itself
- The structure's purpose is unknown
- The name implied we understood it (we don't)

New name `UnknownStruct60Byte` is honest about our limited knowledge.

## Test Coverage

### Files WITH Structure
- ✓ sch5.oa
- ✓ sch6.oa
- ✓ sch7.oa
- ✓ sch8.oa

### Files WITHOUT Structure
- sch9.oa, sch10.oa, sch11.oa, sch12.oa, sch13.oa, sch14.oa, sch15.oa, sch16.oa, sch17.oa, sch18.oa
- sch_old.oa, sch_new.oa, sch2.oa, sch3.oa, sch4.oa

## Recommendations

### DO NOT:
- ❌ Assume this is a stable format feature
- ❌ Use it for critical parsing decisions
- ❌ Claim to understand its purpose
- ❌ Build functionality that depends on it

### DO:
- ✓ Treat it as a research curiosity
- ✓ Document when it appears/disappears
- ✓ Keep the parser flexible for when it's absent
- ✓ Consider it might be removed in future refactoring

## Conclusion

This structure is **NOT WELL UNDERSTOOD**. It appears briefly in 4 files and then disappears. What we thought was a "footer" is actually a separator. What we thought was stable "config" data is actually transient.

The honest conclusion: **We don't know what this is.** It may be:
- Transient metadata during certain operations
- A format quirk that gets cleaned up later
- Something we're completely misinterpreting

Until we understand it better, it should be treated as **hypothetical** and not relied upon for any critical functionality.

## Further Investigation Needed

To truly understand this structure, we would need to:
1. Analyze the raw bytes in more detail across all files
2. Understand why it disappears after sch8
3. Determine if the "pattern" and "separator" are actually related
4. Find documentation or reverse engineer the actual format

Without this, the structure remains a mystery.
