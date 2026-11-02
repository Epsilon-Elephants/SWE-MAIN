"""Run the recommendation suites with pytest's offline fixtures enabled."""
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def main():
    return pytest.main([
        "-c", str(PROJECT_ROOT / "pytest.ini"),
        *[str(PROJECT_ROOT / "tests" / f"test_{name}.py") for name in (
            "analyzer", "prompts", "recommendation", "data_adapter", "api",
        )],
    ])


if __name__ == "__main__":
    sys.exit(main())
