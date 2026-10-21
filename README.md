# SWE-MAIN

## Pull requests

1. Push your branch and open a pull request.
2. Wait for **Python tests** in the PR’s **Checks** tab to pass. Tests run automatically.
3. If tests fail, open the failed check to see the errors, fix them, and push again.
4. Merge once tests pass and required reviews are complete.

To run tests locally before pushing:

```bash
python -m pip install -r requirements-dev.txt
python -m pytest
```
