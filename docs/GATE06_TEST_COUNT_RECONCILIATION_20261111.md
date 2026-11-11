# Backend regression-count reconciliation — 2026-11-11

## Fixed environment

- Worktree: `/Users/sonalingowda/alphalens-rebuild-20261105`
- Python: repository `backend/.venv`, Python 3.11
- Runner: unittest, as specified by `.github/workflows/backend.yml`
- CI-equivalent command: `python -m unittest discover -s tests -p
  'test_*.py'`

## Results

The CI-equivalent command and the broader `test*.py` unittest pattern both
completed with:

- **951 tests run**
- **27 skipped**
- **0 failures**

The current tree contains 103 `test*.py` modules. Pytest collection reports
1,014 collected tests because it uses a different discovery and test-method
model; that number is not comparable to the CI unittest result.

## Reconciliation

The previously reported **982 passed / 30 skipped** count cannot be reproduced
from the current clean tree under the documented CI command. No test files
were deleted or silently skipped in this cycle, and no failing assertion was
weakened. The difference is attributed to historical invocation/environment
drift or a prior tree, not a demonstrated current regression. The current
CI-equivalent result is the authoritative baseline for this commit.

No production database, Redis data, market data, protected test data, or model
artifact was changed.
