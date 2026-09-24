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
# 4. The API key pair on the site's Administrator (bench execute generate_keys, in
#    your own terminal; the pair goes to the benchmark environment's secrets).
# 5. The read principals (M2 build plan step 0, ruled 2026-09-22): one read-only
#    role, one user per reading consumer on it, a key pair per user. Repeated on
#    every world site, because a role and its users live in the site's database.
#    The role has no desk access, so its holders are saved as Website Users and
#    never receive the automatic Desk User role; `add_permission` grants read only
#    and, on a doctype's first custom rule, copies the standard rows into Custom
#    DocPerm (the four doctypes are customized from then on, frozen against
#    upstream defaults: fine on a synthetic site recreated per world) and refuses
#    a duplicate rule, so the permission loop is repeatable; the role insert and the
#    two user creations are not, they refuse a duplicate, which on a partial rerun
#    is the signal that step was already done. No password: the keys are the only
#    way in, and the users never see the desk.
ssh box 'cd /srv/frappe && docker compose exec backend bench --site <name>.ardabasarici.dev execute frappe.client.insert --kwargs "{\"doc\": {\"doctype\": \"Role\", \"role_name\": \"Leave Impact Reader\", \"desk_access\": 0}}"'
for doctype in Employee Department "Leave Application" "Employee Skill Map"; do
  ssh box "cd /srv/frappe && docker compose exec backend bench --site <name>.ardabasarici.dev execute frappe.permissions.add_permission --kwargs '{\"doctype\": \"$doctype\", \"role\": \"Leave Impact Reader\"}'"
done
for user in validator-reader investigator-reader; do
  ssh box "cd /srv/frappe && docker compose exec backend bench --site <name>.ardabasarici.dev add-user $user@ardabasarici.dev --first-name $user --last-name reader --add-role 'Leave Impact Reader'"
done
#    The key pair per user (prints the pair: run in your own terminal; the validator's
#    goes to the benchmark environment's secrets, the investigator's to the instance's
#    SSM parameters; regenerate on the site to rotate):
#    bench --site <name>.ardabasarici.dev execute frappe.core.doctype.user.user.generate_keys \
#      --args '["validator-reader@ardabasarici.dev"]'
#    Acceptance is `probes/read-principals/probe.py frappe --principal <p>` per user.
# That is the whole recipe: a blank, usable site with its read principals. ERPNext's
# setup wizard is NOT a step here — the generator's preparation checks the site is setup-complete and
# completes the wizard itself when it is not (the first truly fresh world site,
# hr-w2, refused the world's company until it did; 2026-09-15).
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
