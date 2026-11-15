# Fixture 2 - Earnings Event / PEAD

Status: fixture specification complete; runtime execution not performed in this pass.

## Graph Path

```text
earnings release -> surprise/guidance event -> price reaction -> event materiality -> PEAD candidate insight -> event profile -> catalyst board -> PIT validation
```

## Required Checks

- event available_at precedes decision cutoff
- estimate/news rights reviewed
- stale event handled
- transaction-cost warning included

## Failure Cases

- estimate history missing downgrades insight
- same-day close lookahead blocks test
- stale event state suppresses action

## Expected Result

The fixture should produce output only after PIT, rights, evidence, profile, and validation gates pass.
