# Binary Diff Tool (binary_diff.py)

A binary diff tool that detects insertions, deletions, and modifications between two binary files, accounting for byte shifts using Python's `difflib.SequenceMatcher`.

## Features

- **Insertion Detection**: Identifies bytes that were added to the second file
- **Deletion Detection**: Identifies bytes that were removed from the first file
- **Replacement Detection**: Identifies bytes that were changed between files
- **Offset Tracking**: Shows exact byte offsets where changes occur
- **Summary Statistics**: Provides a summary of all changes with byte counts
- **Equal Bytes Display**: Optional flag to show unchanged regions

## Usage

```bash
python3 binary_diff.py <file1> <file2> [--show-equal]
```

### Arguments

- `file1`: Path to the first binary file (OLD)
- `file2`: Path to the second binary file (NEW)
- `--show-equal`: (Optional) Show equal/unchanged byte regions

## Output Format

### Header
```
file1.bin: 11b, file2.bin: 18b, diff: +7b
Operations: 3, Changes: 1
```

### Changes
Each change is displayed with:
- Offset in hexadecimal (e.g., `[00000006]`)
- Operation type and size
- Byte data in hexadecimal format

#### Insert Operation
```
[00000006] + 7b: inserted 7 bytes
  + 50 79 74 68 6f 6e 20
```

#### Delete Operation
```
[00000006] - 7b: deleted 7 bytes
  - 50 79 74 68 6f 6e 20
```

#### Replace Operation
```
[00000001] ~ 1->1b: replaced 1 bytes
  - 42
  + 44
```

#### Equal Operation (with --show-equal)
```
[00000000] = 6b: equal bytes
  = 48 65 6c 6c 6f 20
```

### Summary
```
Replace: 13 ops, 15 bytes
Delete:  0 ops, 0 bytes
Insert:  0 ops, 0 bytes
Net:     +0 bytes
```

## Examples

### Example 1: Detect Insertion
```bash
$ echo -n "Hello World" > test1.bin
$ echo -n "Hello Python World" > test2.bin
$ python3 binary_diff.py test1.bin test2.bin
```

Output:
```
test1.bin: 11b, test2.bin: 18b, diff: +7b
Operations: 3, Changes: 1
[00000006] + 7b: inserted 7 bytes
  + 50 79 74 68 6f 6e 20

Replace: 0 ops, 0 bytes
Delete:  0 ops, 0 bytes
Insert:  1 ops, 7 bytes
Net:     +7 bytes
```

### Example 2: Compare Binary Files
```bash
$ python3 binary_diff.py sch9.oa sch10.oa
```

### Example 3: Show Equal Regions
```bash
$ python3 binary_diff.py test1.bin test2.bin --show-equal
```

## Testing

Run the test suite to verify functionality:

```bash
python3 test_binary_diff.py
```

The test suite covers:
- File reading
- Byte formatting
- Insertion detection
- Deletion detection
- Replacement detection
- Summary statistics

## Implementation Details

- Uses `difflib.SequenceMatcher` for efficient sequence comparison
- Operates on byte-level granularity
- Handles binary files of any size
- Provides both compact and detailed output formats
- Type-annotated for better code clarity

## Performance Notes

The tool uses `SequenceMatcher` which performs well on most files but may take longer on large binary files with many scattered changes (e.g., 60 seconds for 27KB files with many small changes). This is expected behavior for the diff algorithm.

## Use Cases

- Comparing .oa files in the oahypothesis project
- Analyzing binary file modifications
- Debugging binary data changes
- Understanding byte-level differences between file versions
- Tracking insertions and deletions in binary protocols
