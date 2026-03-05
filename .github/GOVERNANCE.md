# Repository Governance

## Branching Strategy

This project uses a **trunk-based** branching model with `main` as the primary branch.

### Branch Naming

| Prefix        | Purpose                     | Example                          |
| ------------- | --------------------------- | -------------------------------- |
| `feature/`    | New functionality           | `feature/trailing-stop-tool`     |
| `fix/`        | Bug fixes                   | `fix/order-timeout`              |
| `docs/`       | Documentation changes       | `docs/api-reference`             |
| `refactor/`   | Code restructuring          | `refactor/tool-registration`     |
| `test/`       | Test additions/changes      | `test/market-data-edge-cases`    |
| `release/`    | Release preparation         | `release/0.2.0`                  |

### Workflow

1. Create a branch from `main` using the naming convention above
2. Make changes, commit with [Conventional Commits](https://www.conventionalcommits.org/) messages
3. Push the branch and open a pull request
4. Address review feedback
5. Squash-merge into `main` after approval

## Branch Protection Rules (for maintainers)

Apply these settings to the `main` branch via **Settings > Branches > Branch protection rules**:

### Required Settings

- [x] **Require a pull request before merging**
  - Require at least **1 approval**
  - Dismiss stale pull request approvals when new commits are pushed
  - Require review from code owners (once CODEOWNERS is configured)
- [x] **Require status checks to pass before merging**
  - Require the `test` CI job to pass
  - Require branches to be up to date before merging
- [x] **Require conversation resolution before merging**
- [x] **Require signed commits** (recommended)
- [x] **Do not allow bypassing the above settings**

### Additional Recommendations

- [x] **Restrict who can push to matching branches** — only maintainers
- [x] **Do not allow force pushes**
- [x] **Do not allow deletions**

## Releases

- Releases are tagged from `main` using semantic versioning (`v0.1.0`, `v0.2.0`, etc.)
- Each release should update [CHANGELOG.md](../CHANGELOG.md)
- Use GitHub Releases to publish release notes

## Repository Settings Checklist

Before making the repository public, configure these GitHub settings:

### General

- [ ] Set repository description and topics (`mcp`, `metatrader5`, `trading`, `ai`, `claude`)
- [ ] Set repository URL in About section
- [ ] Enable Discussions (for Q&A and community)
- [ ] Disable unused features (Wiki if not needed, Projects if not used)

### Branches

- [ ] Set `main` as default branch
- [ ] Apply branch protection rules listed above

### Security

- [ ] Enable Dependabot alerts
- [ ] Enable Dependabot security updates
- [ ] Enable secret scanning
- [ ] Enable push protection (blocks commits containing secrets)
- [ ] Enable private vulnerability reporting

### Actions

- [ ] Configure CI workflow permissions (read-only for PRs from forks)

### Collaborators

- [ ] Add trusted collaborators with appropriate roles
- [ ] Review and revoke any unnecessary access
