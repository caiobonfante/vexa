# Mission

Focus: conductor
Problem: need to verify Stop hook loop works — agent must be forced to continue when target not met
Target: create conductor/test-loop-output.md with exactly 3 sections, each added in a separate attempt. The file must contain "## Attempt 1", "## Attempt 2", "## Attempt 3" with timestamps. Dev must NOT write all 3 at once — write one, try to stop, get forced back by Stop hook, write next.
Stop-when: file has all 3 sections
Constraint: only touch conductor/test-loop-output.md. Validator must confirm each section was added in a separate pass (check timestamps are different).
