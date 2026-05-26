# How-Tos

Personal reference tutorials. Each tutorial lives in its own subdirectory so it has room for diagrams, helper scripts, and example files.

## Index

| Tutorial | What it covers |
|---|---|
| [vps-from-zero](./vps-from-zero/README.md) | Provision a fresh Ubuntu VPS: SSH keys, locked-down SSH, firewall, auto-patches, Docker Engine, deploy user, shared network, shared Postgres, backups. |
| [dockerized-deployments](./dockerized-deployments/README.md) | The application side: multi-stage Dockerfile, VS Code Dev Containers, GitHub Actions → GHCR build pipeline, SSH-based CD to the VPS, database migrations, multi-app stacks, Caddy reverse proxy. End-to-end automation from dev container to production. |

The two are meant to be read in order — `vps-from-zero` provisions the box; `dockerized-deployments` ships apps to it.

## Conventions for new tutorials

- One folder per tutorial: `howtos/<kebab-case-topic>/`
- Main content lives in `README.md` inside that folder so GitHub/VS Code render it by default
- Drop diagrams, scripts, example configs into the same folder
- Link from the table above when you add one
- Front-matter at the top of each tutorial: a one-line description, prerequisites, and what you'll have at the end
