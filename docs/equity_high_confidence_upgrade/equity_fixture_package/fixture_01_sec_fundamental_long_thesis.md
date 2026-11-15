# Fixture 1 - SEC Fundamental Long Thesis

Status: fixture specification complete; runtime execution not performed in this pass.

## Graph Path

```text
SEC filing -> XBRL facts -> fundamental attributes -> valuation assumptions -> thesis object -> insight -> quality-value profile -> investment memo -> validation report -> rights report
```

## Required Checks

- SEC 10-K/10-Q accepted_at used as available_at
- Restated values blocked before availability
- Valuation assumptions separated from facts
- Memo claims have evidence refs
- Restricted inputs redacted

## Failure Cases

- missing accepted_at blocks backtest
- terminal value sensitivity missing creates warning
- provider peer data blocks export

## Expected Result

The fixture should produce output only after PIT, rights, evidence, profile, and validation gates pass.
