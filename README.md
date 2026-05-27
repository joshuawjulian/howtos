# How-Tos

Personal reference tutorials. Each tutorial lives in its own subdirectory so it has room for diagrams, helper scripts, and example files.

See [CLAUDE.md](./CLAUDE.md) for writing standards and deep per-tutorial context. That file is also the authoritative reference for any AI agent extending or editing tutorials in this repo.

## Index

| Tutorial | What it covers |
|---|---|
| [ssh-keys](./ssh-keys/README.md) | SSH key generation, naming conventions, the `~/.ssh/config` file format, ssh-agent persistence, and multi-device / multi-account workflows. The deep treatment that the other how-tos reference for SSH basics. |
| [vps-from-zero](./vps-from-zero/README.md) | Provision a fresh Ubuntu VPS: SSH keys, locked-down SSH, firewall, auto-patches, Docker Engine, deploy user, shared network, shared Postgres, backups. |
| [dockerized-deployments](./dockerized-deployments/README.md) | The application side: multi-stage Dockerfile, VS Code Dev Containers, GitHub Actions → GHCR build pipeline, SSH-based CD to the VPS, database migrations, multi-app stacks, Caddy reverse proxy. End-to-end automation from dev container to production. |

The first two are typically read in order — `ssh-keys` covers the auth foundation; `vps-from-zero` provisions the box; `dockerized-deployments` ships apps to it.

## Conventions for new tutorials

- One folder per tutorial: `howtos/<kebab-case-topic>/`
- Main content lives in `README.md` inside that folder so GitHub/VS Code render it by default
- Drop diagrams, scripts, example configs into the same folder
- Link from the table above when you add one
- Follow the writing standards documented in [CLAUDE.md](./CLAUDE.md) — opinionated, alternatives-aware, historically grounded, example-heavy, future-proofed, automation-first, GitHub-renderable
