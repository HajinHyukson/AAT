# Kenneth French Adapter

Source: Kenneth French Data Library at Dartmouth.

The adapter currently targets the daily Fama/French 5 Factors CSV zip:

`https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/ftp/F-F_Research_Data_5_Factors_2x3_daily_CSV.zip`

## Timestamp Policy

The public CSV zip is a current file, not a point-in-time vintage feed. Parsed factor rows use:

- `event_time`: the factor date from the file
- `ingestion_time`: when this system downloaded or loaded the file
- `timestamp_available`: the same as `ingestion_time`

This is conservative for historical replay. A real point-in-time factor archive can later replace this timestamp policy.
