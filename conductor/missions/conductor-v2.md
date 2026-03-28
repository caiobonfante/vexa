# Mission

Focus: conductor
Problem: delivery stage is sequential (dev then evaluator) — validator catches issues too late. Human can only intervene via stop file. Completion check has false positives.
Target: TeamCreate-based delivery (dev + validator collaborate in real-time), chat-based intervention, accurate completion check. All three FAIL items in quality bar → PASS.
Stop-when: target met OR 5 iterations
Constraint: keep the dumb loop (run.sh). Replace what it spawns, not the loop itself. Don't break existing missions, dashboard, or pre-merge gate.
