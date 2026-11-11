# Gate 06 evidence inventory — 2026-11-11

Status: **preserved / secret-free inventory**

## Preserved operational evidence

The existing result JSONs and candidate logs were copied from `/tmp` into the
owner-controlled operational root:

`/Users/sonalingowda/alphalens-operational-20261105/research/gate06-development-20261111-92da190a/`

The directory mode is 700 and its files are mode 600. Verified result hashes:

| File | SHA-256 |
|---|---|
| `alpha-1.0-result.json` | `a0c97b6c6ca31fa095c9ab9086af6baa26b7568548bf6990d02c7006a7ce7bbf` |
| `alpha-0.1-result.json` | `ac0c249249e7c504aa464007220d92118447a910b9f5ee17ab46ee395561a692` |
| `alpha-10.0-result.json` | `c56cd2cf0fcd4c5addc9f531c3f4ad9c54adc52268195ea4ceeaadc6e6cd02b5` |

The two corresponding stdout logs were preserved without modification. Hashes
and file sizes were checked before and after copying. Raw market data was not
copied into the operational archive or GitHub.

## Provenance identity

- Development source: retained local artifact, SHA-256
  `f17dfdab0dfcaa1e24508d9484942eee6677c2e56ddb96869ce774e85ca80fbc`.
- Source identity: `BTCUSDT`, `5m`, 25,920 candles.
- Current source timestamp range: `2026-07-14T10:10:00Z` through
  `2026-10-12T10:05:00Z`.
- Historical result object: Git blob
  `1630b1ec2c66a5857c84d4e950650d7b5766b82d`.
- Historical runner object: Git blob
  `091cbe012c0b2a9a130b900c0c6baf9ed967d85d`.
- Active repository baseline: `92da190a0e9500425da7364ada0f0559cdf248df`.
- Research environment: Python 3.11.14, NumPy 2.4.6, scikit-learn 1.9.0,
  pandas 3.0.5, SciPy 1.17.1.

The historical runner worktree at `/tmp/alphalens-gate06-research.kUvh63` was
removed after execution as a disposable resource. Its absence is recorded;
the runner was not fabricated or silently regenerated. The source dataset,
protected-test data, credentials, and owner database were not copied.

## Gate status

The preserved results belong to the new development lineage and remain
negative evidence for the frozen correlation criterion. Gate 06 is not
validated. The inventory contains no model artifact or protected-test result.

