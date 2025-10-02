#!/bin/bash
# Test script for OA file analysis tools

echo "======================================"
echo "OA File Analysis Tools Test Suite"
echo "======================================"
echo ""

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Test counter
TESTS_PASSED=0
TESTS_FAILED=0

# Test function
run_test() {
    local test_name="$1"
    local command="$2"
    
    echo -n "Testing: $test_name ... "
    
    if eval "$command" > /dev/null 2>&1; then
        echo -e "${GREEN}PASS${NC}"
        ((TESTS_PASSED++))
        return 0
    else
        echo -e "${RED}FAIL${NC}"
        ((TESTS_FAILED++))
        return 1
    fi
}

# Test 1: parser.py can parse sch_old.oa
run_test "parser.py on sch_old.oa" \
    "python3 parser.py sch_old.oa"

# Test 2: parser.py can parse sch_new.oa
run_test "parser.py on sch_new.oa" \
    "python3 parser.py sch_new.oa"

# Test 3: parser.py --hexdump mode
run_test "parser.py --hexdump mode" \
    "python3 parser.py sch_old.oa --hexdump"

# Test 4: compare_tables.py
run_test "compare_tables.py" \
    "python3 compare_tables.py sch_old.oa sch_new.oa"

# Test 5: compare_tables.py (replaces analyze_changes.py)
run_test "compare_tables.py (replaces analyze_changes.py)" \
    "python3 compare_tables.py sch_old.oa sch_new.oa"

# Test 6: String table finds "popop" in sch_old.oa
run_test "Find 'popop' in sch_old.oa" \
    "python3 parser.py sch_old.oa | grep -q 'popop'"

# Test 7: String table finds "THISISNOWTHERESISTOR" in sch_new.oa
run_test "Find 'THISISNOWTHERESISTOR' in sch_new.oa" \
    "python3 parser.py sch_new.oa | grep -q 'THISISNOWTHERESISTOR'"

# Test 8: compare_tables detects 7 changed tables
run_test "Detect 7 changed tables" \
    "python3 compare_tables.py sch_old.oa sch_new.oa | grep -q 'Tables that changed: 7'"

# Test 9: compare_tables detects string addition
run_test "Detect string addition" \
    "python3 compare_tables.py sch_old.oa sch_new.oa | grep -q 'THISISNOWTHERESISTOR'"

# Test 10: String table size increase detected
run_test "Detect string table size increase" \
    "python3 compare_tables.py sch_old.oa sch_new.oa | grep -q '+20 String Table'"

echo ""
echo "======================================"
echo "Test Results:"
echo "======================================"
echo -e "Passed: ${GREEN}$TESTS_PASSED${NC}"
echo -e "Failed: ${RED}$TESTS_FAILED${NC}"
echo "Total:  $((TESTS_PASSED + TESTS_FAILED))"
echo ""

if [ $TESTS_FAILED -eq 0 ]; then
    echo -e "${GREEN}All tests passed!${NC}"
    exit 0
else
    echo -e "${RED}Some tests failed.${NC}"
    exit 1
fi
