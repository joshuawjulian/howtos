# How-Tos

Personal reference tutorials. Each tutorial lives in its own subdirectory so it has room for diagrams, helper scripts, and example files.

See [CLAUDE.md](./CLAUDE.md) for writing standards and deep per-tutorial context. That file is also the authoritative reference for any AI agent extending or editing tutorials in this repo.

## Index

### Foundations

| Tutorial | What it covers |
|---|---|
| [ssh-keys](./ssh-keys/README.md) | SSH key generation, naming conventions, `~/.ssh/config` format, ssh-agent persistence, multi-device + multi-account workflows. The deep treatment of keys that the other how-tos reference. |
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

## Conventions for new tutorials

- One folder per tutorial: `howtos/<kebab-case-topic>/`
- Main content lives in `README.md` inside that folder so GitHub/VS Code render it by default
- Drop diagrams, scripts, example configs into the same folder
- Link from the appropriate section above when you add one
- Follow the seven writing standards documented in [CLAUDE.md](./CLAUDE.md): opinionated, alternatives-aware, historically grounded, example-heavy, future-proofed, automation-first, GitHub-renderable
