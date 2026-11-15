# Fixture 5 - Rights/Redaction Package Test

Status: fixture specification complete; runtime execution not performed in this pass.

## Graph Path

```text
mixed public + licensed + restricted sources -> output view -> package preview -> redaction -> source-rights report -> blocked export where required
```

## Required Checks

- restrictive rights policy wins
- raw provider data blocked from export
- derived-only outputs flagged
- package report explains redaction

## Failure Cases

- unknown rights blocks package
- licensed raw field redacted
- mixed-source insight inherits most restrictive policy

## Expected Result

The fixture should produce output only after PIT, rights, evidence, profile, and validation gates pass.
