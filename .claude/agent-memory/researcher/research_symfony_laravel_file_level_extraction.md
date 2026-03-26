---
name: Symfony/Laravel File-Level Extraction Analysis
description: Exact file-by-file comparison of what lives in monorepo component dirs vs standalone split repos — Symfony HttpKernel and Laravel Illuminate/Database verified March 2026
type: reference
---

# Symfony & Laravel: Monorepo vs Standalone Repo File-Level Analysis

## Key Finding: Files Are IDENTICAL

Both Symfony and Laravel maintain ALL standalone-repo files INSIDE the monorepo component directory. The split is a pure directory extraction — no files are added, removed, or transformed during the split process.

## Symfony HttpKernel — Verified File Comparison

### Files in `symfony/symfony/src/Symfony/Component/HttpKernel/` (monorepo):
```
.gitattributes          .gitignore              .github/
CHANGELOG.md            LICENSE                 README.md
composer.json           phpunit.xml.dist
+ all .php source files + Tests/ directory
```

### Files in `symfony/http-kernel` (standalone split repo):
```
.gitattributes          .gitignore              .github/
CHANGELOG.md            LICENSE                 README.md
composer.json           phpunit.xml.dist
+ all .php source files + Tests/ directory
```

**Result: IDENTICAL.** Zero files exist in the standalone repo that don't exist in the monorepo component directory.

### What Each File Contains

| File | Purpose | Notes |
|------|---------|-------|
| `composer.json` | Package metadata, deps, autoload | Lives in monorepo. References other Symfony packages by name+version range, NOT path. |
| `LICENSE` | MIT license, "Copyright (c) Fabien Potencier" | Lives in monorepo, copied as-is during split |
| `README.md` | Brief component description + links to symfony.com docs | Lives in monorepo. Points contributors to main repo. |
| `CHANGELOG.md` | Version-by-version changes | Lives in monorepo. Maintained by humans. |
| `.gitattributes` | `export-ignore` for /Tests, phpunit.xml.dist, .git* | Lives in monorepo. Controls `composer install --prefer-dist` behavior. |
| `.gitignore` | `vendor/`, `composer.lock`, phpunit.xml, test cache dirs | Lives in monorepo. For standalone development. |
| `phpunit.xml.dist` | PHPUnit config for running component tests in isolation | Lives in monorepo. Bootstrap: `vendor/autoload.php`. |
| `.github/PULL_REQUEST_TEMPLATE.md` | Redirects PRs to main symfony/symfony repo | Lives in monorepo. Says "this is a read-only subtree split". |
| `.github/workflows/close-pull-request.yml` | Auto-closes PRs with redirect message | Lives in monorepo. Uses `superbrothers/close-pull-request@v3`. |

### `.gitattributes` content (in monorepo):
```
/Tests export-ignore
/phpunit.xml.dist export-ignore
/.git* export-ignore
```

### `.github/workflows/close-pull-request.yml` content (in monorepo):
```yaml
name: Close Pull Request
on:
  pull_request_target:
    types: [opened]
permissions:
  pull-requests: write
jobs:
  close:
    runs-on: ubuntu-latest
    steps:
      - uses: superbrothers/close-pull-request@v3
        with:
          comment: |
            Thanks for the PR! This repo is a read-only subtree split.
            Please submit PRs to https://github.com/symfony/symfony
```

---

## Laravel Illuminate/Database — Verified File Comparison

### Files in `laravel/framework/src/Illuminate/Database/` (monorepo):
```
.gitattributes          .github/workflows/
LICENSE.md              README.md
composer.json
+ all .php source files
```

### Files in `illuminate/database` (standalone split repo):
```
.gitattributes          .github/workflows/
LICENSE.md              README.md
composer.json
+ all .php source files
```

**Result: IDENTICAL.** Zero files added or removed during split.

### Key Differences from Symfony

