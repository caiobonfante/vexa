# /test -- Full compose deployment test

1. Stop existing stack: `make down`
2. Clean .env: `rm -f .env`
3. Run `make all` -- report each step
4. Verify all services: `make ps`
5. Hit every endpoint
6. Create test user + token
7. Verify DB + Redis
8. Report PASS/FAIL per check
9. Clean up test data
