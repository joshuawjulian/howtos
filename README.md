# How-Tos

Personal reference tutorials. Each tutorial lives in its own subdirectory so it has room for diagrams, helper scripts, and example files.

See [CLAUDE.md](./CLAUDE.md) for writing standards and deep per-tutorial context. That file is also the authoritative reference for any AI agent extending or editing tutorials in this repo.

## Index

### Foundations

| Tutorial | What it covers |
|---|---|
| [ssh-keys](./ssh-keys/README.md) | SSH key generation, naming conventions, `~/.ssh/config` format, ssh-agent persistence, multi-device + multi-account workflows. The deep treatment that the other how-tos reference. |
| [git-for-solo-devs](./git-for-solo-devs/README.md) | Git workflow for working alone (short branches, aggressive history-rewriting, `--force-with-lease`, `reflog` as safety net). Recovery procedures, multi-machine workflows, a curated `~/.gitconfig`. |
| [claude-code-workflow](./claude-code-workflow/README.md) | Practical patterns for Claude Code as a solo dev. Memory system, plan mode, sub-agents, custom slash commands, hooks, prompting patterns. |

### Server-side stack

| Tutorial | What it covers |
|---|---|
| [vps-from-zero](./vps-from-zero/README.md) | Provision a fresh Ubuntu VPS: SSH keys, locked-down SSH, firewall, auto-patches, Docker Engine, deploy user, shared network, shared Postgres, backups. |
| [domain-caddy-https](./domain-caddy-https/README.md) | Buying a domain, DNS records, Caddy reverse proxy, Let's Encrypt mechanics, Cloudflare proxy decision, wildcard certs, subdomain strategy, Cloudflare Email Routing. |
| [tailscale-for-personal-use](./tailscale-for-personal-use/README.md) | Private mesh networking with Tailscale: MagicDNS, Tailscale SSH (and closing public port 22), internal services on the tailnet, exit nodes, subnet routes, Funnel. |
| [backups-and-restore](./backups-and-restore/README.md) | Boring, tested, offsite backups: `pg_dumpall` + cron + rclone + B2 + `age` encryption. Disaster recovery runbook. Monthly restore drill. |

### Application stack

| Tutorial | What it covers |
|---|---|
| [dockerized-deployments](./dockerized-deployments/README.md) | End-to-end automation: multi-stage Dockerfile, VS Code Dev Containers, GitHub Actions → GHCR build pipeline, SSH-based CD to the VPS, database migrations, multi-app stacks, Caddy reverse proxy. |
| [sveltekit-bun-deployment](./sveltekit-bun-deployment/README.md) | The TypeScript-side companion: SvelteKit + Bun + `adapter-node`, Drizzle + postgres.js for DB, Better Auth for sessions, the same Dockerized pipeline tailored for Bun. |
| [postgres-deep-dive](./postgres-deep-dive/README.md) | The long-form Postgres reference: schema design, indexes (every type), JSON/JSONB, full-text search, `EXPLAIN`, transactions & locks, triggers, performance, extensions (pgvector, etc.), anti-patterns, dense cheat sheet for print. |

### Data / ML stack

| Tutorial | What it covers |
|---|---|
| [scientific-python-2026](./scientific-python-2026/README.md) | The modern Python data stack: `uv` as universal tool, Polars > Pandas, Marimo > Jupyter, Altair/Matplotlib/Plotly/Seaborn split, scikit-learn for classical ML, PyTorch for DL, Dev Container template, reproducibility discipline. |
| [gpu-passthrough-for-wsl](./gpu-passthrough-for-wsl/README.md) | CUDA workloads in WSL2 + Dev Containers: NVIDIA driver setup, skipping the CUDA toolkit, PyTorch/JAX install with CUDA wheels, Docker GPU passthrough, verification, diagnostics. |

### Personal docs

| Tutorial | What it covers |
|---|---|
| [resume-as-code](./resume-as-code/README.md) | Resume in markdown → pandoc + LaTeX (AltaCV) → professionally-typeset PDF. Multi-variant support, ATS-safe variant, docx output, Dev Container for reproducibility, git workflow for managing application history. |

### Suggested reading order

For someone bootstrapping the whole stack from scratch:

1. `ssh-keys` — auth foundation
2. `git-for-solo-devs` — version-control hygiene (not stack-specific but baseline)
3. `claude-code-workflow` — productivity tool (optional but high-leverage)
4. `vps-from-zero` — provision the server
5. `tailscale-for-personal-use` — close public SSH, add private network
6. `domain-caddy-https` — get HTTPS + a real domain
7. `backups-and-restore` — protect what's running
8. `dockerized-deployments` — ship a Python app end-to-end
9. `sveltekit-bun-deployment` — ship a TypeScript app end-to-end
10. `postgres-deep-dive` — once you actually need to use the database well
11. `scientific-python-2026` — for the data-science track
12. `gpu-passthrough-for-wsl` — when ML compute matters
13. `resume-as-code` — orthogonal, but useful

## Printer-friendly PDFs

A printable PDF of every how-to lives in [`pdfs/`](./pdfs). Built from the markdown source via `uv run --with markdown --with weasyprint --with pygments python scripts/build-pdfs.py`. Optimized for printing on paper (B&W toner-friendly, serif body, sensible page breaks); Mermaid diagrams are replaced with a pointer to the online version.

## Conventions for new tutorials

- One folder per tutorial: `howtos/<kebab-case-topic>/`
- Main content lives in `README.md` inside that folder so GitHub/VS Code render it by default
- Drop diagrams, scripts, example configs into the same folder
- Link from the appropriate section above when you add one
- Follow the seven writing standards documented in [CLAUDE.md](./CLAUDE.md): opinionated, alternatives-aware, historically grounded, example-heavy, future-proofed, automation-first, GitHub-renderable
