# CLAUDE.md — Repository instructions for Claude (and humans)

> This is a personal how-to reference library. Every document in this repo follows a specific style: **opinionated, alternatives-aware, historically grounded, and example-heavy.** This file documents that style, indexes every existing how-to with deep context, and provides a template for adding new ones.
>
> Read this file in full before editing anything in this repo or writing a new how-to.

---

## What this repo is for

A personal collection of "how to do X" tutorials I (Joshua Julian) have written for my own future reference, with enough context that:

- **Six months from now**, when I've forgotten why I made a particular choice, the doc explains it.
- **An AI agent** opening this repo can extend, correct, or update any how-to without breaking the style or principles.
- **Someone else reading it** (collaborator, friend, eventual public release) can follow it without prior context about my preferences.

The repo is not a "list of commands to copy-paste." It's a **decision record + tutorial hybrid** — the kind of doc where you can read the surrounding prose and understand why each command is what it is, what could have been done instead, and what would go wrong if you skip a step.

## Layout

```
howtos/
├── CLAUDE.md                         # this file
├── README.md                         # short index for humans browsing the repo
├── vps-from-zero/
│   └── README.md                     # provisioning a fresh Ubuntu VPS
└── dockerized-deployments/
    └── README.md                     # CI/CD pipeline + dev containers
```

Each how-to lives in its own subdirectory. The main content is always `README.md` inside that directory, because that's what GitHub and VS Code render by default. Additional assets (diagrams, helper scripts, example configs) live in the same directory.

---

## Writing standards

Every how-to in this repo must satisfy **six standards**. These aren't suggestions; they're load-bearing. If a how-to lacks one, it's incomplete.

### 1. Opinionated

The doc takes a stance. It doesn't say "you could use Docker, or Kubernetes, or systemd, or…" — it says "use Docker for these reasons, and here's when to reconsider."

**Why:** Lists of options without recommendations are useless to a future me trying to make a decision quickly. Wishy-washy "it depends" advice is what you get from search-engine-optimized content farms. The whole point of writing my own how-to is that I have a defensible position; the doc should preserve that position so I don't relitigate it every time.

**How to apply:**

- State the recommended path early and clearly.
- Use phrases like "use X" not "X is one option."
- When something is a judgment call, say it's a judgment call and *still pick a side*.
- Defend the recommendation with concrete reasons.

**Example of opinionated writing** (from `dockerized-deployments/README.md`):

> **`workflow_run` trigger explained**
>
> Splitting build from deploy means:
>
> - A failed build never produces a deploy.
> - You can see the build/deploy status separately on the Actions tab.
> - You can re-deploy without re-building (just trigger deploy.yml manually).
> - The deploy can be disabled temporarily without breaking the build.
>
> **Alternative pattern**: a single workflow with two jobs, where deploy `needs: build`. That works too — slightly faster, one less workflow file. Two workflows is slightly cleaner for log reading.

Note the doc picks "two workflows" *and* acknowledges the alternative *and* says why it picked one over the other. That's the formula.

