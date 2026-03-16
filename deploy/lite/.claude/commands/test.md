# /test -- Full Lite deployment test

1. Build image: `docker build -f deploy/lite/Dockerfile.lite -t vexa-lite:test .`
2. Record image size: `docker images vexa-lite:test --format '{{.Size}}'`
3. Start container with test env vars
4. Wait 20s for supervisord startup
5. Check all supervisord programs are RUNNING
6. Hit API Gateway at :8056
7. Create test user + token via admin API
8. Verify DB tables exist
9. Verify internal Redis is healthy
10. Report PASS/FAIL per check
11. Cleanup: stop + remove container
