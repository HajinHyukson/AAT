# Fixture 3 - Short Red-Flag Monitor

Status: fixture specification complete; runtime execution not performed in this pass.

## Graph Path

```text
filings + accounting attributes -> accrual/red-flag screen -> deterioration signal -> borrow/squeeze gate -> short thesis object -> legal/human-review warning -> risk dashboard
```

## Required Checks

- borrow data treated as licensed
- squeeze risk can block or limit action
- fraud language requires human review
- negative thesis has invalidation conditions

## Failure Cases

- borrow unavailable blocks short action
- unsupported accusation redacted
- missing invalidation downgrades thesis

## Expected Result

The fixture should produce output only after PIT, rights, evidence, profile, and validation gates pass.