**Anti-pattern (don't do this):**

> You can split build and deploy into two workflows or one workflow with multiple jobs. Both have tradeoffs.

That's evasive. The reader has no idea what to do.

### 2. Alternatives-aware

For every meaningful choice, the doc lists the alternatives — what else could have been done — and explains *when to reconsider*.

**Why:** Conditions change. The "right" choice for a personal VPS with one developer isn't the right choice for a 50-person team with HA requirements. Documenting alternatives keeps the doc useful as conditions evolve, instead of becoming dogma that no longer fits.

**How to apply:**

- Include an "Alternatives considered" section near the end (or per major decision).
- For each alternative, say *when to reconsider it* — what change in conditions would tip the balance.
- Use a comparison table when there are 3+ alternatives.

**Example** (from `vps-from-zero/README.md`):

> | Pattern | Verdict | Why |
> |---|---|---|
> | **Fly.io / Railway / Render** | Use these if you want zero-ops. Free tiers are tight. | Best simplicity; monthly costs scale per-app. |
> | **Kubernetes (k3s, k0s)** | Overkill for a personal VPS. | The complexity tax isn't justified until you have ≥5 nodes or genuine HA needs. |
> | **This guide** | The sweet spot for 1–10 apps on one box. | Add one app at a time without disturbing others; same workflow scales. |

Note the "verdict" column is opinionated AND each row has a reconsider condition implicit in the "why."

### 3. Historically grounded

The doc explains *why this approach exists* — what problem it solves, what didn't work before, what historical accident led to this being the right way to do it.

**Why:** Knowing why something is a certain way is often the difference between maintaining it correctly and breaking it. Cargo-cult solutions ("we do X because everyone does X") don't survive the first time you have to debug them.

**How to apply:**

- When introducing a tool/technique, briefly explain what it replaced or what gap it filled.
- When showing a config that's idiomatic, explain *why* it became idiomatic.
- Reference real incidents or pain points that motivated the design.
- When something looks weird (a flag, an order of operations), explain the history.

**Example** (from `dockerized-deployments/README.md`):

> **`COPY pyproject.toml uv.lock ./` and `RUN uv sync --frozen --no-install-project --no-dev`**
>
> This is the **layer-caching trick** that makes builds fast.
>
> Docker caches each `RUN` step's resulting filesystem. If the inputs haven't changed (file contents, command), Docker reuses the cached layer. By copying *only the dependency manifest* and running install before copying the actual source code, we ensure that:
>
> - Code changes (which happen many times per day) don't invalidate the dep-install layer.
> - Dep changes (which happen occasionally) do invalidate it — correctly.

The "trick" framing is historical — this is a pattern people figured out by suffering through 10-minute builds and then noticing the layer cache was being invalidated too often. Mentioning that history lets the reader appreciate *why* this seemingly arbitrary order matters.

**Another example** (also from dockerized-deployments):

> **Security caveat about the docker group.** Anyone in the docker group can mount the host filesystem into a privileged container and effectively become root. This is a known property of Docker, not a bug.

Calling it "a known property, not a bug" is doing historical/cultural work — it tells the reader that this isn't something that's going to be "fixed," it's by design, and there are mitigations rather than workarounds.

### 4. Example-heavy

Every concept must be paired with **at least one concrete example**. Many concepts get multiple examples — including failure modes and counter-examples ("what NOT to do").

**Why:** Abstract explanations slide off the brain. Concrete examples stick. "Many examples" is better than "the right example" — when you give five examples, the reader builds intuition; with one, they memorize.

**How to apply:**

- Every command shown should have a sample of what good output looks like (or what the failure looks like).
- Every config field should have a value example, not just a description.
- Every decision should have a real-world scenario where the decision matters.
- Show what to do AND show what to NOT do, side by side.

**Example** (from `dockerized-deployments/README.md`):

> ### Why each piece is the way it is
>
> **`image: postgres:16`**
> Pin a specific major version. **`:latest` is dangerous here** — Postgres major versions are not data-file-compatible. If a `docker compose pull` upgrades you from 16 to 17 across a reboot, the new container will fail to start because the data files are in the 16 format.

That's the principle stated + the failure mode shown concretely. Reader doesn't just learn "pin major versions" abstractly; they learn what would actually break and how.

**Another example** (table from migration troubleshooting in dockerized-deployments):

> **Migration partially applied (e.g., ADD COLUMN succeeded but UPDATE failed):**
>
> - Schema is mid-state. Bot still on old image, but schema isn't where Alembic thinks it should be.
> - Either push a corrective migration, or manually fix the DB:
>   ```bash
>   docker exec -it infra-postgres-1 psql -U botuser -d botdb
>   -- apply the operations Alembic didn't finish
>   -- update Alembic's bookkeeping
>   UPDATE alembic_version SET version_num = '<the-revision-id>';
>   ```
>   Take a backup first.

Concrete failure → concrete recovery commands → caveat. Not "you might need to fix it manually"; *here is the SQL you might run.*

### 5. Future-proofed (bleeding edge)

The doc recommends and uses **the latest stable versions of every tool referenced**, and uses the most modern syntax/features available. Older versions appear only in the "Alternatives considered" treatment with explicit reasons to reconsider them (compatibility, organizational constraints, etc.).

**Why:** Personal how-tos that lock you into two-year-old tool versions become net-negative — you read them in 18 months and they're recommending workflows that have been superseded by something faster, simpler, or better-supported. Bleeding edge ages out *faster* than conservative tooling, but it ages out *cleanly*: you can tell from version numbers and feature mentions that an update is overdue. Conservative version pinning ages out *invisibly* — the doc keeps "working" while the world moves past it, and you don't notice until you're three years behind.

Future-proofing also means **automating the things that move**. Pin to specific versions (for reproducibility), but pin to the *latest at time of writing*. Use action versions that auto-update minor revisions (`actions/checkout@v4`, not `actions/checkout@v4.1.7`). Use `:16` for Postgres major-version pinning, not `:16.4.2`. The goal is "still works in a year with minimal upkeep," not "frozen in time."

**How to apply:**

- Pick the **latest stable major version** of every tool referenced. As of writing: Python 3.12+, Postgres 16+, Ubuntu 24.04+, Docker Engine current, Compose v2.22+, GHA action `@v4` / `@v5` (current majors).
- Use **modern syntax** wherever available — modern Python (`match` statements, `|` type unions), modern Compose (`develop.watch.sync`), modern Docker (BuildKit / Buildx features), modern shell (`#!/usr/bin/env bash` not `#!/bin/sh`).
- Use **modern tools** where they've clearly won — `uv` over `pip+venv+pip-tools`, `ruff` over `flake8+isort+black`, `pnpm` over `npm` (or `bun` if that's stabilized by the time you're reading this), `pydantic v2` over `dataclasses` for serialization, etc.
- **Note "as of <month> <year>"** near version specifics so a future reader knows roughly when the doc was last validated.
- When BleedingEdge has a known cost (e.g., a tool's API is still stabilizing), call it out explicitly in the doc and pick the cost honestly.

**Example** — from `dockerized-deployments/README.md`:

- Uses `uv` (rapid adoption since 2024) instead of pip+poetry.
- Uses Python 3.12-slim base image.
- Uses BuildKit via `docker/setup-buildx-action@v3`.
- Uses Compose `develop.watch.sync` (requires Compose v2.22+).
- Uses GHA `actions/checkout@v4`, `docker/build-push-action@v5`, `docker/metadata-action@v5` — latest stable majors.

**Anti-pattern:** A doc that still recommends `virtualenv + pip-tools + requirements.txt` (the 2019 stack) when `uv` does the whole job in one binary that's 100× faster.

**Anti-pattern:** Using `docker-compose` (the legacy Python-based v1 binary) instead of `docker compose` (the Go-based v2 plugin). v1 has been EOL since 2023; v2 is the only thing that gets new features.

**Maintenance discipline:** Once a year, sweep every how-to and bump version numbers / replace tools that have been superseded. Note the bump date in commits.

### 6. Automation-first

The doc treats manual procedures as a **last resort**. Where automation exists — CI/CD pipelines, declarative configs, shell scripts, cron, systemd units — the doc shows the automated path as the canonical one. Manual recipes appear only when:

- Automation is genuinely impossible (one-time provisioning of a fresh box; interactive auth flows; irreversible decisions a human must confirm).
- The reader needs to understand the manual flow in order to debug the automated one (e.g., the `docker compose run --rm migrate` command you'd run by hand to investigate a failed CI migration).

**Why:** Manual steps are where mistakes hide. "Now SSH in and run X" is a great way to forget to run X, or to run it on the wrong server, or to skip it because you remember "doing it last time" (but on a different machine, or a different version, and now your context is wrong). Automation pushes the *opportunity for mistakes* to the **design layer**, where it gets debugged once and then keeps not failing. Manual procedures push it to **every execution**, where it has to be re-debugged forever.

Automation is also how the doc stays useful as the writer gets older / has less time. A how-to that needs you to remember 12 steps is a how-to that won't be used in two years. A how-to that ends with "and now `git push` does the rest" is the kind that pays compounding dividends.

**How to apply:**

- For **deploys**, show the CI/CD pipeline as the only canonical path. Manual SSH-and-restart appears only in the rollback section or in troubleshooting.
- For **repeated procedures**, write a shell script in `scripts/` rather than listing the steps in prose. Reference the script from the doc.
- For **scheduled tasks**, write a cron entry or systemd timer; document that.
- For **secrets / configuration**, use declarative files (`.env`, compose `env_file:`) — not "now export these variables manually."
- When a manual step is *genuinely* required, **explicitly explain why automation doesn't apply** ("this is one-time provisioning of a fresh VPS, so there's nothing to automate it from yet").
- When showing a manual command, **also show what automating that command would look like** ("the same thing in a cron entry: …").

**Example** — from `dockerized-deployments/README.md`:

- The entire end-to-end CI/CD pipeline (build → push → SSH → pull → migrate → restart) replaces what would otherwise be ~8 manual SSH steps per deploy.
- The migrate service is a compose-defined automation invoked by the deploy script — *not* "remember to run `alembic upgrade head` after deploying."
- Image tagging (`:latest` + `:sha-<commit>`) is computed by `docker/metadata-action@v5` rather than the developer writing tag arguments by hand.

**Example** — from `vps-from-zero/README.md`:

- `unattended-upgrades` automates security patching. No "remember to run `apt upgrade` weekly."
- The `pg_dumpall` backup script is invoked from cron, not "remember to run it."
- The deploy user is created with `--disabled-password` so password rotation isn't a thing you need to remember to do.

**Anti-pattern:** A doc whose "deploy" instructions are "SSH in, `cd ~/app`, `git pull`, `pip install -r requirements.txt`, `alembic upgrade head`, `systemctl restart app`, watch logs." Every one of those steps is a future failure. The whole sequence should be a CI workflow with one trigger: `git push`.

**Anti-pattern:** A doc that says "you'll want to set up backups eventually" but doesn't show the script and cron entry that *actually does the backups*. "Eventually" means "never."

**Where manual is correct:**

- The first ~30 minutes of provisioning a brand-new VPS — nothing to automate it *from* yet. (Though even there, prefer a single bootstrap script the user runs once.)
- Decisions that require human judgment (e.g., which Discord token to use, which domain name to attach).
- Irreversible operations where a wrong automated step is worse than a wrong manual one (e.g., DROP TABLE in prod).

---

## What's in this repo

Two how-tos as of writing. Each gets its own deep entry below.

### 1. `vps-from-zero/`

**Path:** [vps-from-zero/README.md](./vps-from-zero/README.md)

**What it covers**

Taking a brand-new Ubuntu VPS from "the provider just emailed you root credentials" to "locked-down server with Docker, a shared Postgres, and a clean directory layout, ready to host containerized apps." The boundary is intentional: this doc handles **infrastructure**, not applications.

**Who it's for**

Me, when I rebuild this stack on a new VPS. Or anyone who:

- Has paid for a $5/month Hetzner / DO / Linode box.
- Is comfortable on a Linux command line but isn't a sysadmin.
- Wants to host their own side projects without leaning on a PaaS.

**Historical context — why this how-to exists**

Every time I've gotten a new VPS, I've spent half an hour re-googling "how do I disable root SSH login" and "what's the safest way to install Docker on Ubuntu." Each time I'd skip something — install Docker via apt (which gets you a Docker that's 6 months old), forget to set up unattended security updates, leave Postgres on `0.0.0.0:5432` because the default tutorial didn't warn against it. The how-to is what I wish I'd had: a single document that gets every important step right and explains why each one matters.

The structure (admin user + separate deploy user + per-app DB users) emerged from years of mixing personal and CI access on the same account and getting nervous about blast radius. Once I split them, "what if my CI key leaks" stopped being an existential question.

**Opinionated stance**

This document believes:

- **Keys not passwords**, full stop, day one. Password auth on the public internet is brute-forced in minutes.
- **Default-deny firewall.** UFW with only OpenSSH allowed. Add 80/443 only when there's a service to expose.
- **Three layers of identity** (admin user, deploy user, DB-user-per-app) is the right granularity for a personal VPS. More layers is overkill; fewer is risk.
- **Pin Postgres major versions.** `:latest` is a footgun; Postgres major upgrades require explicit dump/restore.
- **Patch automatically.** `unattended-upgrades` on day one. Unpatched OpenSSH is the #1 reason personal VPSes get owned.
- **Use the official Docker install script**, not `apt install docker.io`. The Ubuntu repo lags by months.

**Alternatives considered (with reconsider conditions)**

The doc has a full "Alternatives considered" section. Highlights:

- **Fly.io / Railway / Render** — recommended if you only have 1-2 apps and don't want to learn ops. Reconsider this VPS approach if monthly hosting costs are negligible relative to your time.
- **Kubernetes (k3s on a single node)** — actively rejected. Complexity tax not justified for one box. Reconsider when you have ≥3 nodes or true HA needs.
- **Coolify / Dokploy / CapRover** — actively rejected for *this* doc, because they hide the compose layer and break the "you can debug it" property. Reconsider when you have 5+ apps and the GUI ergonomics outweigh the abstraction tax.

**Concrete examples in the doc**

- A complete sshd_config lockdown (what to set, why each setting matters, what the failure mode is if you skip it).
- A real `pg_dumpall` backup script with retention.
- The `\du+ <user>` and `\l+ <db>` audit commands with example output.
- A "before closing your session, open a new terminal and confirm SSH still works" safety check — born from getting locked out of a VPS once.

**What's NOT in this doc**

- How to deploy apps. That's the dockerized-deployments doc.
- How to set up monitoring/alerting. Mentioned as "next steps," not covered.
- HA / multi-VPS setups. Explicitly out of scope.
- Anything Windows-server related.

---

### 2. `dockerized-deployments/`

**Path:** [dockerized-deployments/README.md](./dockerized-deployments/README.md)

**What it covers**

The end-to-end automation that takes code from "I'm typing in a VS Code Dev Container" to "running on the VPS, automatically, on every push to main." Covers:

- Multi-stage Dockerfile (one image, dev + prod stages)
- VS Code Dev Containers as the local dev environment
- GitHub Actions building and pushing to GHCR
- SSH-based CD to the VPS
- Database migrations integrated into the deploy pipeline
- Multi-app architecture (adding the Nth app at zero marginal cost)
- Caddy reverse proxy for web apps
- Rollbacks

**Who it's for**

Me, every time I start a new side project. Or anyone who:

- Has finished `vps-from-zero` (or has an equivalent VPS setup).
- Wants the full CI/CD pipeline, not just "Dockerfile basics."
- Is willing to spend 30 minutes on the first project's plumbing to get a workflow that scales to N projects.

**Historical context — why this how-to exists**

For years I'd deploy side projects by SSHing into a VPS, running `git pull && systemctl restart`, and crossing my fingers. Three problems with that:

1. **Dev/prod drift.** "Works on my Mac, breaks on the Linux VPS." Python version mismatch, missing apt package, libssl version skew — each one a half-hour debugging session.
2. **Migration nightmares.** "Did I run the migration before restarting? Should I have? Is the schema where I think it is?" — answered by SSHing in, running psql, hoping.
3. **Per-app drudgery.** Setting up systemd units, nginx config, venv path quirks — each new project was a fresh adventure in remembering how to set up the boring parts.

Dockerization fixed (1). CI/CD fixed (3). The migration-as-a-compose-service-with-profiles pattern fixed (2). The doc captures all three insights and the wiring that ties them together.

The dev container piece came later, after the n-th time I had to install the same `apt install postgresql-client libpq-dev` on a new laptop. Now my "laptop" is a Linux container that lives in the repo.

**Opinionated stance**

This document believes:

- **One image, many environments.** Same artifact in dev container, in CI tests, on the VPS. Configuration via env vars; never bake env-specific stuff into the image.
- **Stacks, not monoliths.** One docker-compose per app. Shared services in their own stack. Restarting one app must not touch the others.
- **CI builds, CD deploys.** Two separate workflows. The boundary is the image in GHCR. Each phase is independently debuggable.
- **Multi-stage Dockerfile** is mandatory. Single-stage means dev tools ship to prod, which means bloat and attack surface.
- **Pin runtime versions** (Python, Node, Postgres clients) in the Dockerfile. Don't trust "latest stable" to mean the same thing in 6 months.
- **Migrations as a separate compose service with `profiles:`.** Run explicitly via `compose run --rm migrate` in the deploy pipeline, before the app restart. Never bake migration into the app's startup.
- **Tag every CI build with both `:latest` and `:sha-<commit>`.** SHA tags are immutable; they're your rollback handle.
- **Caddy for HTTPS.** Three lines of config; Let's Encrypt auto-renewal; done.

**Alternatives considered (with reconsider conditions)**

Per major decision:

- **Registry: GHCR vs Docker Hub vs self-hosted.** Pick GHCR. Reconsider Docker Hub if you specifically want anonymous-pullable public images with a known reputation. Reconsider self-hosted only if you're operating at scale where the bandwidth/storage matters.
- **CI: GitHub Actions vs GitLab CI vs Jenkins/Drone.** Pick GHA. Reconsider if you're on GitLab anyway, or if you have organizational compliance requirements that need self-hosted.
- **Dev env: Dev Containers vs local venv vs Nix.** Pick Dev Containers for the dev/prod identity property. Reconsider local venv for ultra-fast iteration on a single language. Reconsider Nix if you want reproducibility without containers.
- **Migrations: Alembic vs Yoyo vs Flyway vs raw SQL.** Pick Alembic for Python/SQLAlchemy. Reconsider Yoyo if you're not using SQLAlchemy. Reconsider Flyway only if you're in a Java shop.
- **Reverse proxy: Caddy vs Traefik vs nginx.** Pick Caddy for the config simplicity. Reconsider Traefik if you want Docker labels driving config. Reconsider nginx if you have an existing nginx config investment.

**Concrete examples in the doc**

This is where the example-heavy standard is most heavily applied:

- The full Dockerfile, line-by-line annotated with what each directive does and why.
- The full devcontainer.json, field-by-field explanation including what would happen without each field.
- The full build.yml workflow, block-by-block.
- The complete deploy.yml workflow, including the `workflow_run` trigger semantics.
- A full end-to-end walkthrough of a single feature (new `/leaderboard` command + scores table) from "branch off main" through "verify in production," with timing.
- Database migration setup with Alembic — wiring `env.py` to read `DATABASE_URL` from env, the migrate service in compose, the deploy pipeline integration, and three concrete failure modes (clean failure, partial application, schema-rolled-back-but-image-not).
- The expand/contract migration pattern with concrete SQL operations across multiple deploys.
- A troubleshooting table mapping symptom → layer to debug.
- A rollback workflow with a real example command.

**What's NOT in this doc**

- How to provision the VPS in the first place. That's vps-from-zero.
- How to write good application code, write tests, etc. — language-specific.
- Multi-VPS / load-balancer / blue-green deploys. Out of scope for the "personal box" target.
- Observability stack (Prometheus, Grafana, Loki). Mentioned only as future work.

---

## When working in this repo (instructions for Claude)

### Adding a new how-to

1. Create a new subdirectory: `<kebab-case-topic>/`.
2. Write `<kebab-case-topic>/README.md` following the template below.
3. Add an entry to this CLAUDE.md under "What's in this repo" with the full deep-entry treatment (what, who, history, opinionated stance, alternatives, examples, what's NOT in it).
4. Add a row to the top-level `README.md` index table.
5. Commit + push.

### Editing an existing how-to

Hard rules:

- **Never strip the "why" prose.** If you find yourself wanting to make a section "tighter" by cutting explanation paragraphs, stop. The explanations are the whole point. Tighten by sharpening, not by deleting.
- **Never sanitize opinions.** If a how-to says "use X, not Y" — don't soften it to "both X and Y are valid choices" unless the underlying advice has actually changed.
- **Preserve historical context.** Don't remove the "this is why this approach exists" paragraphs even when refactoring sections.
- **Preserve concrete examples.** If you replace an example, replace it with another concrete example — not with an abstraction.
- **Don't add cause attribution / diagnostic prose where it doesn't already exist.** The how-tos describe what the user does, what the user observes, and the *mechanics under the hood*. They don't moralize about what could have caused historical bugs unless the historical context is load-bearing.

When adding content:

- Match the existing tone (direct, second-person, no hedging unless genuinely uncertain).
- If you introduce a new tool/command/config, add a "why this and not X" paragraph.
- If you remove something, add a note about *why* you removed it in the commit message.

### Things to verify before committing

- [ ] Every command in the doc has a one-paragraph explanation of what it does and why this command vs the alternative.
- [ ] Every config field shown has either inline annotation or a "what each field does" section.
- [ ] At least one "Alternatives considered" treatment in the doc.
- [ ] At least one "What this doc is NOT for" section to bound scope.
- [ ] At least one concrete failure mode with concrete recovery steps.
- [ ] The opinionated recommendation is stated early and stated clearly.
- [ ] **Latest stable versions of every tool referenced** (or explicit "as of <date>" annotation if a future bump is expected). No legacy tooling unless explicitly justified.
- [ ] **Manual procedures are last resort.** Anywhere a manual step appears, either (a) automation is genuinely impossible and the doc says why, or (b) the same step is also shown as an automation.

### Things to NEVER do

- **Don't add disclaimers.** "Your mileage may vary" / "this is just one approach" weakens the doc. Either you stand by the advice or you don't.
- **Don't link out to external tutorials in lieu of explaining.** Linking is fine for *reference* (specs, official docs); it's not a substitute for in-document explanation.
- **Don't write generic "tips and tricks" sections.** Every tip should have a concrete reason and a concrete example. Otherwise it's filler.
- **Don't create planning, decision, or analysis docs as separate files.** That kind of meta-content belongs in commit messages or in this CLAUDE.md, not as a standalone doc next to the actual how-to.
- **Don't bloat the doc to seem thorough.** If a topic is genuinely a 200-line doc, that's fine. If it's a 200-line doc that should be 50, that's bad. The standards are about *depth in the right places*, not *length*.
- **Don't recommend legacy tooling.** If `uv` exists, don't recommend `pip+venv+pip-tools`. If `docker compose` (v2) is the current plugin, don't reference `docker-compose` (v1, EOL since 2023). If GHA `actions/checkout@v4` is the current major, don't pin to `@v3`. Bleeding edge is the default; deviations need justification.
- **Don't document manual workflows as the canonical path** when an automated one exists. Manual instructions belong in rollback / debug / one-time-bootstrap sections only.

---

## Template for new how-tos

Copy this skeleton when starting a new how-to. Fill in every section; if a section genuinely doesn't apply, delete it (don't leave it blank).

```markdown
# <Topic Title>: <One-line outcome>

> One-paragraph overview. What this doc covers, what you'll have at the end,
> what its boundaries are (link to related how-tos that handle adjacent
> concerns).

## What you'll have at the end

Bulleted list of concrete outcomes. The reader should know exactly what
state their system will be in when they finish.

## Prerequisites

- Bulleted list of what the reader needs before starting.
- Include skill prerequisites if non-obvious.
- Include time estimate.

---

## Table of contents

Numbered list with anchor links.

---

## 1. The principles

The 3-7 ideas the rest of the doc rests on. Each one stated as a sentence
with a brief explanation. This is where the opinionated stance lives.

### Why this architecture vs. alternatives

A comparison table of major alternatives with "verdict" and "why" columns.

---

## 2. <First topic>

Lead with the "why" of this topic — why are we doing this at all, what
problem does it solve, what historical pattern motivated it.

Then the "what" — the actual command/config/code.

Then deep walkthrough — line by line for code/configs, step by step for
procedures. Every command/line gets a brief explanation.

Include at least one concrete example.

Include at least one "what could go wrong" callout when relevant.

---

## <N-1>. End-to-end walkthrough

A scenario that ties together all the pieces. Walk through ONE realistic
journey — "Alice wants to do X" — using every concept introduced.

Include timing where relevant.

---

## <N>. Troubleshooting

| Symptom | Layer to check |
|---|---|
| ... | ... |

Then specific common errors with their cause and fix.

---

## <N+1>. Alternatives considered

For each major decision, what else was considered and when to reconsider.

---

## <N+2>. Quick reference

Cheat sheet of the most common commands, organized by task.
```

---

## Style examples to reference

When in doubt, model new prose on these specific examples from existing docs.

### Example A: A great "why" paragraph

From `dockerized-deployments/README.md` (`workflow_run` trigger discussion):

> **Why two separate workflows?** Splitting build from deploy means:
>
> - A failed build never produces a deploy.
> - You can see the build/deploy status separately on the Actions tab.
> - You can re-deploy without re-building (just trigger deploy.yml manually).
> - The deploy can be disabled temporarily without breaking the build.

Why this is good: states the question, answers with concrete bulleted reasons. Each reason is operational and falsifiable (you could check whether it's true).

### Example B: A great "alternatives" treatment

From `vps-from-zero/README.md`:

> **Coolify, Dokploy, CapRover**
> - *Why not for this guide:* Hides the docker/compose layer we explicitly want you to understand. When something breaks at the compose layer, you have to break through the abstraction to debug.
> - *When to reconsider:* You've internalized the docker-compose flow, you're running 5+ apps, and the GUI ergonomics are worth the trade.

Why this is good: explicit "not this, because X" + explicit "reconsider when Y." The reader knows both the current verdict and the conditions that would change it.

### Example C: A great historical/cultural callout

From `dockerized-deployments/README.md` (about Postgres major version pinning):

> **`image: postgres:16`**
> Pin a specific major version. **`:latest` is dangerous here** — Postgres major versions are not data-file-compatible. If a `docker compose pull` upgrades you from 16 to 17 across a reboot, the new container will fail to start because the data files are in the 16 format. With the major version pinned, you upgrade on your schedule (with a dump-and-restore).

Why this is good: states the rule + explains the *underlying reason* (data-file incompatibility) + describes the *failure mode* (container won't start) + gives the *correct path forward* (dump and restore on your schedule). Four pieces of information in one short paragraph.

### Example D: A great "concrete example of failure recovery"

From `dockerized-deployments/README.md` (migration troubleshooting):

> **Migration partially applied (e.g., ADD COLUMN succeeded but UPDATE failed):**
>
> - Schema is mid-state. Bot still on old image, but schema isn't where Alembic thinks it should be.
> - Either push a corrective migration, or manually fix the DB:
>   ```bash
>   docker exec -it infra-postgres-1 psql -U botuser -d botdb
>   -- apply the operations Alembic didn't finish
>   -- update Alembic's bookkeeping
>   UPDATE alembic_version SET version_num = '<the-revision-id>';
>   ```
>   Take a backup first.

Why this is good: specific scenario, specific actions, specific commands, specific caveat. The reader can execute this from "what they read" without further digging.

---

## Future how-tos planned (not yet written)

A loose list of topics that fit this repo's pattern. Add to this list when you think of one, remove when written.

- **Observability stack on a personal VPS.** Loki + Grafana + Promtail for log aggregation; uptime monitoring; alerting to Discord/email.
- **Backups + offsite storage.** Picking up where `vps-from-zero` left off — rclone to Backblaze B2, restore-testing.
- **Secrets management.** When per-app `.env` files stop scaling: Vault? SOPS? doppler?
- **From WSL to a real Linux laptop.** Migration guide for when you decide to ditch Windows.
- **Personal CI runner.** When GitHub Actions free tier isn't enough — self-hosted runner on the VPS.
- **Multi-region (or HA) on a budget.** Two cheap VPSes + a load balancer. When does this make sense and when doesn't it?

Don't preemptively write these. Wait until I actually have a reason to do the thing — then writing the how-to is part of doing it.

---

## A note on tone

This whole repo is written in a particular voice: direct, second-person, mildly opinionated, occasionally dry. It's a voice I (the author) talk in. If you're an AI editing these docs, match that voice. If you're a human contributor, feel free to adopt your own voice — but keep the four standards intact.

Phrases that fit the voice:

- "Pin a specific major version. **`:latest` is dangerous here.**"
- "Don't make a habit of this."
- "That's the formula."
- "Wild and powerful; use sparingly."
- "Cargo-cult solutions don't survive the first time you have to debug them."
- "If you find yourself wanting to make a section 'tighter' by cutting explanation paragraphs, stop."

Phrases that DON'T fit (avoid these):

- "It's important to note that…"
- "There are many valid approaches here, and…"
- "Your mileage may vary."
- "Best practices suggest that…"
- "This is just one of many possible ways…"

The first set is direct and committed. The second set is hedged and corporate. We write in the first.
