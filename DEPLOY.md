# Deploy — EnglshBot

Production deployment via Docker Compose. The bot runs long-polling (no inbound
ports / webhook needed), so it works on any Linux box with Docker.

---

## 0. Before you start

- **Rotate the bot token.** The token was shared in plaintext earlier — open
  [@BotFather](https://t.me/BotFather) → `/revoke` → get a fresh one. Put the new
  token only in the server `.env` (never commit it; `.env` is gitignored).
- You need a Linux server with **Docker Engine + Compose plugin**.

Install Docker on a fresh Ubuntu/Debian server (skip if already installed):

```bash
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER   # re-login afterwards
docker compose version          # verify the compose plugin is present
```

---

## 1. Get the code onto the server

Either clone from your git remote:

```bash
git clone <your-repo-url> englshbot && cd englshbot
```

…or copy the project from your machine (excludes secrets/junk via rsync):

```bash
rsync -av --exclude '.git' --exclude '.venv' --exclude '__pycache__' \
      --exclude '.env' ./ user@server:/opt/englshbot/
```

---

## 2. Create the server `.env`

The prod compose assembles `DATABASE_URL` / `REDIS_URL` itself, so you only set a
few values. Minimal production `.env`:

```dotenv
# Telegram
BOT_TOKEN=<NEW_TOKEN_FROM_BOTFATHER>

# Database — set a STRONG password; it's the single source of truth.
POSTGRES_PASSWORD=<long-random-password>
# optional overrides (defaults: englsh / englsh)
# POSTGRES_USER=englsh
# POSTGRES_DB=englsh

# Access gate — set a non-empty value to require a password on /start (empty = open)
ACCESS_PASSWORD=

# Logging
LOG_LEVEL=INFO
LOG_FORMAT=json
```

Generate a strong DB password quickly:

```bash
openssl rand -base64 24
```

> You do **not** need `DATABASE_URL` / `REDIS_URL` in `.env` for the prod compose —
> they are injected by `docker-compose.prod.yml`. (If present, they're overridden.)

Lock down the file:

```bash
chmod 600 .env
```

---

## 3. Launch

```bash
docker compose -f docker-compose.prod.yml up -d --build
```

This builds the image, starts Postgres + Redis, waits until they're healthy,
runs `alembic upgrade head` (DB schema + seed packs), then starts the bot.

---

## 4. Verify

```bash
docker compose -f docker-compose.prod.yml ps          # all services Up / healthy
docker compose -f docker-compose.prod.yml logs -f bot  # watch JSON logs
```

You're good when you see a line like:

```json
{"event":"bot_starting","logger":"main","level":"info","timestamp":"..."}
```

Then open the bot in Telegram and send `/start`. (If `ACCESS_PASSWORD` is set,
it will ask for the password first.)

---

## 5. Updating

```bash
git pull                                                   # or rsync new code
docker compose -f docker-compose.prod.yml up -d --build     # rebuild + restart
```

Migrations apply automatically on start (`alembic upgrade head`). Compose recreates
only changed containers; Postgres/Redis data persist in named volumes.

---

## 6. Operations cheatsheet

```bash
# Logs (JSON, one event per line — pipe to jq if installed)
docker compose -f docker-compose.prod.yml logs -f bot | jq .

# Restart just the bot
docker compose -f docker-compose.prod.yml restart bot

# Stop everything (data kept)
docker compose -f docker-compose.prod.yml down

# One-off DB shell
docker compose -f docker-compose.prod.yml exec postgres psql -U englsh englsh
```

### Automated backups

A daily `pg_dump` runs via host cron (installed once):

```bash
bash /opt/englshbot/scripts/install-backup-cron.sh   # idempotent
bash /opt/englshbot/scripts/backup.sh                # run one now
```

Dumps land in `/opt/englshbot/backups/englsh-YYYYmmdd-HHMMSS.sql.gz`, kept 14
days (`RETENTION_DAYS`). Restore:

```bash
gunzip -c /opt/englshbot/backups/englsh-<stamp>.sql.gz \
  | docker exec -i englshbot-postgres-1 psql -U englsh -d englsh
```

**Offsite:** the dumps live on the same VPS as the data. Periodically pull one
to another machine, e.g. from a laptop:

```bash
scp root@95.217.98.125:/opt/englshbot/backups/$(ssh root@95.217.98.125 \
  'ls -t /opt/englshbot/backups/englsh-*.sql.gz | head -1' | xargs basename) .
```

---

## 7. Security notes

- Postgres/Redis ports are **not** exposed to the host in prod compose — only the
  bot reaches them over the internal network. Keep it that way.
- `.env` holds the token and DB password: `chmod 600`, never commit it
  (`.dockerignore` keeps it out of the image, `.gitignore` keeps it out of git).
- Enable a host firewall (e.g. `ufw allow OpenSSH && ufw enable`). The bot needs
  only outbound HTTPS to Telegram — no inbound ports.
- Logs go to stdout as JSON and are captured by Docker (rotated at 10 MB × 3).
  To centralize later, point a log shipper (Vector/Promtail) at the Docker logs.

---

## 8. Known follow-ups (not blockers)

- **Reminder system** (daily / streak / inactivity) is not implemented yet — it
  needs a scheduler. Add as a separate worker service later.
- First run seeds sample packs (migration `0002`); extend `examples.json` for
  richer example coverage.
- Japanese track is behind `ENABLE_JAPANESE=false` (foundation only).