| Aspect | Symfony | Laravel |
|--------|---------|---------|
| License file | `LICENSE` (no extension) | `LICENSE.md` |
| Has `.gitignore` | Yes | No |
| Has `CHANGELOG.md` | Yes | No |
| Has `phpunit.xml.dist` | Yes | No |
| Has `Tests/` directory | Yes (in monorepo component) | No (tests are separate) |
| `.gitattributes` content | Excludes Tests, phpunit, .git* | Excludes .github, .gitattributes only |
| Component README depth | Brief (3 paragraphs) | Detailed (standalone usage examples) |

### Laravel `.gitattributes` content (in monorepo):
```
/.github export-ignore
.gitattributes export-ignore
```

### Laravel close-pull-request.yml content (in monorepo):
```yaml
name: Close Pull Request
on:
  pull_request_target:
    types: [opened]
jobs:
  run:
    runs-on: ubuntu-24.04
    steps:
      - uses: superbrothers/close-pull-request@v3
        with:
          comment: "Thank you for your pull request. However, you have submitted
            this PR on the Illuminate organization which is a read-only sub split
            of laravel/framework. Please submit your PR on
            https://github.com/laravel/framework"
```

---

## Split Infrastructure Comparison

### Symfony
- Uses an **enhanced internal version of splitsh-lite** (not publicly available)
- Adds tag management, Packagist updates on top of the open-source splitsh-lite core
- Split is server-side (not GitHub Actions)
- Since 2021: skips patch tags for unchanged packages

### Laravel
- Uses **splitsh-lite** via `bin/split.sh` and `bin/release.sh`
- Runs on a **dedicated server** (104.248.56.26) via SSH from GitHub Actions
- `.github/workflows/releases.yml` triggers SSH to the splitter server
- The server keeps splitsh.db cache warm for performance
- All 33 illuminate packages split and tagged simultaneously

---

## The Pattern: Everything Lives in the Monorepo

Neither Symfony nor Laravel adds ANY files during the split. The component directory in the monorepo IS the standalone repo. splitsh-lite simply extracts that directory's git history into a separate repo.

### Files that MUST be in monorepo component directory:
1. **Package manifest** — `composer.json` / `pyproject.toml` / `package.json`
2. **LICENSE** — Required for standalone distribution
3. **README.md** — Describes standalone usage, links back to main repo
4. **`.gitattributes`** — `export-ignore` for dev files (tests, CI config)
5. **`.github/workflows/close-pull-request.yml`** — Auto-close PRs on read-only mirror
6. **`.github/PULL_REQUEST_TEMPLATE.md`** — Redirect message (Symfony uses this; Laravel relies on the workflow alone)

### Files that are MONOREPO-ONLY (not in component dirs):
1. Root `composer.json` with `replace` section
2. `bin/split.sh`, `bin/release.sh` — split scripts
3. `.github/workflows/releases.yml` — orchestration workflow
4. Root `.gitattributes` with global export-ignore rules
5. Root CI workflows (test matrix, linting, etc.)
6. `CONTRIBUTING.md`, `CODE_OF_CONDUCT.md`, `SECURITY.md` — at monorepo root only

### Files that are STANDALONE-ONLY:
**None.** Both Symfony and Laravel have zero standalone-only files. The split is purely extractive.

## Sources
- Symfony monorepo HttpKernel: https://github.com/symfony/symfony/tree/7.2/src/Symfony/Component/HttpKernel
- Symfony standalone HttpKernel: https://github.com/symfony/http-kernel
- Laravel monorepo Database: https://github.com/laravel/framework/tree/11.x/src/Illuminate/Database
- Laravel standalone Database: https://github.com/illuminate/database
- Laravel split discussion: https://github.com/laravel/framework/discussions/51059
- Symfony tagging blog: https://symfony.com/blog/symfony-packages-are-not-tagged-anymore-when-nothing-changes-between-versions
- subtreesplit.com: https://www.subtreesplit.com/
