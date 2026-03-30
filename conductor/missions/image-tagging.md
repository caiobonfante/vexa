# Mission

Focus: deployment infrastructure
Problem: Image tagging is ad-hoc. Compose builds produce unnamed images, Helm uses untraceable mutable tags (`:local`, `:staging`). During dev, you can't tell which build is running. No project-wide convention for building, tagging, publishing, or promoting images.
Target: Every `make build` produces immutable `YYMMDD-HHMM` tagged images. `make publish` pushes to DockerHub and updates `:dev`. `make promote-staging`/`promote-latest` re-points mutable tags. All services — including vexa-bot — follow the same convention. Helm and compose both reference `vexaai/` DockerHub registry. Deploy READMEs document the workflow.
Stop-when: target met OR 5 iterations
Constraint: No CI/CD automation — local tooling and docs only. No fallbacks to old naming.

## DoD (Definition of Done)

### 1. Build produces immutable tags
- [ ] `make build` in `deploy/compose/` generates `IMAGE_TAG=YYMMDD-HHMM`
- [ ] All service images tagged as `vexaai/{service}:{IMAGE_TAG}`
- [ ] Bot image tagged as `vexaai/vexa-bot:{IMAGE_TAG}`
- [ ] Tag saved to `.last-tag` (gitignored)
- [ ] Verify: `docker images | grep YYMMDD` shows all services with same timestamp

### 2. Run uses specific tags
- [ ] `make up` reads `.last-tag` and runs those exact images
- [ ] `docker compose ps` shows containers with the timestamp tag, not `:dev` or `:latest`

### 3. Publish workflow works
- [ ] `make publish` pushes all images to DockerHub with immutable tag
- [ ] `make publish` updates `:dev` pointer via `docker buildx imagetools create`
- [ ] `make promote-staging TAG=X` updates `:staging` on DockerHub
- [ ] `make promote-latest TAG=X` updates `:latest` on DockerHub

### 4. Registry consolidated to DockerHub
- [ ] Helm `values.yaml` uses `vexaai/*` repositories with `:latest` default
- [ ] Helm `values-staging.yaml` uses `vexaai/*` repositories (no `ghcr.io`)
- [ ] Compose `docker-compose.yml` uses `vexaai/*:${IMAGE_TAG:-dev}`
- [ ] Bot profile (`profiles.yaml`) uses `vexaai/vexa-bot:latest` default

### 5. Documentation updated
- [ ] `deploy/README.md` has Image Tagging section with tag hierarchy table
- [ ] `deploy/compose/README.md` documents build/publish/promote workflow
- [ ] `deploy/helm/README.md` explains mutable vs immutable tags and pinning

## Verification Method

Verify by running, not reading code:
1. `cd deploy/compose && make build` — check `docker images` for timestamp-tagged images
2. `make up` — check `docker compose ps` for correct tags
3. `make publish` — check DockerHub for the pushed tag (requires DockerHub auth)
4. Helm: `helm template vexa ./deploy/helm/charts/vexa` — verify image references
