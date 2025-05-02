
from services.test_runner import TestRunner
import sys

if __name__ == '__main__':
    if len(sys.argv) > 1:
        # Run specific test module
        test_name = sys.argv[1]
        TestRunner.run_specific_test(test_name)
    else:
        # Run all tests
        TestRunner.run_all_tests()
