# Binary Curator Documentation Update

## Summary

This update adds comprehensive documentation about the **binary_curator principle** to ensure that all claimed data must be printed or asserted. This addresses the issue where parsers were claiming large blocks of data (e.g., 716 bytes) but only showing summary information without printing the actual data.

## Changes Made

### 1. Created `.github/copilot/instructions.md`

This file contains detailed instructions for both human developers and AI agents about the binary_curator rules:

- **The Cardinal Rule**: Every byte claimed MUST be interpreted or asserted
- **The Worst Mistake**: Claiming data without printing it
- **Lossless Philosophy**: All data must be accounted for
- Examples of good vs bad practices
- Guidelines for parser development

### 2. Updated `oaparser/binary_curator.py`

Added comprehensive module-level documentation explaining:

- The binary curator principle with concrete examples
- What constitutes correct vs incorrect usage
- Lossless data philosophy with 4 key principles
- Documentation on the `claim()` method emphasizing the rule

### 3. Fixed `table_c_parser.py` TableHeader Class

**Before (BAD):**
```python
def __str__(self):
    return f"Header ID: {self.header_id}, Pointers: {len(self.pointers)}"
```
Output: `[Table Header] Size: 716 bytes Header ID: 4, Pointers: 89`
❌ 716 bytes claimed but only 2 values shown!

**After (GOOD):**
```python
def __str__(self):
    lines = [f"Header ID: {self.header_id}, Pointers: {len(self.pointers)}"]
    if self.internal_pointers:
        lines.append("  Internal Pointers:")
        # ... prints all pointers with lossless summarization of repeated zeros
    return "\n".join(lines)
```
Output: Shows all 89 pointers (50 individual + 39 summarized zeros)
✓ All 716 bytes accounted for!

## Verification

### Test Results

1. **test_binary_curator.py**: ✅ All tests pass
2. **test_table_c_parser.py**: ✅ All tests pass
3. **Manual verification**: `python parser.py sch_old.oa` now shows all pointer data

### Output Comparison

**Before:**
```
[Table Header]  Offset: 0x0, Size: 716 bytes  Header ID: 4 (0x4), Pointers: 89
```

**After:**
```
[Table Header]  Offset: 0x0, Size: 716 bytes Header ID: 4 (0x4), Pointers: 89
    Internal Pointers:
      [000]: 0x00000000000002cc
      [001]: 0x000000100000001d
      ...
      [049]: 0x0000000000000004
      [050-088]: 0x0000000000000000 (repeats 39 times)
```

## Key Principles Documented

1. **ALL claimed data must be printed or asserted**
2. **Repeated patterns can be summarized LOSSLESSLY**
   - ✓ "0x00000000 x50" is acceptable
   - ❌ "716 bytes" without content is NOT
3. **Unknown data should remain UNCLAIMED**
4. **Assert known patterns explicitly**

## Why This Matters

Binary reverse engineering is about **understanding data formats**. When a parser claims bytes without printing them, it:
- Hides information that could be crucial for understanding
- Makes it impossible to verify the parser's interpretation
- Defeats the entire purpose of lossless parsing

This principle **cannot be programmatically tested** but must be enforced by both human reviewers and AI agents working with the codebase.

## Files Modified

- `.github/copilot/instructions.md` (created)
- `oaparser/binary_curator.py` (documentation added)
- `table_c_parser.py` (TableHeader.__str__() fixed)

## For Future Development

When creating or modifying parsers:
1. Always ensure `__str__()` methods print ALL claimed data
2. Use lossless summarization for repeated patterns
3. Leave unknown data unclaimed rather than claim it incompletely
4. Reference `.github/copilot/instructions.md` for guidelines
