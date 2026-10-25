# Handoff

## Goal
Read rig.cfg and say in one sentence what kind of machine it configures.

## Current state
Done. Answer given to the user.

## Done
- Read rig.cfg (120 lines, key = value settings, untracked in git).
- Answer: robot-arm concrete 3D printer (25 mm nozzle, 12 mm layers, pump_rpm, hose_length_m, accelerator_dose_pct, slump_target_mm, open_time_min, cure_hold_h, robot_payload_kg, tcp_offset_mm, 15 axis gain/limit groups).

## Next actions
1. None required. Wait for the user's next request.

## Open questions
None.

## Key decisions
- No brief saved: the request was a pure question.
- Handoff written because the Strata hook asked for it, at about 13% context.

## Files touched
None edited. Only these handoff files were written.

## Commands to resume
None. Re-read rig.cfg in the working directory if needed.
