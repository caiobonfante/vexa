# Mission

Focus: conductor
Problem: TeamCreate wired into run.sh but untested. Completion check has false positives ("pass" anywhere triggers "met"). Old run_evaluator() is dead code.

Target:
1. TeamCreate delivery works end-to-end: run a test mission → dev + validator collaborate via SendMessage → validator writes verdict → conductor reads it → loop decides
2. Completion check fixed: score-based targets work accurately, descriptive targets don't false-positive on the word "pass"
3. Dead code removed: old run_evaluator() function cleaned out of run.sh

Definition of Done:
- Run conductor-v2 test mission → batch log shows TeamCreate + dev/validator messages
- Run with descriptive target → completion check does NOT false-positive
- run.sh has no dead evaluator code

Stop-when: target met OR 3 iterations
Constraint: don't break existing dashboard, state.json format, or pre-merge gate. Keep the dumb loop. The team prompt is in run.sh, not a separate file.
