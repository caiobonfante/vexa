# /test -- Full Helm deployment test

1. Validate templates: `helm template` for both charts
2. Dry-run install for both charts
3. If cluster available: deploy and verify pods
4. Check all services have endpoints
5. Verify ingress routing
6. Check secrets and PVCs
7. Test bot RBAC (can spawn pods)
8. Hit health endpoints on each service
9. Report PASS/FAIL per check
