
import unittest
import sys
from tests.test_batch_inventory import *
from tests.test_check_stock import *
from tests.test_unit_conversion import *

class TestRunner:
    @staticmethod
    def run_all_tests():
        """Run all test cases"""
        loader = unittest.TestLoader()
        start_dir = 'tests'
        suite = loader.discover(start_dir, pattern='test_*.py')
        runner = unittest.TextTestRunner(verbosity=2)
        return runner.run(suite)

    @staticmethod
    def run_specific_test(test_name):
        """Run a specific test module"""
        loader = unittest.TestLoader()
        try:
            suite = loader.loadTestsFromName(f'tests.{test_name}')
            runner = unittest.TextTestRunner(verbosity=2)
            return runner.run(suite)
        except Exception as e:
            print(f"Error loading test {test_name}: {str(e)}")
            return None
