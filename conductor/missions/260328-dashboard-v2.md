# Mission

Focus: conductor
Problem: dashboard doesn't show phase (plan/deliver/evaluate), team activity is invisible during runs, layout is confusing — can't tell what's happening at a glance

Target:
1. Phase indicator at top: PLAN / DELIVER / EVALUATE with mission name
2. During delivery: show team messages (dev/validator conversation) parsed from stream in real-time
3. Clean layout: phase + summary at top, team activity center, scores sidebar

Definition of Done:
- Dashboard shows current phase from state.json
- During a run, clicking a mission shows dev/validator messages (not just raw tool calls)
- After run, shows validator verdict prominently

Stop-when: target met OR 3 iterations
Constraint: single HTML file + dashboard.py. No new dependencies. Keep existing API endpoints working. parse-stream.py can be enhanced to extract team messages.
