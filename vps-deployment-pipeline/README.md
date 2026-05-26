# VPS Deployment Pipeline: From Fresh Box to Production

> Complete end-to-end guide for running containerized apps on a personal Ubuntu VPS, with local development using VS Code Dev Containers and automated deploys via GitHub Actions. Designed for one developer hosting multiple side projects on a single VPS.

**What you'll have at the end:**
- A locked-down Ubuntu VPS with Docker, a shared Postgres, and a clean directory structure for N apps.
- A single SSH key that works in WSL, Windows, and dev containers.
- Local development that runs in the same container as production (no "works on my machine").
- `git push origin main` → live in ~90 seconds.
- A repeatable pattern for adding a 2nd, 3rd, Nth app at zero marginal cost.
- A migration workflow you can trust at 11pm.

**Prerequisites:**
- A Ubuntu 24.04 VPS (Hetzner, DigitalOcean, Linode, Vultr — anything with root SSH access)
- A domain name (optional; only needed once you serve HTTP)
- A GitHub account
- Windows 11 + WSL2 (this guide is written for that environment; substitute equivalents for macOS/Linux as needed)
- VS Code with the **Remote - WSL** and **Dev Containers** extensions installed
- Docker Desktop installed on Windows with WSL2 integration enabled, OR `docker.io` installed directly in your WSL distro

---

## Table of Contents

