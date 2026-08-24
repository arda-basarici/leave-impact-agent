# Frappe HR on the box

The simulated org's HRIS. One Compose stack under `/srv/frappe/` on the netcup
box, joined to the box's shared `web` network and fronted by the box-owned Caddy
(`steam-lens/deploy/box/` owns the proxy, firewall and host provisioning — this
directory adds one stack and one Caddyfile stanza, exactly as that README's
"new project" contract says). The application on AWS reaches it over HTTPS as a
remote system; nothing here runs where the agent runs.

Public host: `hr.ardabasarici.dev` (Cloudflare, orange-cloud, SSL Full (strict) —
the same origin-CA pair Caddy already holds covers `*.ardabasarici.dev`).

## The image

`ghcr.io/arda-basarici/leave-impact-frappe` — Frappe `v16.31.0` with ERPNext and
Frappe HR from `apps.json`, built by `.github/workflows/frappe-image.yml` from a
pinned `frappe_docker` commit. No official image carries hrms, and the box never
builds, so CI is the builder (DESIGN: production hosts consume artifacts, they
don't manufacture them). The box references the image **by digest**: the
workflow's build step prints it (`ImageID`/`Digest` in the job summary), and
`/srv/frappe/.env` carries `FRAPPE_IMAGE=ghcr.io/…@sha256:…`; the `:16` and
`:<git-sha>` tags exist for humans. Rebuild: bump `apps.json` (or dispatch the
workflow) → new digest → edit the one `.env` line → `compose up -d`.

## Bring-up (first time)

```sh
# 1. DNS: A record hr → origin IP, PROXIED (orange) before anything listens.

# 2. Box directory + secrets (never committed; chmod 600 like steamlens's).
ssh steamlens 'mkdir -p /srv/frappe/data/db'
scp deploy/frappe/compose.yaml steamlens:/srv/frappe/compose.yaml
ssh steamlens 'umask 077 && printf "DB_PASSWORD=%s\nFRAPPE_SITE_NAME=hr.ardabasarici.dev\n" \
  "$(openssl rand -hex 24)" > /srv/frappe/.env'

# 3. Caddy stanza (steam-lens/deploy/box/Caddyfile gets it; reload the proxy).
#    The site block is the steamlens one minus the app-specific parts:
#
#    hr.ardabasarici.dev {
#        tls /etc/caddy/certs/ardabasarici.dev.pem /etc/caddy/certs/ardabasarici.dev.key
#        header {
#            Strict-Transport-Security "max-age=15552000"
#            X-Content-Type-Options "nosniff"
#            Referrer-Policy "strict-origin-when-cross-origin"
#        }
#        reverse_proxy frappe-frontend-1:8080 {
#            header_up X-Forwarded-For {client_ip}
#        }
#    }
ssh steamlens 'cd /srv/box-proxy && docker compose exec caddy caddy reload --config /etc/caddy/Caddyfile'

# 4. Stack up, then the site (one bench, one site, named after its host).
ssh steamlens 'cd /srv/frappe && docker compose pull && docker compose up -d'
ssh steamlens 'cd /srv/frappe && set -a && . ./.env && set +a && \
  docker compose exec backend bench new-site "$FRAPPE_SITE_NAME" \
    --mariadb-user-host-login-scope="%" --db-root-username root \
    --db-root-password "$DB_PASSWORD" \
    --admin-password "<choose; goes into the probe env, not here>" \
    --install-app erpnext --install-app hrms'
```

`--mariadb-user-host-login-scope='%'`: the site's DB user must accept
connections from any container IP — they are not stable across recreates.

Verify: `https://hr.ardabasarici.dev` shows the login page from outside; on the
box `docker ps` shows no port arrow on any `frappe-*` container (only Caddy
publishes); `free -m` and `docker stats --no-stream` captured to
`probes/captures/frappe-up/`.

## Sites — one per world version (ruled 2026-08-24)

The bench is multi-site: `FRAPPE_SITE_NAME_HEADER` is `$host`, so the Host
header Caddy forwards selects the site, and sites are named after their public
hosts. A world gets a fresh site (provably clean by creation — the alternative,
scrubbing a shared site, can't prove what's left); resetting a world is
drop-and-recreate, ~2 min. Per new world `<name>` (e.g. `hr-w1`):

```sh
# 1. Cloudflare: A record <name> -> origin IP, PROXIED (the origin-CA pair
#    already covers *.ardabasarici.dev).
# 2. Caddy: copy the hr stanza in the box Caddyfile for <name>.ardabasarici.dev,
#    reload the proxy.
# 3. The site (scheduler is disabled on a fresh site — enable it):
ssh box 'cd /srv/frappe && set -a && . ./.env && set +a &&   docker compose exec backend bench new-site <name>.ardabasarici.dev     --mariadb-user-host-login-scope="%" --db-root-username root     --db-root-password "$DB_PASSWORD"     --admin-password "<choose; env ceremony, never here>"     --install-app erpnext --install-app hrms'
ssh box 'cd /srv/frappe && docker compose exec backend   bench --site <name>.ardabasarici.dev enable-scheduler'
# Teardown: bench drop-site + remove the Caddy stanza + the DNS record.
```

## Footprint

Memory limits in `compose.yaml` are first guesses sized for a 16 GB box shared
with SteamLens (~0.6 GB resting): ~5.4 GB hard cap across the stack, 2 GB swap
as the last line. The `frappe-up` probe records the resting and seeded
footprints and the limits get re-derived from them.

## Backup

MariaDB's data dir is a bind mount (`/srv/frappe/data/db`); the nightly box
backup covers it once a `mariadb-dump` step joins `backup.sh` — parked in the
stream's TODO until the world milestone gives it data worth keeping.
