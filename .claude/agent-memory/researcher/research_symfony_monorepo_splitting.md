---
name: Symfony Monorepo Splitting Research
description: How Symfony splits 50+ components from symfony/symfony to individual read-only repos using splitsh-lite, CI workflows, versioning, and cross-component deps
type: reference
---

# Symfony Monorepo Splitting: Complete Research

## Tooling: splitsh-lite (Go binary)

- Written in Go (79.5%) + Shell (20.5%), wraps libgit2
- Replaces `git subtree split` with much faster implementation
- Initial split: "hours+ to < 1 minute"; incremental: "minutes+ to < 10ms"
- Deterministic: same code always produces same commit SHAs
- Caches already-split commits in splitsh.db for speed
- Key flags: --prefix, --path, --origin, --target, --scratch (flush cache)
- Prefix supports `from:to:exclude` syntax

**Symfony uses an enhanced layer on top of splitsh-lite** (not publicly available) that adds tag management, Packagist updates, and versioning logic. The public splitsh-lite is the core engine.

## CI Workflow Pattern (GitHub Actions)

Canonical workflow (from community implementations, Symfony's actual split may be server-side):

```yaml
on:
  push:
    tags: ['v*']
    branches: [main, '*.x']

jobs:
  split:
    runs-on: ubuntu-latest
    strategy:
      fail-fast: false
      matrix:
        package:
          - { local: 'packages/console', remote: 'console' }
          - { local: 'packages/http-kernel', remote: 'http-kernel' }
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0  # CRITICAL: shallow clone breaks splits

      - name: Install splitsh-lite
        run: |
          curl -sL https://github.com/splitsh/lite/releases/download/v1.0.1/lite_linux_amd64.tar.gz | tar xz
          sudo mv splitsh-lite /usr/local/bin/splitsh-lite

      - name: Split and push
        env:
          SPLIT_GH_TOKEN: ${{ secrets.SPLIT_GITHUB_TOKEN }}
        run: |
          SHA=$(splitsh-lite --prefix="${{ matrix.package.local }}")
          REMOTE_URL="https://x-access-token:${SPLIT_GH_TOKEN}@github.com/owner/${{ matrix.package.remote }}.git"
          git remote add split "${REMOTE_URL}" 2>/dev/null || true
          git push split "${SHA}:refs/heads/main" --force
          git push split "${SHA}:refs/tags/${TAG_NAME}" --force
```

43 packages split in ~2 minutes via parallel matrix execution.

## Component READMEs

- Each component has its own README.md inside the monorepo at `src/Symfony/Component/Console/README.md`
- The split copies this file as-is to the mirror repo root
- The README is **identical** in both locations (it IS the same file)
- Symfony's package-tests workflow validates that every package has: .gitignore, CHANGELOG.md, LICENSE, README.md, phpunit.xml.dist

## Mirror Repo Auto-Generated Files

The `sync-packages.php` script generates these files in each mirror:
1. `.gitattributes` — adds `/.git* export-ignore`
2. `.github/PULL_REQUEST_TEMPLATE.md` — redirects contributors to main repo
3. `.github/workflows/close-pull-request.yml` — auto-closes PRs with redirect message

## Cross-Component Dependencies (composer.json)

Each component has its own `composer.json` in the monorepo (e.g., `src/Symfony/Component/Console/composer.json`). This file:
- Specifies dependencies on other Symfony components by package name (e.g., `"symfony/string": "^6.4|^7.0"`)
- Uses version ranges, not `self.version`
- Includes `conflict` declarations for incompatible older versions
- Has `require-dev` for testing dependencies on other components
- Is copied as-is to the mirror repo

The **root** `composer.json` has a `replace` section listing all 54 components with `"self.version"`, so installing `symfony/symfony` satisfies all component requirements.

## Versioning

- All components share the same major.minor version (e.g., 7.2)
- Since 2021: patch tags are **skipped** for packages with no changes since last patch release
- Minor/major releases (.0 versions) always tag ALL packages
- Each component can have independent patch versions (e.g., Console at 7.2.3 while HttpKernel is at 7.2.5)
- Root `composer.json` uses `"replace": { "symfony/console": "self.version" }` etc.

## Key Gotchas

1. **Shallow clone = broken splits** — `fetch-depth: 0` is mandatory
2. **Commit hash mismatch** — Early splitsh-lite trimmed leading empty lines from commit messages, producing different SHAs than `git subtree split`. Fixed by using `git_commit_message_raw()`.
3. **GPG signing breaks hash preservation** — Signature is part of commit hash
4. **Cache file sharing** — splitsh.db can't be shared between parallel workers easily
5. **Apple Silicon segfaults** — Historical issue with libgit2 on ARM Macs
6. **--target flag quirks** — Must use `refs/heads/` prefix for branch targets
7. **Empty tags waste** — Tagging unchanged packages wastes CI/download resources (Symfony's fix: skip patch tags)
8. **Full splitsh vs lite** — Symfony internally uses an enhanced version with tag/Packagist management; the public tool is just the split engine
9. **Mirror repo PRs** — Must auto-close PRs on mirrors to prevent contributor confusion

## Sources
- splitsh-lite: https://github.com/splitsh/lite
- Symfony .github scripts: https://github.com/symfony/symfony/tree/7.2/.github
- Subtree Split as a Service: https://www.subtreesplit.com/
- DEV.to tutorial: https://dev.to/jonesrussell/publishing-a-php-monorepo-to-packagist-with-splitsh-lite-2c3f
- Versioning blog post: https://symfony.com/blog/symfony-packages-are-not-tagged-anymore-when-nothing-changes-between-versions
- Fabien's talk: https://speakerdeck.com/fabpot/a-monorepo-vs-manyrepos