1. [The big picture](#1-the-big-picture)
2. [SSH key strategy: one key, every environment](#2-ssh-key-strategy-one-key-every-environment)
3. [Setting up a fresh Ubuntu VPS](#3-setting-up-a-fresh-ubuntu-vps)
4. [Managing OS and database users](#4-managing-os-and-database-users)
5. [The shared infrastructure stack on the VPS](#5-the-shared-infrastructure-stack-on-the-vps)
6. [Structuring a containerized app repo](#6-structuring-a-containerized-app-repo)
7. [Local development with VS Code Dev Containers](#7-local-development-with-vs-code-dev-containers)
8. [Day-to-day development cycles](#8-day-to-day-development-cycles)
9. [Building images with GitHub Actions → GHCR](#9-building-images-with-github-actions--ghcr)
10. [Deploying to the VPS (continuous delivery)](#10-deploying-to-the-vps-continuous-delivery)
11. [Adding a second (or fifth) app](#11-adding-a-second-or-fifth-app)
12. [Reverse proxy with Caddy (HTTPS for web apps)](#12-reverse-proxy-with-caddy-https-for-web-apps)
13. [Database migrations without tears](#13-database-migrations-without-tears)
14. [Backups, monitoring, and rollbacks](#14-backups-monitoring-and-rollbacks)
15. [Troubleshooting](#15-troubleshooting)
16. [Alternatives considered](#16-alternatives-considered)
17. [Quick reference (cheat sheet)](#17-quick-reference-cheat-sheet)

---

## 1. The big picture

Before any commands, internalize the architecture. Everything in this guide is in service of this shape:

```
┌────────────────┐    git push origin main     ┌────────────────┐
│  Your laptop   │ ──────────────────────────► │     GitHub     │
│   (WSL2)       │                              │   (your repo)  │
└────────────────┘                              └───────┬────────┘
        │                                               │
        │ Dev Container                                 │ GitHub Actions
        │ (same Dockerfile                              │ builds image
        │  as production)                               ▼
        │                                       ┌────────────────┐
        │                                       │  GHCR registry │
        │                                       │  (your image)  │
        │                                       └───────┬────────┘
        │                                               │
        │                              SSH + docker     │ docker pull
        │                              compose pull     │
        │                                               ▼
        │                                       ┌────────────────┐
        └──── ssh myvps ────────────────────────►│   Your VPS    │
                                                │   (Ubuntu)     │
                                                │                │
                                                │  ┌──────────┐  │
                                                │  │ infra    │  │
                                                │  │ stack    │  │
                                                │  │ (postgres,│  │
                                                │  │  caddy)  │  │
                                                │  └────┬─────┘  │
                                                │       │        │
                                                │  shared network│
                                                │       │        │
                                                │  ┌────┴─────┐  │
                                                │  │ app 1    │  │
                                                │  │ app 2    │  │
                                                │  │ app N    │  │
                                                │  └──────────┘  │
                                                └────────────────┘
```

### The principles

1. **One image, many environments.** The Docker image you push to GHCR is the same artifact that runs in your local dev container and on the VPS. Configuration (env vars) is the only thing that varies.
2. **Stacks, not monoliths.** Each app is its own docker-compose stack. Shared services (Postgres, reverse proxy) live in a separate `infra` stack. Stacks talk to each other over a Docker network you create manually.
3. **Secrets never go in images.** Secrets live in `.env` files on the machine that runs the container, injected at runtime.
4. **CI builds, CD deploys.** GitHub Actions builds and pushes the image; a separate step SSHes in and runs `docker compose pull && up -d`. Two distinct phases, each independently debuggable.
5. **Separation of identity.** *You* SSH in as a sudo-capable user for admin work. *CI* SSHes in as a sandboxed `deploy` user with docker access but no sudo. *Apps* connect to Postgres as per-app users that own only their own database.

If you understand these five, everything below is just implementation detail.

### Why this architecture vs. alternatives

| Pattern | Verdict | Why |
|---|---|---|
| **Fly.io / Railway / Render** | Use these if you want zero-ops. Free tiers are tight. | Best simplicity. But: monthly costs scale per-app, less learning. |
| **Heroku-style PaaS on your VPS (Coolify, Dokploy)** | Reasonable upgrade if/when ops becomes a burden. | Web UI, less to learn upfront, but a heavier abstraction to debug when it breaks. |
| **One docker-compose file for everything** | Don't. | Adding an app requires editing one big file; deploys risk bouncing everything. |
| **Kubernetes (k3s, k0s)** | Overkill for a personal VPS. | The complexity tax isn't justified until you have ≥5 nodes or genuine HA needs. |
| **Plain systemd + Python venv on the host** | Works, but loses you "same image in dev and prod." | Migrating between machines is painful; toolchain drift accumulates. |
| **Stacks + shared network (this guide)** | The sweet spot for 1–10 apps on one box. | Adds one app at a time without disturbing others; same workflow scales. |

---

## 2. SSH key strategy: one key, every environment

### The goal

Generate **one** Ed25519 keypair. Use it from WSL, from Windows-native tools, and from inside any dev container. Don't proliferate keys; that way lies "wait, which key does this machine know?"

There's a separate consideration for **CI deploy keys** (used by GitHub Actions to SSH into the VPS). That key is *intentionally* different — narrower scope, no passphrase, never on your laptop's SSH agent. See [§ 9](#9-building-images-with-github-actions--ghcr) for that.

### Why WSL is the right canonical home for your personal key

- **Performance.** ext4 honors strict file permissions; SSH refuses keys with sloppy perms. The 9p mount of `/mnt/c` doesn't behave well here.
- **Where you actually work.** Day-to-day terminal work happens in WSL.
- **Dev container forwarding.** VS Code Dev Containers automatically forward your WSL `ssh-agent` into the container with zero config.
- **Easy to back up to Windows.** Copy the keypair into `C:\Users\<you>\.ssh\` as a backup that survives a WSL distro reinstall.

### Step 2.1 — Generate the key

In WSL:

```bash
ssh-keygen -t ed25519 -C "you@example.com"
# accept default path: ~/.ssh/id_ed25519
# set a passphrase — yes, really
```

**Why Ed25519?** Smaller, faster, more secure than RSA. Supported by every modern SSH server and by GitHub. Don't use RSA in 2026.

**Why a passphrase?** It's protection-in-depth: if your laptop is stolen with the disk decrypted, the attacker still needs your passphrase. `ssh-agent` caches the unlocked key for the session, so you type it once.

### Step 2.2 — Persistent ssh-agent in WSL

Without persistence, every new terminal asks for your passphrase. Install `keychain`:

```bash
sudo apt install keychain
```

Add to `~/.bashrc`:

```bash
eval "$(keychain --eval --quiet id_ed25519)"
```

Open a new terminal, type the passphrase once when prompted, and every subsequent terminal reuses the same agent.

**Why `keychain` over raw `ssh-agent`?**
- Raw `ssh-agent` starts a *new* agent per shell unless you manually track the socket path.
- `keychain` finds an existing agent and reuses it, or starts a new one only if needed.
- Survives terminal close/reopen, only dies on system reboot (or WSL shutdown).

**Alternative: 1Password SSH Agent.** If you already use 1Password, its built-in SSH agent is genuinely better — key never touches disk, syncs across devices, biometric auth per use. You'd point `SSH_AUTH_SOCK` at 1Password's socket and skip `keychain`. Worth it if you're already paying for 1Password.

### Step 2.3 — Mirror to Windows for native tools (optional)

If you ever use Git for Windows, VS Code on the Windows side directly, or GitHub Desktop:

```bash
# in WSL, copy the keypair into Windows' .ssh dir
mkdir -p /mnt/c/Users/<YOUR_WINDOWS_USERNAME>/.ssh
cp ~/.ssh/id_ed25519 ~/.ssh/id_ed25519.pub /mnt/c/Users/<YOUR_WINDOWS_USERNAME>/.ssh/
```

Then in **PowerShell** as administrator (one time):

```powershell
Get-Service ssh-agent | Set-Service -StartupType Automatic
Start-Service ssh-agent
ssh-add $env:USERPROFILE\.ssh\id_ed25519
```

This also serves as your **key backup** — if you ever blow away your WSL distro, the key still exists on the Windows side.

### Step 2.4 — Add the public key to GitHub

```bash
cat ~/.ssh/id_ed25519.pub
```

Copy the output. Go to [github.com/settings/keys](https://github.com/settings/keys) → "New SSH key" → paste. Title it something like "WSL on laptop, 2026".

Test:

```bash
ssh -T git@github.com
# expect: "Hi <username>! You've successfully authenticated..."
```

### Step 2.5 — Dev container forwarding (automatic)

You don't need to do anything special. VS Code's Dev Containers extension automatically forwards your WSL `ssh-agent` socket into any container it builds. Once you're inside a dev container, verify:

```bash
ssh-add -L
# should list your public key
ssh -T git@github.com
# should authenticate
```

If it doesn't, see [Troubleshooting](#15-troubleshooting).

### Step 2.6 — Ad-hoc `docker run` containers

For one-off containers that aren't dev containers but need SSH:

```bash
docker run -it --rm \
  -v "$SSH_AUTH_SOCK:/ssh-agent" \
  -e SSH_AUTH_SOCK=/ssh-agent \
  myimage
```

You're mounting the agent's Unix socket from the host into the container and pointing the container's `SSH_AUTH_SOCK` at it. The container has no copy of the key, just access to the agent that holds it.

### Step 2.7 — SSH config sweetener

In `~/.ssh/config`:

```
Host github.com
  AddKeysToAgent yes
  IdentityFile ~/.ssh/id_ed25519

# Filled in after VPS setup:
Host myvps
  HostName <vps-ip-or-domain>
  User julian
  IdentityFile ~/.ssh/id_ed25519
```

Now `ssh myvps` just works. Add a similar block for the deploy user if you want to SSH in as `deploy` for debugging.

---

## 3. Setting up a fresh Ubuntu VPS

You have a VPS with an IP address and either a root password or a "paste this SSH key in" form during provisioning. If your provider lets you paste a key during provisioning, paste your `~/.ssh/id_ed25519.pub` from Step 2.4 and skip directly to Step 3.3.

### Step 3.1 — First login as root

From WSL:

```bash
ssh root@<vps-ip>
# enter the provider's initial password if prompted
```

### Step 3.2 — Update everything

```bash
apt update && apt upgrade -y
hostnamectl set-hostname my-vps          # whatever you want to call this box
timedatectl set-timezone America/Chicago  # or whichever
```

**Why upgrade first?** Provider images are often weeks out of date. Patching is the single highest-leverage security action you can take, and `unattended-upgrades` (Step 3.7) keeps you patched going forward.

### Step 3.3 — Create your interactive user

```bash
adduser julian                    # prompts for password; used only for sudo
usermod -aG sudo julian
```

**Why a separate user instead of using root?**
- A momentary `rm -rf` typo as root is catastrophic. As `julian`, sudo asks for a password and gives you a half-second to think.
- Audit logs distinguish "what did the human do" from "what did the system do."
- Standard Unix hygiene.

### Step 3.4 — Install your public key for the new user

From a **new WSL terminal** (keep the root session open as a safety net):

```bash
ssh-copy-id julian@<vps-ip>
# enter julian's password once
ssh julian@<vps-ip>
# should log in without password
```

`ssh-copy-id` appends your public key to `/home/julian/.ssh/authorized_keys` and fixes the permissions correctly. Don't try to do this by hand the first time; you will get a permissions detail wrong and lock yourself out.

### Step 3.5 — Lock down SSH

As `julian` on the VPS:

```bash
sudo nano /etc/ssh/sshd_config
```

Find and set:

```
PermitRootLogin no
PasswordAuthentication no
PubkeyAuthentication yes
```

Then:

```bash
sudo systemctl restart ssh
```

**Critical safety step:** *Before closing your current session*, open a **new** WSL terminal and confirm `ssh julian@<vps-ip>` still works. If it does, you're safe to close everything. If it doesn't, you have the original session to fix it. Don't skip this; misconfigured sshd is the #1 way personal VPSes get locked out forever.

### Step 3.6 — Firewall

```bash
sudo ufw allow OpenSSH
sudo ufw enable
sudo ufw status
```

That's it. Discord bots and other outbound-only services don't need any inbound ports. When you add a reverse proxy in [§ 12](#12-reverse-proxy-with-caddy-https-for-web-apps), you'll add `sudo ufw allow 80/tcp` and `sudo ufw allow 443/tcp`.

**Why UFW over plain iptables?** UFW is iptables with a sane interface. It's not less powerful; it's just less typo-prone.

### Step 3.7 — Automatic security patches

```bash
sudo apt install -y unattended-upgrades
sudo dpkg-reconfigure --priority=low unattended-upgrades
# select "Yes" when prompted
```

By default this installs **security-only** patches automatically (no feature upgrades, no breaking changes). The box will reboot itself in the middle of the night only if a kernel update requires it. Configurable in `/etc/apt/apt.conf.d/50unattended-upgrades`.

### Step 3.8 — Install Docker Engine

```bash
curl -fsSL https://get.docker.com | sudo sh
sudo usermod -aG docker julian
# log out and back in for group to take effect
exit
ssh julian@<vps-ip>
docker run hello-world    # should succeed without sudo
```

**Why the official install script instead of `apt install docker.io`?** The Ubuntu repo's `docker.io` is often months behind. The official script adds Docker's apt repo and pulls the latest stable version, which you'll want for security and features like BuildKit defaults.

**Why add yourself to the docker group?** So you don't have to `sudo docker` every time. **Caveat:** anyone in the docker group can effectively get root (via `docker run --privileged`). This is the standard tradeoff for single-admin personal servers; don't add `deploy` to sudoers as well.

### Step 3.9 — Create the deploy user (for CI)

```bash
sudo adduser --disabled-password --gecos "" deploy
sudo usermod -aG docker deploy
```

The deploy user:
- Has no password (can only log in with SSH key)
- Has docker access (can run containers, build, etc.)
- Has **no** sudo (compromise of the deploy key cannot take over the box)
- Has its own home directory `/home/deploy/` where app directories live

### Step 3.10 — Generate the CI deploy key

Do this **on your laptop**, not on the VPS. The private half will live in GitHub, never on your local SSH agent.

```bash
ssh-keygen -t ed25519 -f ~/.ssh/vps-deploy -C "github-actions deploy key" -N ""
```

`-N ""` means no passphrase — CI has no way to type one. The reduced security is mitigated by:
- Key is single-purpose (deploy user only, no sudo)
- Key only exists in GitHub Secrets (encrypted at rest)
- You can revoke it instantly by removing it from `/home/deploy/.ssh/authorized_keys`

### Step 3.11 — Install the deploy key on the VPS

```bash
# from WSL
scp ~/.ssh/vps-deploy.pub julian@<vps-ip>:/tmp/

# on the VPS
sudo mkdir -p /home/deploy/.ssh
sudo cp /tmp/vps-deploy.pub /home/deploy/.ssh/authorized_keys
sudo chown -R deploy:deploy /home/deploy/.ssh
sudo chmod 700 /home/deploy/.ssh
sudo chmod 600 /home/deploy/.ssh/authorized_keys
```

Test from your laptop:

```bash
ssh -i ~/.ssh/vps-deploy deploy@<vps-ip> "docker ps"
# should show running containers (probably none yet)
```

### Step 3.12 — Quality-of-life touches

As `julian` on the VPS:

```bash
# helpful aliases
cat >> ~/.bashrc << 'EOF'
alias dc='docker compose'
alias dlogs='docker compose logs -f --tail=100'
alias dexec='docker compose exec'
alias dps='docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Image}}"'
EOF

# debug tools you'll be glad to have at 11pm
sudo apt install -y htop ncdu jq tree
```

### Step 3.13 — Update your local SSH config

In `~/.ssh/config` on WSL:

```
Host myvps
  HostName <vps-ip>
  User julian
  IdentityFile ~/.ssh/id_ed25519

Host myvps-deploy
  HostName <vps-ip>
  User deploy
  IdentityFile ~/.ssh/vps-deploy
```

Now `ssh myvps` is your admin login; `ssh myvps-deploy` lets you debug as the deploy user when something goes wrong with CI.

### Checkpoint

At this point you have:
- A locked-down VPS, key-only SSH, root login disabled
- Two distinct identities: `julian` (you, sudo) and `deploy` (CI, docker only)
- Docker Engine installed and working
- Auto security patches running

You have not yet:
- Created the shared network
- Installed any services
- Configured any apps

Those are the next sections. But first, a deeper look at the users you just created.

---

## 4. Managing OS and database users

The previous section created two OS users. This section gives you a model for thinking about users, the commands to audit/verify them, and the playbooks for things you'll need later: rotating keys, adding collaborators, adding per-app database users.

### 4.1 — The user model

Three categories of identity exist on a personal VPS:

| Identity | Type | Purpose | Has sudo? | Has docker? | Authenticates with |
|---|---|---|---|---|---|
| `julian` (you) | OS user | Admin work, interactive use | Yes | Yes | Your personal SSH key |
| `deploy` | OS user | CI/CD only | No | Yes | The CI deploy key (in GH Secrets) |
| `botuser`, `dashuser`, etc. | Postgres user | Apps connecting to DB | n/a | n/a | Password in app `.env` |

The principle: each identity has the **minimum** privileges for its job.
- If your personal key leaks → attacker has full sudo. Bad, but you control rotation.
- If the CI deploy key leaks → attacker can deploy containers, but no sudo and no shell escape from docker group (well, mostly — see §4.3 caveat).
- If an app's `.env` leaks → attacker has access to that app's database **only**.

### 4.2 — Auditing OS users

Run this on the VPS to see what you have:

```bash
# list all users with login shells (excludes system/service accounts)
getent passwd | awk -F: '$7 ~ /(bash|zsh|sh)$/ {print $1, $7}'

# what groups is each user in?
groups julian
groups deploy

# who can sudo?
sudo grep -r '' /etc/sudoers /etc/sudoers.d/ 2>/dev/null
getent group sudo

# who can use docker?
getent group docker

# what SSH keys are authorized for each user?
sudo cat /home/julian/.ssh/authorized_keys
sudo cat /home/deploy/.ssh/authorized_keys

# is password auth disabled at the daemon level?
sudo grep -E '^(PasswordAuthentication|PubkeyAuthentication|PermitRootLogin)' /etc/ssh/sshd_config
```

### 4.3 — What "good" looks like

**For `julian` (your interactive user):**
- ✅ In groups `sudo` and `docker`
- ✅ `~/.ssh/authorized_keys` contains exactly your personal `id_ed25519.pub`
- ✅ Has a password (used for sudo prompts, not for SSH)
- ✅ Can SSH in with key, escalates with `sudo` + password
- ✅ Owns `/home/julian/` and everything under it

**For `deploy` (CI user):**
- ✅ In group `docker` only — **not** in `sudo`
- ✅ `~/.ssh/authorized_keys` contains exactly the CI deploy public key
- ✅ Has no password (`--disabled-password` at creation time)
- ✅ Owns `/home/deploy/` and all app subdirectories

**For both:**
- ✅ `PasswordAuthentication no` in sshd_config
- ✅ `PermitRootLogin no` in sshd_config
- ✅ UFW firewall enabled with only OpenSSH allowed

**Caveat about the docker group:** anyone in the docker group can mount the host filesystem into a privileged container and effectively become root. This is a known property of Docker, not a bug. The mitigations:
- Only put accounts you trust into the docker group (you and the deploy user).
- Treat the deploy SSH key as effectively root-equivalent. Rotate it on suspected compromise.
- For higher-paranoia setups, use rootless Docker — but that's a separate guide.

### 4.4 — Rotating the CI deploy key

Do this every 6–12 months, or immediately if you suspect the key is compromised.

```bash
# 1. Generate a new key on your laptop
ssh-keygen -t ed25519 -f ~/.ssh/vps-deploy-new -C "github-actions deploy key" -N ""

# 2. Append the new public key to VPS authorized_keys (keep the old one for now)
scp ~/.ssh/vps-deploy-new.pub julian@<vps-ip>:/tmp/
ssh myvps
sudo bash -c "cat /tmp/vps-deploy-new.pub >> /home/deploy/.ssh/authorized_keys"

# 3. Update VPS_SSH_KEY secret in GitHub repo settings with the new private key contents

# 4. Trigger a deploy to verify (empty commit works)
git commit --allow-empty -m "test new deploy key" && git push

# 5. Once verified, remove the OLD key line from /home/deploy/.ssh/authorized_keys

# 6. Replace local copies
rm ~/.ssh/vps-deploy
mv ~/.ssh/vps-deploy-new ~/.ssh/vps-deploy
mv ~/.ssh/vps-deploy-new.pub ~/.ssh/vps-deploy.pub
```

The two-step process (add new, then remove old) means you never have a window with no working key. If something breaks, the old key still works.

### 4.5 — Adding a collaborator user

Say a friend is helping with one project. Don't share your `julian` account.

```bash
# on the VPS as julian
sudo adduser alice                       # set initial password
sudo usermod -aG docker alice            # if they need to manage containers
# DO NOT add to sudo unless they truly need it
```

They send you their public key (`id_ed25519.pub`):

```bash
sudo mkdir -p /home/alice/.ssh
sudo nano /home/alice/.ssh/authorized_keys  # paste their key
sudo chown -R alice:alice /home/alice/.ssh
sudo chmod 700 /home/alice/.ssh
sudo chmod 600 /home/alice/.ssh/authorized_keys
```

To revoke later: `sudo deluser --remove-home alice`.

**Scoping their access:** if alice should only touch one app, give her `chown alice:alice /home/deploy/alice-project/` (or move that project out of `deploy`'s home entirely). Don't put her in the docker group if she doesn't need it.

### 4.6 — Removing a user safely

```bash
# stop any of their running containers first
docker ps --filter "label=user=alice"     # if you label by user

# delete the user and their home directory
sudo deluser --remove-home alice

# audit what they may have left running
docker ps -a
crontab -l -u alice 2>/dev/null
```

### 4.7 — Database users: the per-app pattern

Every app gets its own Postgres user that owns exactly one database. Apps cannot read each other's data.

```sql
-- as the postgres superuser (connect via: docker compose exec postgres psql -U postgres)
CREATE USER botuser WITH PASSWORD 'long-random-string-A';
CREATE DATABASE botdb OWNER botuser;
-- botuser now has full privileges on botdb only, zero access elsewhere

CREATE USER dashuser WITH PASSWORD 'long-random-string-B';
CREATE DATABASE dashdb OWNER dashuser;
```

Generating strong passwords:

```bash
openssl rand -base64 24
```

Save passwords to:
1. The app's `.env` on the VPS (`/home/deploy/<app>/.env`)
2. A password manager as a long-term backup

Never commit them to git.

### 4.8 — Auditing database users

Connect to the shared Postgres:

```bash
cd ~/infra && docker compose exec postgres psql -U postgres
```

Useful psql commands:

```sql
\du                       -- list all users and their role attributes
\l                        -- list all databases and their owners
\du+ botuser              -- detailed info on one user, including memberships
\l+ botdb                 -- detailed info on one database

-- connect to a specific db
\c botdb

-- table-level permissions in current db
\dp

-- the schema search path
SHOW search_path;
```

What you want to see in `\du`:
- Each app user has **no** "Superuser", "Create role", or "Create DB" attributes
- The `postgres` user is the only one with elevated attributes
- No user has an empty password (column will show "Cannot login" if locked out)

What you want to see in `\l`:
- Each app database is owned by its corresponding app user
- No database is owned by `postgres` (other than the built-ins `postgres`, `template0`, `template1`)

### 4.9 — Rotating a database password

When you suspect a password has leaked, or on a hygiene schedule:

```sql
ALTER USER botuser WITH PASSWORD 'new-long-random-string';
```

Then update the app's `.env` on the VPS and restart:

```bash
cd ~/apm-bot
nano .env                              # update DATABASE_URL with new password
docker compose up -d                   # restart with new env
```

The bot reconnects with the new password. Brief disconnect (~2 seconds), no data loss for a Discord bot that's idempotent.

### 4.10 — Read-only user for debugging/analytics

When you want to poke at production data without risk of mutation:

```sql
CREATE USER bot_readonly WITH PASSWORD 'another-random-string';
GRANT CONNECT ON DATABASE botdb TO bot_readonly;
\c botdb
GRANT USAGE ON SCHEMA public TO bot_readonly;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO bot_readonly;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON TABLES TO bot_readonly;
```

The `ALTER DEFAULT PRIVILEGES` line is important: new tables created by future migrations are automatically readable. Without it, you'd have to re-grant after every migration.

To connect from your laptop **without exposing Postgres publicly**, use an SSH tunnel:

```bash
# in WSL — this binds local 15432 to the VPS's container postgres:5432 via SSH
ssh -L 15432:localhost:5432 myvps

# in another terminal
psql "postgresql://bot_readonly:password@localhost:15432/botdb"
```

Note: `localhost:5432` from the VPS's perspective is the VPS host, not the container. To reach the container, you need an `ssh -L` plus a target Postgres that's bound to the docker bridge — easier to add a temporary published port to the infra compose, then remove it. Alternative: install psql on the VPS itself and run queries locally there.

### 4.11 — The full user audit checklist

Run quarterly:

- [ ] `cat /etc/passwd` — any users you don't recognize?
- [ ] `groups julian` + `groups deploy` — correct group memberships?
- [ ] `sudo cat /home/julian/.ssh/authorized_keys` — only your keys, no surprises?
- [ ] `sudo cat /home/deploy/.ssh/authorized_keys` — only the current CI deploy key?
- [ ] `last -a` — any logins from IPs you don't recognize?
- [ ] `journalctl -u ssh -n 100 | grep "Failed password"` — any brute force attempts? (with password auth disabled, these should fail harmlessly)
- [ ] In psql: `\du` — only expected app users, none with elevated privileges?

---

## 5. The shared infrastructure stack on the VPS

The "infra" stack holds services that *every other app* depends on: Postgres, eventually a reverse proxy, optionally a backup runner. You bring it up once, and it stays up forever (well, until a reboot, then it restarts itself).

### Step 5.1 — Create the shared Docker network

As `deploy` on the VPS:

```bash
sudo -iu deploy           # switch from julian to deploy
docker network create shared
```

**Why a manually-created network instead of letting compose create one?** Compose-created networks are scoped to a single compose project. We want one network that *multiple* stacks share. You create it once by hand, then every compose file references it as `external: true`.

**Naming:** I use `shared`. Some people use `web` or `proxy`. It doesn't matter, just be consistent.

### Step 5.2 — Set up the directory structure

```bash
mkdir -p ~/infra
mkdir -p ~/apm-bot       # placeholder for your first app
```

You'll add one directory per app under `/home/deploy/`. Each holds a `docker-compose.yml` and a `.env`.

### Step 5.3 — The infra compose file

Create `/home/deploy/infra/docker-compose.yml`:

```yaml
networks:
  shared:
    external: true

services:
  postgres:
    image: postgres:16
    restart: unless-stopped
    environment:
      POSTGRES_PASSWORD: ${POSTGRES_ROOT_PASSWORD}
    volumes:
      - postgres_data:/var/lib/postgresql/data
    networks:
      - shared
    # NOTE: no `ports:` block — Postgres is NOT exposed to the internet.
    # Only other containers on the `shared` network can reach it.
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U postgres"]
      interval: 10s
      timeout: 5s
      retries: 5

volumes:
  postgres_data:
```

**Why pin to `postgres:16` and not `postgres:latest`?** `:latest` will silently upgrade you to Postgres 17, 18, etc. across reboots. Major version upgrades for Postgres are *not automatic* — they require a dump/restore. Pin to a major version so you upgrade on your schedule, not on Docker's.

**Why `restart: unless-stopped`?** Survives reboots and crashes, but a manual `docker compose stop` actually stays stopped (unlike `restart: always`, which fights you).

**Why no `ports:` exposed?** Postgres on `0.0.0.0:5432` is an invitation to brute force. With no `ports:`, the only way to reach Postgres is from another container on the `shared` network. This is the safest default.

**Why a named volume `postgres_data` and not a bind mount?** Docker manages named volumes; they're easier to back up and survive `docker compose down`. Bind mounts (`./data:/var/lib/postgresql/data`) put you in charge of permissions, which Postgres is picky about.

### Step 5.4 — The infra .env

Create `/home/deploy/infra/.env`:

```
POSTGRES_ROOT_PASSWORD=<a-long-random-string-here>
```

Generate one:

```bash
openssl rand -base64 32
```

Save this password somewhere safe (password manager). You'll only use the root user to create app-specific databases.

### Step 5.5 — Bring up the infra stack

```bash
cd ~/infra
docker compose up -d
docker compose ps        # confirm postgres is healthy
docker compose logs postgres
```

### Step 5.6 — Create your first app's database

```bash
docker compose exec postgres psql -U postgres
```

In the psql prompt:

```sql
CREATE USER botuser WITH PASSWORD 'a-different-long-random-string';
CREATE DATABASE botdb OWNER botuser;
GRANT ALL PRIVILEGES ON DATABASE botdb TO botuser;
\q
```

Repeat this pattern for each new app you add. See [§ 4.7](#47--database-users-the-per-app-pattern) for the full per-app pattern.

### Checkpoint

The VPS now has:
- A `shared` Docker network all apps will join
- Postgres running, accessible to other containers as hostname `postgres`, port `5432`
- One database (`botdb`) with its own user
- The directory structure ready for app stacks

---

## 6. Structuring a containerized app repo

We'll use the APM Discord bot as the worked example (Python + uv + discord.py). The patterns generalize: substitute your language's idioms.

### Step 6.1 — Repo layout

```
apm-class-bot/
├── .devcontainer/
│   └── devcontainer.json       # tells VS Code how to build the dev container
├── .github/
│   └── workflows/
│       ├── build.yml           # CI: build and push image to GHCR
│       └── deploy.yml          # CD: SSH to VPS and restart
├── alembic/                    # migrations (after §13)
│   ├── env.py
│   ├── script.py.mako
│   └── versions/
├── alembic.ini
├── src/
│   └── bot/
│       └── __init__.py
│       └── main.py
├── tests/
├── .dockerignore
├── .env.example                # template, committed
├── .env                        # real local values, gitignored
├── .gitignore
├── docker-compose.yml          # LOCAL DEV only (includes postgres)
├── Dockerfile                  # one Dockerfile, used everywhere
├── pyproject.toml
├── README.md
└── uv.lock
```

**One Dockerfile, multiple uses:**
- Dev container (VS Code builds it locally)
- Local dev with docker-compose (`build: .`)
- CI (built and pushed to GHCR)
- Production (pulled from GHCR by the VPS)

Same artifact in every environment. This is the property that eliminates "works on my machine."

### Step 6.2 — The Dockerfile (multi-stage, dev + runtime)

```dockerfile
# syntax=docker/dockerfile:1.7

# ── Base stage: shared dependencies ────────────────────────────────
FROM python:3.12-slim AS base

# Install uv (fast Python package manager)
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

ENV UV_LINK_MODE=copy \
    UV_COMPILE_BYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

# Install runtime dependencies first (better layer caching)
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-install-project --no-dev

# ── Dev stage: adds dev tools ──────────────────────────────────────
FROM base AS dev

RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    curl \
    openssh-client \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# Install dev dependencies
RUN uv sync --frozen --no-install-project

# Don't COPY source — dev container mounts it as a volume
CMD ["bash"]

# ── Runtime stage: minimal image for production ────────────────────
FROM base AS runtime

# Copy source code into the image
COPY src ./src
COPY alembic alembic
COPY alembic.ini ./

# Install the project itself
RUN uv sync --frozen --no-dev

# Create a non-root user
RUN useradd --create-home --shell /bin/bash app
USER app

CMD ["uv", "run", "python", "-m", "bot.main"]
```

**Why multi-stage?**
- `base` is the common layer (Python + uv + dependency install).
- `dev` extends it with debugging tools and dev dependencies. The dev container uses this stage.
- `runtime` is the minimal production image — no git, no debuggers, no dev deps. Smaller, less attack surface.

**Why `uv` instead of pip?** Speed (10-100× faster), reproducible installs from `uv.lock`, single tool for venv + package management. If you're using pip/poetry, substitute appropriately.

**Why install deps before COPY src?** Docker caches each layer. Code changes far more often than dependencies. By installing deps before copying source, a code change only invalidates the final COPY layer, not the whole dependency install.

**Why `USER app` in runtime?** Containers run as root by default. Running as a non-root user inside the container is a defense-in-depth measure: if an attacker exploits a bug in your app, they're constrained to the `app` user's permissions inside the container, not root.

**Why include `postgresql-client` in the dev stage?** So `psql` is available inside the dev container for debugging — connecting to the local Postgres service is one command.

**Alternative: separate `Dockerfile.dev` and `Dockerfile`.** Some teams prefer this for clarity. Multi-stage is more DRY (one file, one place to update Python version, etc.) but multi-stage knowledge is a prerequisite. Pick what fits your team.

### Step 6.3 — The `.dockerignore`

```
# secrets
.env
.env.*

# version control
.git
.gitignore

# python
__pycache__
*.pyc
.venv
.pytest_cache
.mypy_cache
.ruff_cache

# editor
.vscode
.idea
*.swp

# docs / artifacts not needed at runtime
docs/
*.md
!README.md
```

**Why .dockerignore matters:** Without it, `COPY . .` pulls in everything — `.env`, `.git`, `__pycache__`, and so on. Secrets leak into image layers; image sizes balloon; cache invalidates on every git commit because `.git` changed.

### Step 6.4 — The `.env.example` (committed)

```
# Discord
DISCORD_TOKEN=replace-me-with-dev-bot-token

# Database — points at the `postgres` service in docker-compose.yml
DATABASE_URL=postgresql://botuser:dev@postgres:5432/botdb

# Logging
LOG_LEVEL=DEBUG
```

`.env.example` is the contract: "here are the variables this app reads." Future-you (or future-collaborator) copies this to `.env` and fills in real values.

### Step 6.5 — The local-dev `docker-compose.yml` (committed)

```yaml
services:
  postgres:
    image: postgres:16
    environment:
      POSTGRES_USER: botuser
      POSTGRES_PASSWORD: dev
      POSTGRES_DB: botdb
    ports:
      - "5432:5432"           # exposed to host so you can use psql/DBeaver/etc.
    volumes:
      - postgres_dev_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U botuser -d botdb"]
      interval: 5s
      timeout: 3s
      retries: 5

  bot:
    build:
      context: .
      target: runtime          # build the runtime stage by default
    env_file: .env
    depends_on:
      postgres:
        condition: service_healthy
    develop:
      watch:
        - action: sync
          path: ./src
          target: /app/src     # hot reload on file change (compose v2.22+)
        - action: rebuild
          path: pyproject.toml # rebuild if deps change

  migrate:
    build:
      context: .
      target: runtime
    profiles: ["migrate"]      # only runs when explicitly invoked
    env_file: .env
    depends_on:
      postgres:
        condition: service_healthy
    command: uv run alembic upgrade head

volumes:
  postgres_dev_data:
```

**Why expose Postgres on `5432` in dev but not in prod?** In dev, you want to be able to connect with DBeaver/psql/pgAdmin from your host. In prod, you don't — the only thing that needs to talk to Postgres is the bot, and it does so over the shared network.

**Why `condition: service_healthy`?** Without it, `bot` would start the instant the `postgres` container starts — but Postgres takes a second or two to actually accept connections, and your bot would crash on its first DB query. The healthcheck ensures `bot` waits for `pg_isready` to return success.

**Why `develop.watch.sync`?** Modern compose can hot-reload code into a running container by syncing files. You edit, save, the container sees the new file immediately. Cleaner than a bind mount because it respects `.dockerignore` and is opt-in.

**Why a `migrate` service with `profiles:`?** Services with profiles are excluded from `docker compose up` by default. You invoke them explicitly with `docker compose run --rm migrate`. This means migrations never run "by accident" — see [§ 13](#13-database-migrations-without-tears).

### Step 6.6 — `.gitignore`

```
.env
.env.local
.venv
__pycache__
*.pyc
.pytest_cache
.mypy_cache
.ruff_cache
.coverage
```

---

## 7. Local development with VS Code Dev Containers

The promise of dev containers: **your editor, debugger, language server, and runtime are all inside the same Linux container that ships to prod.** No "I have the wrong Python version locally," no "this works in CI but not on my laptop," no juggling pyenv/asdf/nvm.

### Step 7.1 — The `.devcontainer/devcontainer.json`

Create `apm-class-bot/.devcontainer/devcontainer.json`:

```json
{
  "name": "apm-class-bot dev",
  "dockerComposeFile": ["../docker-compose.yml"],
  "service": "bot",
  "workspaceFolder": "/app",
  "shutdownAction": "stopCompose",

  "build": {
    "target": "dev"
  },

  "overrideCommand": true,
  "customizations": {
    "vscode": {
      "extensions": [
        "ms-python.python",
        "ms-python.vscode-pylance",
        "charliermarsh.ruff",
        "tamasfe.even-better-toml",
        "ms-azuretools.vscode-docker",
        "mtxr.sqltools",
        "mtxr.sqltools-driver-pg"
      ],
      "settings": {
        "python.defaultInterpreterPath": "/app/.venv/bin/python",
        "python.terminal.activateEnvironment": false,
        "editor.formatOnSave": true,
        "[python]": {
          "editor.defaultFormatter": "charliermarsh.ruff"
        }
      }
    }
  },

  "forwardPorts": [5432],
  "remoteUser": "root"
}
```

**Key fields explained:**

- `dockerComposeFile` + `service`: reuse the same `docker-compose.yml` you'd use for `docker compose up` directly. VS Code attaches to the `bot` service.
- `build.target: "dev"`: build the **dev** stage of your multi-stage Dockerfile (with dev tools), not the slim `runtime` stage.
- `workspaceFolder`: where your repo gets mounted inside the container. VS Code opens here.
- `shutdownAction: "stopCompose"`: when you close VS Code, the containers stop. Otherwise they linger.
- `overrideCommand: true`: tells VS Code not to run the Dockerfile's `CMD` — VS Code keeps the container alive with its own idle process so you can use the integrated terminal.
- `forwardPorts`: surfaces ports from the container to your host. `5432` lets you connect to the dev Postgres from Windows/WSL.
- `customizations.vscode.extensions`: extensions auto-install in the dev container. Your local VS Code's extensions don't automatically transfer — list the ones you want.
- `remoteUser`: which user VS Code runs as inside the container. For dev, root is fine (you need to install things). Production runs as the `app` user via the Dockerfile's `USER` directive.

### Step 7.2 — Opening the project in a dev container

1. Open VS Code on Windows.
2. Use the Remote-WSL extension: `Ctrl-Shift-P` → "Remote-WSL: Open Folder in WSL" → navigate to `~/dev/apm-class-bot`.
3. VS Code now shows "WSL: Ubuntu" in the bottom-left.
4. `Ctrl-Shift-P` → "Dev Containers: Reopen in Container".
5. First time: VS Code runs `docker compose up`, builds the dev stage of your image, attaches. Takes 1-3 minutes. Subsequent opens are nearly instant.

When it's ready, the bottom-left shows "Dev Container: apm-class-bot dev". Open the integrated terminal — you're inside the container. Run `python --version` to confirm.

### Step 7.3 — What you get for free inside the container

- **Same Python version as production.** No drift possible.
- **Same OS packages.** `apt list --installed` matches what'll run on the VPS.
- **Pre-installed dependencies.** No `pip install` step on first open — the Dockerfile did it during build.
- **Hot reload.** Edit a file under `src/`, save it, the container sees the new content immediately (via `develop.watch.sync`).
- **Postgres at hostname `postgres`.** Try `psql -h postgres -U botuser -d botdb` from inside the dev container — it works because both containers are on the compose-managed network.
- **Forwarded ssh-agent.** `git push` works without configuration.
- **All your VS Code extensions** (the ones listed in `devcontainer.json`) installed automatically.

### Step 7.4 — Running the bot inside the dev container

In the VS Code integrated terminal:

```bash
uv run python -m bot.main
```

The bot connects to the `postgres` container (no Docker-host port forwarding needed for inter-container traffic), loads the dev token from `.env`, and runs.

### Step 7.5 — Running tests, formatters, linters

```bash
uv run pytest
uv run ruff check
uv run ruff format
```

Same commands you'd run in CI. They produce the same results because they're running in the same environment.

### Step 7.6 — Database access from your host machine

The compose file forwards `5432` to your host. Connect from DBeaver/pgAdmin/psql on Windows or WSL:

```
Host:     localhost
Port:     5432
Database: botdb
User:     botuser
Password: dev
```

### Step 7.7 — Rebuilding when the Dockerfile changes

If you edit `Dockerfile` or `pyproject.toml`:

`Ctrl-Shift-P` → "Dev Containers: Rebuild Container". Takes 30-90 seconds. Smaller changes (pure code) don't need a rebuild — they're synced live.

### Why this beats local-Python-with-venv

Things that just *can't happen* with dev containers:

- "I'm on Python 3.11, prod is on 3.12, and my code uses `match` statements wrong." → Impossible. Same Python.
- "I installed libpq-dev locally but it's not in the prod image." → Impossible. Same OS.
- "It works on my Mac but not on the Linux VPS." → Impossible. Container is Linux either way.
- "I forgot to run `uv pip install` before this commit." → Impossible. The container already has the deps; if you add a dep, you commit `pyproject.toml`+`uv.lock` together.

The tax you pay: ~1 minute on the first container build, and a bit of mental overhead about what "inside" vs "outside" the container means. Worth it.

---

## 8. Day-to-day development cycles

You have a working setup. What does an actual day look like? This section walks through the most common workflows, in order of how often you'll do them.

### 8.1 — Morning routine: starting work

```bash
# in WSL
cd ~/dev/apm-class-bot
git pull --rebase
code .                                  # opens VS Code with Remote-WSL
```

In VS Code, if the dev container isn't already running:
- `Ctrl-Shift-P` → "Dev Containers: Reopen in Container"
- ~10 seconds (cached) and you're inside

In the integrated terminal (which is now inside the container):

```bash
uv run pytest                           # confirm tests pass before you change anything
```

Green? You're set. Red? You have your first task — figure out what changed on `main` while you were away.

### 8.2 — The feature loop (most common)

You want to add a new command to the bot.

```bash
# branch off main
git checkout -b feature/leaderboard-command

# edit src/bot/commands/leaderboard.py
# write a test in tests/test_leaderboard.py

uv run pytest tests/test_leaderboard.py -v
# iterate until green

uv run ruff check
uv run ruff format

git add src/bot/commands/leaderboard.py tests/test_leaderboard.py
git commit -m "add leaderboard command"
git push -u origin feature/leaderboard-command
```

Either:
- Open a PR for review (even if you're solo — the PR description is a free changelog): `gh pr create --fill`
- Or merge directly: `gh pr create --fill && gh pr merge --auto --squash`

When the PR merges to main:
1. GHA `build.yml` builds and pushes a new image (~90s)
2. GHA `deploy.yml` SSHes in and restarts the bot (~10s)
3. Total: ~2 minutes from "merge" to "live"

### 8.3 — Verifying the deploy worked

After merging:

```bash
# from your laptop
ssh myvps "docker compose -f ~/apm-bot/docker-compose.yml logs --tail=20 bot"
```

Or for a live tail while you observe the new behavior:

```bash
ssh myvps "docker compose -f ~/apm-bot/docker-compose.yml logs -f bot"
```

You should see the bot reconnecting to Discord with the new code.

### 8.4 — Adding a new dependency

You want to add `httpx` for an HTTP API call.

```bash
# inside the dev container
uv add httpx
# this updates pyproject.toml and uv.lock
```

VS Code's dev container will detect the change to `pyproject.toml` via the `develop.watch` rule with `action: rebuild`, and rebuild the container automatically. Or force it:

`Ctrl-Shift-P` → "Dev Containers: Rebuild Container"

After rebuild, the new dep is installed. Commit both files:

```bash
git add pyproject.toml uv.lock
git commit -m "add httpx for external API calls"
git push
```

CI rebuilds the prod image with the new dep. Prod gets the dep on next deploy.

**Never commit `pyproject.toml` without `uv.lock`.** The lockfile is what guarantees identical installs across environments. Same for `package-lock.json` (npm), `poetry.lock`, `Cargo.lock`, etc.

### 8.5 — Adding a schema change

This is its own workflow. See [§ 13](#13-database-migrations-without-tears) for the full migration playbook. Short version:

```bash
# 1. Edit your SQLAlchemy models (or equivalent)
# 2. Generate a migration
uv run alembic revision --autogenerate -m "add username column to users"

# 3. READ the generated migration, fix anything autogen got wrong
nano alembic/versions/<new-file>.py

# 4. Test it locally against a fresh DB
docker compose down -v
docker compose up -d postgres
docker compose run --rm migrate
uv run pytest

# 5. Commit + push
git add alembic/versions/<new-file>.py
git commit -m "migration: add username column"
git push
```

CI builds the image (containing the new migration file). The deploy script runs `docker compose run --rm migrate` before restarting the bot. If migration fails, bot stays on old version, you see the error in GHA logs.

### 8.6 — Fixing a bug in production

Scenario: users report the bot is throwing errors on the `!status` command.

**Step 1: Look at prod logs.**

```bash
ssh myvps "docker compose -f ~/apm-bot/docker-compose.yml logs --tail=200 bot | grep -A 10 ERROR"
```

You see a traceback. Note the file and line.

**Step 2: Reproduce locally.**

In the dev container, write a failing test that reproduces the bug:

```python
def test_status_with_no_active_users():
    # the exact condition from the prod traceback
    ...
```

Run: `uv run pytest tests/test_status.py -v`. It fails. Good — you've now captured the bug as a test that will fail again if it ever regresses.

**Step 3: Fix.**

Edit the source, get the test green.

**Step 4: Ship.**

```bash
git checkout -b fix/status-no-users
git add -A
git commit -m "fix: handle empty user list in !status"
git push -u origin fix/status-no-users
gh pr create --fill && gh pr merge --auto --squash
```

~2 minutes later, prod is fixed. Verify with prod logs again.

**Step 5: Decide if it warrants more.**

Most personal bot bugs don't. But if the bug was data-corrupting or affected many users, you'd want to:
- Add monitoring/alerting so you catch it earlier next time
- Write a postmortem (literally just notes for yourself) about what you learned
- Confirm the regression test is in the suite so it can't break again

### 8.7 — Debugging in production (when local repro fails)

Sometimes the bug only happens with prod data shapes. Options in order of preference:

**Easy: snapshot prod, restore locally.**

```bash
# on the VPS
ssh myvps
docker exec infra-postgres-1 pg_dump -U botuser -d botdb > /tmp/snap.sql

# locally (in WSL, on your laptop)
scp myvps:/tmp/snap.sql ./
docker compose down -v
docker compose up -d postgres
sleep 5
docker compose exec -T postgres psql -U botuser -d botdb < snap.sql
# now run the bot locally against prod-shaped data
```

Treat the snapshot file as sensitive — delete it after debugging.

**Harder: shell into the prod container.**

```bash
ssh myvps
cd ~/apm-bot
docker compose exec bot bash
# inside the container, run a Python REPL or one-off scripts
```

Don't make a habit of this — it's tempting to "just edit one file" in prod, which leads to drift between the prod image and the source repo. If you find yourself needing to do anything more than read-only inspection, write a real fix and ship through CI.

**Best: VS Code "Attach to Running Container" via Remote-SSH.**

1. In VS Code: install Remote-SSH extension
2. `Ctrl-Shift-P` → "Remote-SSH: Connect to Host" → `myvps`
3. Inside the SSH'd VS Code: `Ctrl-Shift-P` → "Dev Containers: Attach to Running Container" → pick `apm-bot-bot-1`
4. You now have a full VS Code IDE inside the prod container

Wild and powerful; use it sparingly. Perfect for "I need to read these prod files with syntax highlighting and run an interactive Python session." Wrong for "I need to change a line in prod."

### 8.8 — Working on multiple apps at once

If you have `apm-bot` and `dashboard` both in active dev:

```bash
# WSL terminal 1
cd ~/dev/apm-class-bot
code .                         # opens VS Code window 1

# WSL terminal 2
cd ~/dev/dashboard
code .                         # opens VS Code window 2
```

Each VS Code window runs its own dev container with its own Postgres. To avoid port conflicts, give each app a different host port for Postgres:

```yaml
# apm-class-bot's docker-compose.yml
postgres:
  ports:
    - "5432:5432"

# dashboard's docker-compose.yml
postgres:
  ports:
    - "5433:5432"              # different host port
```

The *inside-container* port stays `5432`, so the apps' `DATABASE_URL` doesn't change. Only the host-side port differs.

### 8.9 — When to nuke vs when to hot-reload

| Change | What to do |
|---|---|
| Edit a `.py` file | Save. Hot reload picks it up (compose `develop.watch`). |
| Add a Python dep (`uv add ...`) | Rebuild dev container. |
| Change Dockerfile | Rebuild dev container. |
| Drop or rename a DB column | Write & run migration via `alembic upgrade head`. |
| DB feels corrupted, fresh slate wanted | `docker compose down -v && docker compose up -d` |
| Dev container seems wedged | "Dev Containers: Rebuild Container Without Cache" |
| Compose file or environment changed | `docker compose down && docker compose up -d` |
| Want to test a "fresh user" scenario | `docker compose down -v` then `alembic upgrade head` |

### 8.10 — Branch strategy for a solo dev

You're one person. You don't need GitFlow.

- `main` is always deployable. Every merge to main goes to prod.
- Short-lived feature/fix branches. Squash-merge into main.
- No long-running `develop` branch. No release branches.
- PR-to-self is fine and recommended (CI runs on PR; you can review your own diff a day later with fresh eyes).

If you ever bring in a collaborator, enable branch protection: Repo settings → Branches → Require PR review.

### 8.11 — When to skip the dev container

For some quick tasks, the dev container is overhead:
- Editing the README
- Tweaking GitHub Actions YAML
- One-line typo fixes

For those, work directly in WSL outside the container. Open VS Code with Remote-WSL and just edit. The dev container is for things that actually involve running code.

### 8.12 — The "is this a code bug or a config bug?" decision tree

When something works locally but breaks in prod (or vice versa):

1. **Diff the env.** Local `.env` vs prod `/home/deploy/<app>/.env`. Different `DATABASE_URL`? Different feature flags? Different `LOG_LEVEL` hiding the error?
2. **Diff the schema.** `docker compose exec postgres psql -U botuser -d botdb -c "\dt"` locally vs the same on prod. A missing migration is the #1 cause of "works on my laptop."
3. **Diff the image.** If you bumped a dependency locally but haven't pushed yet, your image is newer than prod's. `docker compose pull` on prod will fix it.
4. **Diff the data.** Prod data shapes can trigger bugs your test data doesn't. See § 8.7 for snapshot-and-restore.

If it's not one of those, then yeah — it's a code bug. Reproduce, fix, ship.

### 8.13 — A typical week, in shape

| Day | Activity | Time spent |
|---|---|---|
| Mon | Pull, dev container, write feature, test, push, PR, merge | 2-3 hr |
| Tue | Review prod logs, notice a bug, write test, fix, ship | 30 min |
| Wed | Add a new dependency for a new feature, ship | 1-2 hr |
| Thu | Schema change (migration), test thoroughly, ship | 1-2 hr |
| Fri | Refactor / clean up tech debt | 1-2 hr |

The deploy step takes ~2 minutes regardless. Your time is in writing and testing, never in DevOps.

---

## 9. Building images with GitHub Actions → GHCR

### Step 9.1 — What GHCR is, briefly

**GHCR** (GitHub Container Registry, `ghcr.io`) is GitHub's Docker image storage. Images live alongside your repo (visible in the "Packages" section). For personal repos, GHCR is free with generous limits and integrates seamlessly with GitHub Actions — no separate API key to set up.

### Step 9.2 — The build workflow

Create `.github/workflows/build.yml`:

```yaml
name: Build and push image

on:
  push:
    branches: [main]
  workflow_dispatch:        # allows manual triggering from the GitHub UI

jobs:
  build:
    runs-on: ubuntu-latest
    permissions:
      contents: read        # to checkout the repo
      packages: write       # to push to GHCR

    steps:
      - name: Checkout code
        uses: actions/checkout@v4

      - name: Set up Docker Buildx
        uses: docker/setup-buildx-action@v3

      - name: Log in to GHCR
        uses: docker/login-action@v3
        with:
          registry: ghcr.io
          username: ${{ github.actor }}
          password: ${{ secrets.GITHUB_TOKEN }}

      - name: Extract metadata
        id: meta
        uses: docker/metadata-action@v5
        with:
          images: ghcr.io/${{ github.repository }}
          tags: |
            type=raw,value=latest,enable={{is_default_branch}}
            type=sha,prefix=sha-
            type=ref,event=branch

      - name: Build and push
        uses: docker/build-push-action@v5
        with:
          context: .
          target: runtime           # build only the runtime stage
          push: true
          tags: ${{ steps.meta.outputs.tags }}
          labels: ${{ steps.meta.outputs.labels }}
          cache-from: type=gha
          cache-to: type=gha,mode=max
```

### Step 9.3 — What each piece does

**`on: push: branches: [main]`** — runs every push to main. Add `workflow_dispatch` so you can also run it manually from the Actions tab (useful for re-running a build that failed for transient reasons).

**`permissions: packages: write`** — *the* gotcha. By default, the auto-generated `GITHUB_TOKEN` is read-only. This line is what allows pushing to GHCR. Without it, you'll get a confusing "denied" error.

**`docker/setup-buildx-action`** — enables Buildx, Docker's modern builder, which gives you better caching (`type=gha`), multi-platform builds, and BuildKit features.

**`docker/login-action`** — authenticates to GHCR using the temporary `GITHUB_TOKEN` that GitHub Actions generates for each workflow run.

**`docker/metadata-action`** — computes tags automatically. You get:
- `:latest` on the default branch
- `:sha-abc123` for every commit (the immutable handle for rollbacks)
- `:<branch-name>` for non-main branch builds

**`docker/build-push-action`** — runs `docker buildx build` + `docker push`. The `target: runtime` line tells it to build only the runtime stage of your multi-stage Dockerfile (skipping the heavier dev stage).

**`cache-from`/`cache-to`** — caches Docker layers in GitHub Actions storage. First build is ~60s; subsequent rebuilds drop to ~15s if only code changed.

### Step 9.4 — First run

Commit and push:

```bash
git add .github/workflows/build.yml Dockerfile
git commit -m "ci: add build workflow"
git push origin main
```

Watch the Actions tab on GitHub. First run takes ~2-3 minutes (Buildx setup, no cache yet). When it goes green, visit your repo's Packages sidebar — you'll see `apm-class-bot` listed.

### Step 9.5 — Image visibility

By default, GHCR images created by Actions are **private**. For most personal projects, leave them private. If you ever want to make them public:

1. Visit the package page (`github.com/users/<you>/packages/container/apm-class-bot`)
2. Package settings → Change visibility → Public

For a Discord bot, keep it private.

### Step 9.6 — Pulling from the VPS

The VPS needs to authenticate to GHCR to pull private images. Generate a **Personal Access Token (PAT)** with **`read:packages`** scope only:

1. github.com/settings/tokens → "Generate new token (classic)"
2. Scope: only check `read:packages`
3. Set expiration to whatever your tolerance is (1 year is reasonable; renew on calendar reminder)
4. Copy the token

On the VPS, as `deploy`:

```bash
echo "<the-PAT>" | docker login ghcr.io -u <your-gh-username> --password-stdin
```

Docker stores this in `/home/deploy/.docker/config.json`. From now on, `docker pull ghcr.io/...` works for any image you own.

---

## 10. Deploying to the VPS (continuous delivery)

Now to close the loop: when CI finishes building the image, automatically SSH into the VPS and restart the container.

### Step 10.1 — The deploy workflow

Create `.github/workflows/deploy.yml`:

```yaml
name: Deploy to VPS

on:
  workflow_run:
    workflows: ["Build and push image"]
    types: [completed]
    branches: [main]

jobs:
  deploy:
    runs-on: ubuntu-latest
    if: ${{ github.event.workflow_run.conclusion == 'success' }}

    steps:
      - name: Deploy via SSH
        uses: appleboy/ssh-action@v1
        with:
          host: ${{ secrets.VPS_HOST }}
          username: deploy
          key: ${{ secrets.VPS_SSH_KEY }}
          script: |
            cd ~/apm-bot
            docker compose pull
            docker compose run --rm migrate    # see § 13
            docker compose up -d bot
            docker image prune -f
```

### Step 10.2 — Configure the GitHub secrets

In your repo settings: Settings → Secrets and variables → Actions → New repository secret. Add:

| Secret name | Value |
|---|---|
| `VPS_HOST` | Your VPS's IP or hostname |
| `VPS_SSH_KEY` | The **private** half of the deploy keypair you generated in [§ 3.10](#step-310--generate-the-ci-deploy-key). Paste the entire contents of `~/.ssh/vps-deploy`, including the `-----BEGIN OPENSSH PRIVATE KEY-----` and `-----END OPENSSH PRIVATE KEY-----` lines. |

**Why a `workflow_run` trigger instead of `on: push`?** This makes deploy depend on a successful build. If the image fails to build, deploy never runs. If the build is green but you want to skip the deploy (rare), you can disable the deploy workflow temporarily.

**Alternative trigger pattern:** Some teams put build + deploy in one workflow with sequential jobs (`needs: build`). That's also fine. Two workflows is slightly cleaner for log-reading; one workflow is slightly faster.

### Step 10.3 — The VPS-side compose file

On the VPS, create `/home/deploy/apm-bot/docker-compose.yml`:

```yaml
networks:
  shared:
    external: true

services:
  bot:
    image: ghcr.io/<your-gh-username>/apm-class-bot:latest
    restart: unless-stopped
    env_file: .env
    networks:
      - shared
    logging:
      driver: json-file
      options:
        max-size: "10m"
        max-file: "3"

  migrate:
    image: ghcr.io/<your-gh-username>/apm-class-bot:latest
    profiles: ["migrate"]
    env_file: .env
    networks:
      - shared
    command: uv run alembic upgrade head
```

And `/home/deploy/apm-bot/.env`:

```
DISCORD_TOKEN=<production-bot-token>
DATABASE_URL=postgresql://botuser:<the-real-prod-password>@postgres:5432/botdb
LOG_LEVEL=INFO
```

**Critical:** the production `DISCORD_TOKEN` should be from a **separate Discord application** than your dev token. Bots can only be connected to Discord from one place at a time; if dev and prod use the same token, they'll fight.

**Why the `logging` block?** By default, Docker stores container logs as a single growing JSON file that never rotates. On a long-running container, this can fill your disk. The `max-size: "10m"` and `max-file: "3"` rotation caps each container's log usage at 30 MB.

### Step 10.4 — First manual deploy (to make sure it works)

On the VPS as `deploy`:

```bash
cd ~/apm-bot
docker compose pull
docker compose run --rm migrate    # may be a no-op if no migrations exist yet
docker compose up -d bot
docker compose logs -f bot
```

If the bot connects to Discord and stays alive, you're good. Ctrl-C the logs (the container keeps running).

### Step 10.5 — End-to-end test

On your laptop:

```bash
# make a trivial code change (e.g., add a comment to bot/main.py)
git commit -am "test deploy pipeline"
git push origin main
```

Watch:
1. GitHub Actions → "Build and push image" → green (~90 seconds)
2. GitHub Actions → "Deploy to VPS" → green (~10 seconds)
3. SSH into VPS: `docker compose -f ~/apm-bot/docker-compose.yml logs --tail=20 bot`

The new image is running.

### Step 10.6 — Rollback procedure

A bad deploy can be reverted to the previous SHA-tagged image:

```bash
# on the VPS
cd ~/apm-bot
# edit docker-compose.yml — change `:latest` to `:sha-abc123` (the prior known-good SHA)
docker compose pull
docker compose up -d
```

This is why CI tags every build with `:sha-<commit>`, not just `:latest`. The SHA tags are immutable; you can always go back.

**Bonus:** for fully reversible deploys, you could pin compose to `:sha-${COMMIT_SHA}` and have the deploy script set the env var. For a personal bot, manual editing on rollback is fine.

---

## 11. Adding a second (or fifth) app

This is where the architecture pays off. The marginal cost of app N+1 is ~10 minutes.

### Step 11.1 — The checklist

For a new app called `dashboard`:

1. **Create the repo** with the same structure (`Dockerfile`, `.devcontainer/`, `.github/workflows/`, `docker-compose.yml`, `.env.example`). Copy them from your existing app, search-and-replace the name.
2. **Add `VPS_HOST` and `VPS_SSH_KEY` secrets** to the new repo (same values as the first repo).
3. **Create the database** on the VPS (see [§ 4.7](#47--database-users-the-per-app-pattern)):
   ```bash
   ssh myvps
   sudo -iu deploy
   cd ~/infra && docker compose exec postgres psql -U postgres
   ```
   ```sql
   CREATE USER dashuser WITH PASSWORD '<random>';
   CREATE DATABASE dashdb OWNER dashuser;
   ```
4. **Create the VPS directory**:
   ```bash
   mkdir ~/dashboard
   # populate ~/dashboard/docker-compose.yml (point at ghcr.io/.../dashboard:latest)
   # populate ~/dashboard/.env (DATABASE_URL=postgresql://dashuser:.../dashdb)
   ```
5. **Push to main.** CI builds, deploys, app comes up. The new container joins the `shared` network and can reach `postgres` by hostname.

### Step 11.2 — What stays the same vs. what's different per app

**Same across all apps:**
- The shape of the Dockerfile (multi-stage, base/dev/runtime)
- The shape of `.devcontainer/devcontainer.json`
- The shape of the GHA workflows (just `image:` name differs)
- The directory structure on the VPS (`~/<app-name>/`)
- The shared `postgres` hostname in connection strings

**Different per app:**
- Database name and user
- Discord token (if it's another Discord bot)
- Forwarded ports (if it's a web app)
- The `cd ~/<app-name>` line in the deploy workflow

### Step 11.3 — Sharing common config across repos

If you start running 3+ apps, you'll feel the duplication. Options:

- **Template repo.** Make one of your repos a GitHub template. New apps start as a fork-with-history of it.
- **Reusable workflows.** GitHub Actions supports `workflow_call` so multiple repos invoke a single shared workflow file in an "infra" repo. Worthwhile around 5+ apps; overkill before.
- **Cookiecutter / scaffold script.** A `new-app.sh` that prompts for a name and stamps out the directory.

Don't optimize for this until you feel the pain. Premature DRY is harder to undo than copy-paste.

---

## 12. Reverse proxy with Caddy (HTTPS for web apps)

Discord bots don't need inbound HTTP, but the moment you build something with a web UI (dashboard, REST API, etc.), you need:
- TLS certificates
- Routing different domains to different containers
- Port 80/443 exposed

**Caddy** does all of this with the simplest config in the game. Auto-fetches Let's Encrypt certs, auto-renews, just-works HTTPS.

### Step 12.1 — Add Caddy to the infra stack

Edit `/home/deploy/infra/docker-compose.yml`:

```yaml
networks:
  shared:
    external: true

services:
  postgres:
    # ... (existing config)

  caddy:
    image: caddy:2
    restart: unless-stopped
    ports:
      - "80:80"
      - "443:443"
      - "443:443/udp"        # HTTP/3
    volumes:
      - ./Caddyfile:/etc/caddy/Caddyfile:ro
      - caddy_data:/data
      - caddy_config:/config
    networks:
      - shared

volumes:
  postgres_data:
  caddy_data:
  caddy_config:
```

### Step 12.2 — The Caddyfile

`/home/deploy/infra/Caddyfile`:

```
dashboard.yourdomain.com {
    reverse_proxy dashboard:3000
}

api.yourdomain.com {
    reverse_proxy api-service:8080
}
```

That's the entire HTTPS-and-routing config. Caddy:
- Solicits a Let's Encrypt cert for each hostname automatically
- Renews certs in the background (~30 days before expiry)
- Reverse-proxies requests to the named container on the shared network

**Why hostname `dashboard:3000` and not `localhost:3000`?** Because Caddy is a container itself — `localhost` would mean Caddy's own loopback. The shared network's DNS resolves `dashboard` to the dashboard container's IP.

### Step 12.3 — Open the firewall

```bash
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
```

### Step 12.4 — Point DNS

Add A records at your DNS provider:

```
dashboard.yourdomain.com → <vps-ip>
api.yourdomain.com → <vps-ip>
```

### Step 12.5 — Restart infra

```bash
cd ~/infra
docker compose up -d
docker compose logs -f caddy
```

Within ~10 seconds of the first DNS resolution, Caddy fetches certs and serves HTTPS. Visit `https://dashboard.yourdomain.com` — you'll see the dashboard container's response with a valid cert.

### Step 12.6 — Per-app compose: no exposed ports

Apps proxied by Caddy do **not** need `ports:` in their compose file. Caddy reaches them over the shared network. Skip `ports:` entirely; the container only listens on the shared network, never on the host's public IP. This is the same defense-in-depth pattern as Postgres in [§ 5.3](#step-53--the-infra-compose-file).

---

## 13. Database migrations without tears

Migrations are the part of this stack where the abstractions stop helping. Container or no container, schema change is the highest-blast-radius operation. Treat with care.

This section uses **Alembic** (the standard for Python/SQLAlchemy). The principles apply to any migration tool — Prisma, Drizzle, Knex, golang-migrate.

### 13.1 — Why migrations are different

For most code changes, "deploy" means "replace the image." If the new image is broken, you redeploy the old one. Reversible in seconds.

Schema changes are different:
- The database is **stateful**. The schema change happens once and stays.
- A bad migration can **corrupt data**. Rollback might be impossible without a backup.
- The new code and the new schema must arrive **together**, or one of them sees something it doesn't expect.

The discipline: treat migrations like a separate kind of deploy, with their own playbook.

### 13.2 — Setting up Alembic from scratch

Inside the dev container, once:

```bash
uv add alembic sqlalchemy psycopg2-binary
uv run alembic init alembic
```

This creates:
- `alembic.ini` — config file
- `alembic/` directory with `env.py`, `script.py.mako`, and a `versions/` folder

Commit all of it to the repo.

### 13.3 — Wire Alembic to your DATABASE_URL

Edit `alembic.ini`. Find this line:

```ini
sqlalchemy.url = driver://user:pass@localhost/dbname
```

Comment it out or leave it blank. We'll set the URL from the environment instead.

Edit `alembic/env.py`. Near the top:

```python
import os
from sqlalchemy import create_engine

# Override the URL from environment — keeps secrets out of alembic.ini
config.set_main_option("sqlalchemy.url", os.environ["DATABASE_URL"])
```

If you have SQLAlchemy models, also import them so autogenerate can detect schema changes:

```python
from bot.db.models import Base
target_metadata = Base.metadata
```

**Why drive Alembic from the env var?** So Alembic uses the same `DATABASE_URL` your app uses. No duplicate config, no risk of pointing migrations at the wrong DB.

### 13.4 — The migration compose service

Already shown in [§ 6.5](#step-65--the-local-dev-docker-composeyml-committed) (local) and [§ 10.3](#step-103--the-vps-side-compose-file) (prod). The key idea:

```yaml
migrate:
  image: ghcr.io/<you>/apm-class-bot:latest     # or `build: .` locally
  profiles: ["migrate"]                          # excluded from `compose up`
  env_file: .env
  networks: [shared]                             # prod only
  command: uv run alembic upgrade head
```

The `profiles: ["migrate"]` block is critical — services with profiles are **excluded** from `docker compose up` unless explicitly invoked. So `migrate` never runs by accident.

To invoke:

```bash
docker compose run --rm migrate
```

`run --rm` runs once and deletes the container after exit, leaving no detritus.

### 13.5 — Wire migrations into the deploy pipeline

Update `.github/workflows/deploy.yml`:

```yaml
script: |
  cd ~/apm-bot
  docker compose pull
  docker compose run --rm migrate           # exits 0 or fails loudly
  docker compose up -d bot
  docker image prune -f
```

If the migration fails, you see the traceback in the GitHub Actions UI. The bot keeps running on the old version. Fix the migration, push, retry.

**Why migrate before `up -d` instead of inside the bot's entrypoint?**
- **Visibility:** you see the migration result in CI logs, not buried in container logs.
- **Failure mode:** bot stays on the old version if migration fails (vs. bot fails to start at all and you're debugging a container that exits in 2 seconds).
- **Idempotency:** `alembic upgrade head` is a no-op if no migrations are pending, so it's safe to run every deploy. No conditional logic needed.

### 13.6 — Writing your first migration

Inside the dev container:

```bash
uv run alembic revision --autogenerate -m "add user table"
```

This creates a file like `alembic/versions/abc123_add_user_table.py`:

```python
"""add user table

Revision ID: abc123def456
Revises:
Create Date: 2026-05-24 12:34:56.789

"""
from alembic import op
import sqlalchemy as sa

revision = "abc123def456"
down_revision = None

def upgrade():
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("discord_id", sa.BigInteger(), nullable=False, unique=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    )

def downgrade():
    op.drop_table("users")
```

**Critical: read the generated migration before committing.** Autogenerate is good but not perfect. It sometimes:
- Misses column type changes (especially for custom types or enums)
- Generates the wrong order for related operations
- Produces an unsafe `downgrade()` (e.g., one that throws away data)

Treat autogen output as a *starting draft*, not a finished migration.

### 13.7 — Testing the migration locally

Always test against a **fresh** DB before pushing:

```bash
# nuke the local DB volume
docker compose down -v

# bring up just postgres
docker compose up -d postgres

# wait for it to be healthy (the compose healthcheck handles this if you `depends_on`)

# apply all migrations from scratch
docker compose run --rm migrate

# inspect the schema
docker compose exec postgres psql -U botuser -d botdb -c "\dt"
docker compose exec postgres psql -U botuser -d botdb -c "\d users"

# run your tests
uv run pytest
```

If the migration applies cleanly from empty to head and tests pass, it's safe to push.

### 13.8 — Testing against a prod-shaped DB (for risky migrations)

When a migration touches existing data (e.g., dropping a column, changing a column type), test against actual production data shapes:

```bash
# on the VPS
docker exec infra-postgres-1 pg_dump -U botuser -d botdb > /tmp/prodsnap.sql

# locally
scp myvps:/tmp/prodsnap.sql ./
docker compose down -v
docker compose up -d postgres
sleep 5
docker compose exec -T postgres psql -U botuser -d botdb < prodsnap.sql

# now apply the new migration against real-shaped data
docker compose run --rm migrate
```

If this surfaces a problem (e.g., a column has unexpected nulls), you caught it before prod.

**On PII:** if your prod data contains user data and you're storing snapshots on your laptop, treat that file with care. Delete it after debugging. Don't commit it. Don't email it.

### 13.9 — The expand/contract pattern for destructive changes

Bad: a single migration that drops a column other code is still using.

Better: split into multiple deploys.

**Step 1 (expand):** Add the new column (or new table). Update code to *write* to both old and new, *read* from old.

```python
# migration 001
def upgrade():
    op.add_column("users", sa.Column("username", sa.String(50)))
```

Deploy. Bot now writes to both `name` and `username` going forward.

**Step 2 (backfill):** A migration (or one-shot script) copies old → new for existing rows.

```python
# migration 002
def upgrade():
    op.execute("UPDATE users SET username = name WHERE username IS NULL")
```

Deploy. All rows now have `username` populated.

**Step 3 (switch reads):** Update code to read from `username`, still write to both.

Deploy.

**Step 4 (contract):** Stop writing to old column. Once you're sure nothing reads it, drop it.

```python
# migration 003
def upgrade():
    op.drop_column("users", "name")
```

Deploy.

This pattern feels overkill for a personal bot — and often it is. But the moment you have data you care about, this is the discipline. The alternative is a deploy that fails partway through schema + code change, with nothing to roll back to.

### 13.10 — Always back up before destructive migrations

Even with expand/contract, take a snapshot immediately before deploying a destructive migration:

```bash
# on the VPS
docker exec infra-postgres-1 pg_dump -U botuser -d botdb \
  | gzip > ~/backups/botdb-pre-migration-$(date +%Y%m%d-%H%M%S).sql.gz
```

To restore later if it goes badly:

```bash
gunzip < ~/backups/botdb-pre-migration-20260524-103000.sql.gz \
  | docker exec -i infra-postgres-1 psql -U botuser -d botdb
```

### 13.11 — When a migration fails in production

It will happen eventually. Some recipes:

**Migration failed cleanly, you see the error in CI logs:**
- Don't panic — the bot is still on the old image, the old schema.
- Look at what state Alembic thinks it's in:
  ```bash
  ssh myvps "docker compose -f ~/apm-bot/docker-compose.yml run --rm migrate alembic current"
  ```
- Fix the migration locally, test against the prod snapshot (§ 13.8), push.

**Migration partially applied (e.g., an `ADD COLUMN` succeeded but a subsequent `UPDATE` failed):**
- The bot is still on the old image, but the schema is now mid-state.
- Two options:
  1. Push a corrective migration that handles the partial state.
  2. Manually fix the DB and update Alembic's bookkeeping:
     ```bash
     docker exec -it infra-postgres-1 psql -U botuser -d botdb
     -- manually apply the operations the migration didn't finish
     UPDATE alembic_version SET version_num = '<the-revision-id>';
     ```
- The manual fix is sketchy but sometimes necessary. Take a backup first.

**Migration succeeded but the new app code is broken:**
- Roll back the *image* to the prior SHA tag (see [§ 10.6](#step-106--rollback-procedure)).
- The schema is forward-compatible (it should be — that's why we expand/contract). Old code reading new schema is fine if the migration was additive.

**Migration applied a destructive change you can't undo:**
- Restore from the pre-migration backup (§ 13.10).
- This is why we always take one before destructive changes.

### 13.12 — Reviewing the autogenerated migration: checklist

Before committing a generated migration, eyeball it for:

- [ ] **Did it pick up all the changes?** Compare your model changes vs. the migration operations.
- [ ] **Is the `downgrade()` function usable?** Autogenerate may produce one that throws away data; rewrite if so or remove and document why.
- [ ] **Any `op.drop_*` calls?** These are destructive — confirm they're intentional and you're doing expand/contract for anything risky.
- [ ] **Any column type changes?** Postgres can't always cast in place; you may need an explicit `USING` clause:
  ```python
  op.alter_column("users", "id", type_=sa.BigInteger(), postgresql_using="id::bigint")
  ```
- [ ] **Indexes on big tables?** Adding an index on a multi-million-row table can lock the table for minutes. Consider `CONCURRENTLY` (Postgres):
  ```python
  op.create_index('idx_users_discord_id', 'users', ['discord_id'], postgresql_concurrently=True)
  ```
  Caveat: `CONCURRENTLY` can't run inside a transaction; you may need to split it into its own migration with `autocommit_block`.
- [ ] **Foreign keys on existing tables?** Adding a FK re-validates every row. Slow on big tables.
- [ ] **NOT NULL constraints on existing columns?** Will fail if any existing row has NULL. Do it in two steps: backfill first, then add the constraint.

### 13.13 — Common Alembic pitfalls

- **`target_metadata` not set.** Autogenerate produces empty migrations because Alembic doesn't know your models. Import your `Base` in `env.py`.
- **Multiple heads.** If two branches each add a migration off the same parent, you end up with branching history when both merge. Resolve with `alembic merge -m "merge branches" abc123 def456`.
- **Running `alembic upgrade` outside the container.** Don't. The host's Python/SQLAlchemy versions may not match the container's. Always run via `docker compose run --rm migrate` or `docker compose exec bot uv run alembic ...`.
- **Editing applied migrations.** Once a migration has been applied to *any* database (yours, prod, anyone's), don't edit it. Create a new migration that adjusts the change instead. Editing breaks Alembic's history tracking.
- **Forgetting to commit `alembic.ini` or `alembic/`.** They're not gitignored by default, but double-check.

### 13.14 — Squashing migrations (advanced)

After a year of development, you may have 50+ migration files. They take longer to apply on a fresh DB and clutter your repo.

Periodically (annually, before major releases):

1. Bring up a fresh DB and apply all migrations.
2. Dump the schema (not the data): `pg_dump --schema-only`.
3. Create a new "baseline" migration with the dumped schema.
4. Delete the old migration files.
5. Mark the baseline as applied in any existing databases (`alembic_version` table).

This is invasive and easy to mess up — only do it when the migration count actually hurts you. For a personal bot, you probably never need to.

### 13.15 — A safe migration playbook (the 11pm checklist)

Before any non-trivial migration deploy:

1. ☐ Migration is reviewed line-by-line (not just trusted from autogen)
2. ☐ Tested locally against a fresh DB
3. ☐ Tested locally against a snapshot of prod data
4. ☐ Pre-deploy backup taken on the VPS
5. ☐ Migration is forward-compatible with the previous app version (expand/contract pattern if destructive)
6. ☐ You have time to babysit the deploy (don't ship at 4:55pm Friday)
7. ☐ You can SSH into the VPS quickly if something goes wrong

If you can check all seven, push. Otherwise, wait until you can.

---

## 14. Backups, monitoring, and rollbacks

### Step 14.1 — Database backups

A nightly cron that `pg_dumpall`s and stores offsite. As `julian` (or root):

```bash
sudo nano /etc/cron.d/pg-backup
```

```cron
0 3 * * * deploy /home/deploy/scripts/backup-db.sh
```

Create `/home/deploy/scripts/backup-db.sh`:

```bash
#!/usr/bin/env bash
set -euo pipefail

BACKUP_DIR=/home/deploy/backups
mkdir -p "$BACKUP_DIR"

TIMESTAMP=$(date +%Y%m%d-%H%M%S)
FILE="$BACKUP_DIR/pgdump-$TIMESTAMP.sql.gz"

docker exec infra-postgres-1 pg_dumpall -U postgres | gzip > "$FILE"

# Keep last 14 days locally
find "$BACKUP_DIR" -name 'pgdump-*.sql.gz' -mtime +14 -delete

# Optional: rsync offsite
# rsync "$FILE" backup-server:~/pgdumps/
```

Make executable: `chmod +x /home/deploy/scripts/backup-db.sh`.

**Offsite storage:** Backblaze B2 ($0.005/GB/month) is the cheapest credible option. `rclone` syncs the local backup dir to B2. Don't trust a backup that lives on the same machine as the database — disk failure kills both.

### Step 14.2 — Container log monitoring

Default Docker logs are searchable but ephemeral. For a personal box, that's fine. If you want more:

- **Lazy option:** `docker logs --since 1h <container>` from SSH when something seems off.
- **Better:** `dozzle` — a single-container web UI for live-tailing all your container logs. Add it to the infra stack, point Caddy at it on `logs.yourdomain.com`.
- **Serious:** Loki + Grafana. Overkill for personal use.

### Step 14.3 — Health checks and alerting

For a Discord bot, the simplest check is "does the bot's presence show as online in your test server?" If you want active alerting:

- **Uptime Kuma** — self-hosted uptime monitor, runs as another container in `infra/`. Notifies Discord/Slack/email when something stops responding.
- **Healthcheck.io** — external service that expects a periodic "I'm alive" ping from your bot. If the ping stops, you get notified. Free tier handles a personal bot fine.

Don't set up alerting before you have something to alert on. A bot with no users doesn't need 24/7 monitoring.

### Step 14.4 — Disk space

Docker's number-one way to ruin your week is filling the disk with unused images, volumes, and build cache. Once a week:

```bash
docker system df          # see what's using space
docker system prune -af   # aggressively clean up unused everything
docker volume prune       # be careful — this won't delete in-use volumes
```

Add a weekly cron if you don't want to remember.

### Step 14.5 — Rollback

See [§ 10.6](#step-106--rollback-procedure). The short version: every commit produces an image tagged `:sha-<commit>`. Edit the compose file to pin to the prior SHA, `docker compose pull && up -d`. Done in 30 seconds.

For database-level rollback (a bad migration that corrupted data): restore from the most recent `pg_dump` (§ 14.1).

---

## 15. Troubleshooting

### "Permission denied (publickey)" when SSHing

Causes:
- `~/.ssh/id_ed25519` has wrong permissions (must be 600). Fix: `chmod 600 ~/.ssh/id_ed25519`.
- Public key wasn't installed correctly. On VPS: `cat ~/.ssh/authorized_keys` and confirm your key is there.
- `sshd_config` disabled key auth. `sudo grep PubkeyAuthentication /etc/ssh/sshd_config` should be `yes`.

### `docker compose` says "permission denied" running docker commands

You're not in the docker group, or you haven't logged out/in since being added.

```bash
groups   # confirm 'docker' is listed
# if not:
sudo usermod -aG docker $USER
# log out completely and back in
```

### GHA workflow fails with "denied: installation not allowed to Write organization package"

The `permissions: packages: write` block is missing from the workflow file. See [§ 9.2](#step-92--the-build-workflow).

### Container can't reach `postgres` hostname

The container isn't on the `shared` network, or the network doesn't exist.

```bash
docker network ls | grep shared           # confirm network exists
docker inspect <container> | grep -A 5 Networks   # confirm container is attached
```

Fix: ensure the app's `docker-compose.yml` has the `networks:` block with `shared: external: true` and the service lists `shared` under its own `networks:`.

### `ssh-add -L` inside dev container shows nothing

VS Code's SSH agent forwarding isn't working. Common causes:

- `keychain` (or whatever started the agent in WSL) isn't running. Confirm `echo $SSH_AUTH_SOCK` returns a path in WSL before launching VS Code.
- You launched VS Code before adding keys. Quit VS Code completely (`taskkill /F /IM Code.exe`), confirm keys are loaded in WSL, then reopen.

### Bot can connect to Discord but database queries hang

Postgres healthcheck wasn't satisfied before the bot started; the bot connected to a Postgres that isn't ready. Restart with `docker compose down && docker compose up -d` and ensure `depends_on.postgres.condition: service_healthy` is set.

### "image not found" on VPS when pulling

VPS isn't logged into GHCR, or the PAT expired.

```bash
docker login ghcr.io -u <username>
# enter the PAT (read:packages scope) as password
```

### CI builds an image but it's huge

Likely culprits:
- No `.dockerignore`, so `.git`, `node_modules`, `__pycache__` are all in the image.
- Only one stage (no multi-stage). Move dev tooling out of `runtime`.
- Apt packages installed without `--no-install-recommends` and `rm -rf /var/lib/apt/lists/*`.

Use `docker history <image>` to see which layers are large.

### "Cannot start service postgres" after a Postgres major-version bump

You upgraded `postgres:16` → `postgres:17` (or used `:latest`) without doing a dump/restore. Postgres major versions are incompatible at the data file level. Recovery:

1. Revert to `postgres:16` in compose, restart.
2. `docker exec ... pg_dumpall > dump.sql`.
3. Stop Postgres, rename the volume.
4. Bring up `postgres:17` (fresh volume), restore from dump.

Or just don't upgrade major versions without planning a migration window. Pin `postgres:16` and revisit yearly.

### Migration says "Can't locate revision" or "Multiple heads"

- **"Can't locate revision":** Alembic's `versions/` directory doesn't have the file referenced in the DB's `alembic_version` table. Either an alembic version file was deleted, or you're running against the wrong DB. Check `alembic_version`:
  ```sql
  SELECT version_num FROM alembic_version;
  ```
  If it references a deleted migration, you've drifted. Either restore the deleted file or manually update `alembic_version` to a real revision (after careful thought).

- **"Multiple heads":** Two migrations branch from the same parent. Run `alembic heads` to see them, then `alembic merge -m "merge branches" <rev1> <rev2>` to create a merge revision.

### Alembic autogenerate produces an empty migration

You didn't set `target_metadata` in `env.py`, or you didn't import your models so SQLAlchemy doesn't know about them. See [§ 13.3](#133--wire-alembic-to-your-database_url).

---

## 16. Alternatives considered

### Hosting choices we rejected (and when to reconsider)

**Fly.io / Railway / Render**
- *Why not:* Per-app monthly cost adds up; learning the abstraction is non-portable.
- *When to reconsider:* You're hosting only 1-2 apps, you don't want to learn ops, and your time is worth more than the $5-20/month/app these services cost past their free tiers.

**Kubernetes (k3s, k0s, single-node)**
- *Why not:* The complexity tax is enormous and the payoff is multi-node orchestration you don't need.
- *When to reconsider:* You actually have ≥3 nodes, real HA requirements, or you're learning K8s as a skill.

**Coolify, Dokploy, CapRover (self-hosted PaaS)**
- *Why not for this guide:* Hides the docker/compose layer we explicitly want you to understand. Migrations and debugging require breaking through the abstraction.
- *When to reconsider:* You've internalized the docker-compose flow, you're running 5+ apps, and the GUI ergonomics are worth the trade.

**systemd + Python venv (no Docker)**
- *Why not:* Loses "same image in dev and prod" — you maintain a venv on the VPS separate from your dev environment, and toolchain drift accumulates.
- *When to reconsider:* You have an app with very heavy native dependencies that don't containerize well. Rare.

### Image registry choices

**GHCR** (this guide)
- Free for personal repos
- Auth integrated with GitHub Actions
- Lives next to the code

**Docker Hub**
- Free public, stingy on private
- Higher trust ceiling (rate-limiting unauthed pulls)

**Self-hosted (Harbor, Distribution)**
- More control, more ops burden
- Only worth it if you're scaling beyond personal projects

### CI/CD choices

**GitHub Actions** (this guide)
- Free for personal repos, integrates with GHCR for free
- YAML-heavy, but well-documented

**GitLab CI**
- Equivalent capability; pick if you're already on GitLab

**Drone, Woodpecker, Jenkins**
- Self-hosted CI; more work to set up and maintain

### Dev environment choices

**Dev Containers** (this guide)
- Same image as production = zero drift
- Initial container build cost: ~1 minute

**Local Python venv (no container)**
- Fastest iteration on micro-changes
- Risks: toolchain drift, OS-specific bugs

**Nix / devbox / mise**
- Reproducible without containers
- Steeper learning curve, less universally understood

### SSH agent choices

**keychain + WSL ssh-agent** (this guide, free option)
- Pure bash, no extra services
- Survives terminal close/reopen
- Doesn't survive WSL shutdown (re-enter passphrase once per session)

**1Password SSH Agent**
- Biometric per-use auth, syncs across devices
- Costs $$/month
- Best UX bar none

**Windows OpenSSH agent + npiperelay**
- Single agent shared with Windows
- Janky setup with multiple bridge tools

**No agent, type passphrase each time**
- Not recommended; you'll disable the passphrase out of frustration

### Migration tool choices

**Alembic** (this guide)
- The standard for Python/SQLAlchemy
- Powerful, well-documented, extensive autogenerate support
- Can be cryptic when something goes wrong

**Yoyo migrations**
- Simpler Python migration tool, no SQLAlchemy required
- Good if you're using raw SQL or a different ORM

**Flyway, Liquibase** (Java ecosystem, but language-agnostic)
- Database-first, schema-as-SQL approach
- More common in enterprise; overkill for personal

**Hand-written SQL files + a version table**
- Maximum control, no abstraction
- Reinventing Alembic poorly

---

## 17. Quick reference (cheat sheet)

### On your laptop (WSL)

```bash
# SSH to VPS as admin user
ssh myvps

# SSH to VPS as deploy user (for CI debugging)
ssh myvps-deploy

# View running containers on VPS without logging in
ssh myvps "docker ps"

# Tail logs of a specific app
ssh myvps "docker compose -f ~/apm-bot/docker-compose.yml logs -f --tail=50 bot"

# Snapshot prod DB and pull locally
ssh myvps "docker exec infra-postgres-1 pg_dump -U botuser -d botdb" > snap.sql
docker compose down -v && docker compose up -d postgres
docker compose exec -T postgres psql -U botuser -d botdb < snap.sql
```

### On the VPS (as `deploy`)

```bash
# bring up all of infra
cd ~/infra && docker compose up -d

# bring up an app
cd ~/<app-name> && docker compose up -d

# bring down an app (stops without deleting)
cd ~/<app-name> && docker compose stop

# pull latest image for an app and restart
cd ~/<app-name> && docker compose pull && docker compose up -d

# run a migration manually (e.g., before a known-risky deploy)
cd ~/<app-name> && docker compose run --rm migrate

# get a psql shell on the shared postgres
docker compose -f ~/infra/docker-compose.yml exec postgres psql -U postgres

# follow logs for an app
dlogs                                                # alias for docker compose logs -f --tail=100
dlogs bot                                            # just the bot service

# exec into a running container
dexec bot bash                                       # alias for docker compose exec

# free up disk
docker system prune -af
```

### Inside the dev container (VS Code terminal)

```bash
# run the app
uv run python -m bot.main

# tests
uv run pytest
uv run pytest tests/test_specific.py -v

# lint and format
uv run ruff check
uv run ruff format

# add a dependency
uv add httpx

# remove a dependency
uv remove httpx

# create a migration
uv run alembic revision --autogenerate -m "add username column"

# apply migrations
uv run alembic upgrade head

# roll back one migration (locally only)
uv run alembic downgrade -1

# show current migration head
uv run alembic current

# show migration history
uv run alembic history
```

### Database user management (psql, as postgres superuser)

```sql
-- create app user + db
CREATE USER appuser WITH PASSWORD 'random';
CREATE DATABASE appdb OWNER appuser;

-- rotate password
ALTER USER appuser WITH PASSWORD 'new-random';

-- list users
\du

-- list databases
\l

-- read-only user
CREATE USER app_readonly WITH PASSWORD 'random';
GRANT CONNECT ON DATABASE appdb TO app_readonly;
\c appdb
GRANT USAGE ON SCHEMA public TO app_readonly;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO app_readonly;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON TABLES TO app_readonly;

-- revoke a user
REVOKE ALL ON DATABASE appdb FROM appuser;
DROP USER appuser;
```

### Adding a new app (the steps in order)

1. New repo on GitHub
2. Copy Dockerfile, `.devcontainer/`, `.github/workflows/`, `docker-compose.yml`, `.env.example` from existing app
3. Update names everywhere
4. Add `VPS_HOST` + `VPS_SSH_KEY` secrets in repo settings
5. On VPS: `mkdir ~/<app-name>`, drop in `docker-compose.yml` + `.env`
6. On VPS: `psql` into shared postgres, `CREATE USER ... CREATE DATABASE ...`
7. `git push origin main`
8. Watch Actions tab, then `ssh myvps "docker compose -f ~/<app-name>/docker-compose.yml logs -f"`

### Deploy workflow at a glance

```
git push origin main
       │
       ▼
GitHub Actions: build.yml
  ├── docker buildx build (target=runtime)
  ├── push :latest and :sha-<commit> to GHCR
  └── ✓ green
       │
       ▼ (workflow_run trigger)
GitHub Actions: deploy.yml
  ├── ssh deploy@vps
  ├── cd ~/<app-name>
  ├── docker compose pull
  ├── docker compose run --rm migrate
  ├── docker compose up -d bot
  └── ✓ green
       │
       ▼
New container running on VPS, ~90 seconds after push
```

### What lives where

| Thing | Lives where | Notes |
|---|---|---|
| Source code | Your laptop + GitHub | Repo per app |
| Dev container | Your laptop (built locally) | Uses `dev` stage of Dockerfile |
| Production image | GHCR | Built by CI, pulled by VPS |
| App `docker-compose.yml` (local) | Your laptop, in repo | Includes Postgres service |
| App `docker-compose.yml` (prod) | VPS only, at `~/<app>/` | No Postgres; uses shared one |
| App `.env` (local) | Your laptop, gitignored | Dev creds, dev token |
| App `.env` (prod) | VPS only, at `~/<app>/.env` | Prod creds, prod token |
| Personal SSH key | WSL `~/.ssh/id_ed25519` | Mirrored to Windows for backup |
| CI deploy key (private) | GitHub Secret `VPS_SSH_KEY` | Never on your laptop's agent |
| CI deploy key (public) | VPS `/home/deploy/.ssh/authorized_keys` | |
| GHCR pull token | VPS `/home/deploy/.docker/config.json` | PAT with `read:packages` scope |
| Postgres data | VPS Docker volume `infra_postgres_data` | Backed up nightly by cron |
| Postgres root password | `/home/deploy/infra/.env` | Used only for creating per-app users |
| Per-app DB password | App's `.env` on VPS + password manager | One per app, never reused |

### Daily-cycle commands cheat sheet

| Goal | Command |
|---|---|
| Start work | `cd ~/dev/<app> && code .` → "Reopen in Container" |
| Run tests | `uv run pytest` (inside dev container) |
| Add a feature | branch, edit, test, commit, push, PR, merge |
| Add a dependency | `uv add <pkg>` then commit `pyproject.toml` + `uv.lock` |
| Create a migration | `uv run alembic revision --autogenerate -m "..."` |
| Test migration | `docker compose down -v && docker compose up -d postgres && docker compose run --rm migrate` |
| Check prod logs | `ssh myvps "docker compose -f ~/<app>/docker-compose.yml logs --tail=50 <service>"` |
| Roll back a deploy | edit VPS compose file to pin prior SHA tag, `docker compose pull && up -d` |
| Snapshot prod DB | `ssh myvps "docker exec infra-postgres-1 pg_dump -U <user> -d <db>" > snap.sql` |
| Restore locally | `docker compose down -v && up -d postgres && exec -T postgres psql ... < snap.sql` |

---

## Closing thoughts

This setup will carry you from "I have a side project" to "I have ten side projects" without architectural changes. The marginal cost of project N+1 is ~10 minutes and ~50 MB of disk. The first project is the expensive one because you're building the foundation.

What this guide does **not** cover (and you may want next):
- Horizontal scaling, load balancing, HA — when one box is no longer enough.
- Secrets rotation, vault systems — for when you have a team and "in a `.env` file on the VPS" isn't tight enough.
- IaC (Terraform, Pulumi) — when you provision multiple VPSes and want them reproducible.
- Container security scanning, signed images — for when supply-chain matters.
- Observability stack (Prometheus + Grafana + Loki) — for serious production loads.

Each of those is a separate guide. None are necessary for personal projects with one admin.

Happy shipping.
