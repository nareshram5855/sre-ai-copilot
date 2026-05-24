# Branch Strategy

| Branch | Purpose | CI | Merge target |
|--------|---------|----|--------------|
| `main` | Production-ready releases | Full CI on push | — | CD on push → GHCR `:latest` |
| `develop` | Integration branch for features | Full CI on push + PRs to `main` | `main` |
| `staging` | Pre-release validation | Full CI on push | `main` | CD on push → GHCR `:staging` |

## Workflow

1. Create feature branches from `develop`: `git checkout -b feature/my-change develop`
2. Open a PR into `develop` — CI runs automatically
3. After review, merge to `develop`
4. Promote to `staging` for soak testing, then open PR `staging` → `main`

## Recommended branch protection (GitHub Settings → Branches)

**`main`**
- Require pull request before merging
- Require status checks: `Backend (Python 3.11)`, `Frontend (Node 20)`, `Docker image`
- Require branches to be up to date

**`develop`**
- Require status checks on PRs from feature branches
