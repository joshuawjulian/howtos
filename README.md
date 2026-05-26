# How-Tos

Personal reference tutorials. Each tutorial lives in its own subdirectory so it has room for diagrams, helper scripts, and example files.

## Index

| Tutorial | What it covers |
|---|---|
| [vps-deployment-pipeline](./vps-deployment-pipeline/README.md) | Full end-to-end: fresh Ubuntu VPS → SSH keys → Docker → GHCR → GitHub Actions CI/CD → multiple apps → shared Postgres → local development with VS Code Dev Containers |

## Conventions for new tutorials

- One folder per tutorial: `howtos/<kebab-case-topic>/`
- Main content lives in `README.md` inside that folder so GitHub/VS Code render it by default
- Drop diagrams, scripts, example configs into the same folder
- Link from the table above when you add one
- Front-matter at the top of each tutorial: a one-line description, prerequisites, and what you'll have at the end
