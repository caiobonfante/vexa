# Mission

Focus: telegram-chat
Problem: services/telegram-bot, services/agent-api, services/runtime-api, services/admin-api lack structured README.md with constraints. The conductor can't enforce service boundaries because there's nothing to enforce.
Target: each of these 4 directories has a README.md with: Why, Data Flow (ASCII), Code Ownership, Constraints, Known Issues. Format matches features/.readme-template.md style.
Stop-when: target met OR 3 iterations
Constraint: do NOT change any code. Only create/update README.md files. Read existing code to understand what each service does, then document it honestly.
