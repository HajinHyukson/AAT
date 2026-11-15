# Fixture 4 - Portfolio Risk Radar

Status: fixture specification complete; runtime execution not performed in this pass.

## Graph Path

```text
holdings -> factor/sector/liquidity exposures -> concentration and risk contribution -> portfolio insight -> rebalance or hedge output
```

## Required Checks

- stock insight does not automatically become portfolio action
- user holdings private
- mandate required before sizing
- liquidity/capacity gate visible

## Failure Cases

- missing mandate blocks sizing
- private holdings blocked from package
- liquidity breach caps position

## Expected Result

The fixture should produce output only after PIT, rights, evidence, profile, and validation gates pass.
