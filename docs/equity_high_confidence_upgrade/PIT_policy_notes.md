# PIT Policy Notes

Status: accepted for Status 6.5.

Every data-dependent object must distinguish observed_at, available_at, and retrieved_at. Filing facts use accepted/filed timestamps, not fiscal period end. 13F holdings are lagged and cannot be treated as current. Macro backtests require ALFRED-style vintages when series are revised. Provider-normalized fields require source_version and license status.
