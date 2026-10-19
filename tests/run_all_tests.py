"""Master test runner for Team Echo recommendation system and Rocky API.

Executes all test suites matching the reference testing pattern:
    python tests/run_all_tests.py
"""
import sys
from pathlib import Path

TESTS_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = TESTS_DIR.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
if str(TESTS_DIR) not in sys.path:
    sys.path.insert(0, str(TESTS_DIR))

import test_analyzer
import test_prompts
import test_recommendation
import test_api

SUITES = [
    ("Deterministic Weakness Analyzer", test_analyzer.main),
    ("Prompt Construction", test_prompts.main),
    ("Recommendation Engine & Fallbacks", test_recommendation.main),
    ("Rocky API & Client Integration", test_api.main),
]


def main():
    print("=" * 60)
    print("RUNNING ALL TEAM ECHO RECOMMENDATION & API TESTS")
    print("=" * 60)

    for name, suite_main in SUITES:
        print(f"\n>> Running suite: {name}")
        suite_main()

    print("\n" + "=" * 60)
    print("ALL TEST SUITES PASSED SUCCESSFULLY!")
    print("=" * 60)


if __name__ == "__main__":
    main()

