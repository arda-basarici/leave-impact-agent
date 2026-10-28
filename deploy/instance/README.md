# Deploying the agent to the app host

The host is operated from the **platform** repository
(github.com/arda-basarici/platform): the instance, its network and security
group, the instance role, the GitHub OIDC deploy role, the SSM parameter
names, the budget, and the cloud-init that lays the host down all live in its
`terraform/stacks/leave-impact-prod/`; the contract values this repository
consumes are published in its `projects/leave-impact/README.md`. This
directory holds what the application itself owns: its deployment entrypoint
(`deploy.sh`, the only thing the workflow's deploy job runs on the host) and,
since the first live run's step, the run lifecycle's host side (`lifecycle.sh`,
sent step by step by the investigate and continue-run workflows through the driver
in `../runner/`).

## What moved, and where (2026-08-27)

Until 2026-08-27 this repository carried the whole AWS layer in `infra/`,
because the agent was the account's first and only workload and the
infrastructure code had to live somewhere. The box side had already shown
the cost of that shape (a second tenant meant editing steam-lens to change a
shared proxy), so the platform repository was founded and the stack moved
there whole: same files, same backend key, a zero-diff plan on the same
state. The git history before that date still shows `infra/`; the platform
repository's DESIGN tells the extraction story.

| Was here | Lives now (platform repo) |
|---|---|
| `infra/*.tf`, `user_data.sh.tftpl`, the provider lock | `terraform/stacks/leave-impact-prod/` |
| the deploy role ARN, the instance `Name` tag, the `/leave-agent/` parameter prefix (as facts the workflow relied on) | `projects/leave-impact/README.md`, the contract table |

## The boundary probe that follows the deploy

`assert-truth-unreachable.sh` runs in the same SSM command, after `deploy.sh`, under
the instance profile: a list of the world bucket's `worlds/` succeeds (the positive
control), a list of the truth bucket and a get of its canary object are both refused
with the `AccessDenied` code. It is the public evidence that the application cannot
reach the answer key, taken on every deploy. A failure turns the run red and rolls
nothing back: the app may be healthy while the boundary is not, and the fix is in the
platform's IAM. The canary is a key known to exist, because S3 refuses a get of an
absent key with AccessDenied whenever list is denied, whatever the get permission.

## The contract this script rides

| Value | Owner | Used here |
|---|---|---|
| `arn:aws:iam::445743457479:role/leave-agent-deploy` | platform (`deploy.tf`) | the workflow's `role-to-assume`; the role may only `ssm:SendCommand` to instances tagged `Name=leave-agent-app` |
| `Name=leave-agent-app` | platform (`instance.tf`) | the workflow finds the host by this tag, so a replaced instance deploys without a workflow edit |
| `/leave-agent/postgres-password` | platform owns the name; the value is put out-of-band | read at deploy time into the process environment for `compose up`; never written to disk |
| `/srv/app`, `/srv/pgdata` | platform (cloud-init: the separate data volume is mounted at `/srv`, so both outlive the instance) | the compose file and `DEPLOYED` marker; the Postgres data directory |

`deploy.sh` lands one commit: the `compose.yaml` of that sha plus the image
CI pushed under that sha, so the host runs exactly what CI tested and a
rollback is the same script with an older sha. It runs as root on the
instance, over `ssm send-command` from the workflow's `production`
environment, never by hand.

One deploy runs on the host at a time (the worker service's step): the workflow's
deploy job sits in one concurrency group that cancels nothing in progress, so a later
run waits behind a running deploy (a newer run queued behind it replaces an older one
still queued, GitHub's default queue policy, which serializes the same), and the script
itself takes `flock -n` on `/srv/app/deploy.lock` before it
fetches or pulls anything, refusing with one sentence when another deploy holds it; the
descriptor dies with the script's shell, so a deploy that crashed holds nothing.

`DEPLOYED` names the last run that reached its end, not a verified release: the
marker is written last, so an interrupted run leaves the new `compose.yaml`
beside the old marker, and the boundary probe runs after the write, so a red
probe leaves the new marker beside a failed deploy. Recovery reads the actual
state, the image the compose file names, the containers up, the probe's result
in the workflow log, and re-runs the script. Making the marker a ledger of
verified releases waited for the service to be long-running (the M1 repository
audit's F-012); the app has served since the demo milestone's scaffold step and the
worker runs beside it since the worker service's step, so the item is due and is
ruled at that step's close.

## The run lifecycle

`lifecycle.sh` is one step of a run on the host: `launch` (the launcher's plan, the
ledger threshold as a receipt, the admission), `work`, `status`, `deliver`,
`publish` or `inventory`, each one `docker compose run` of the deployed image. The
runner-side driver `../runner/investigate.sh` sends it over `ssm send-command` with
the step's `export` lines in the payload, reads each step back, and takes the next
step from what the launcher's `status` answers. The run rides the dispatched
commit: the host refuses a step whose sha is not `DEPLOYED`'s. A deploy is approved in
Actions only between runs: the deploy job shares no concurrency group with the two run
workflows, so the environment's review gate is what keeps an image pull, the cache load
and a postgres recreation off a host with a work container running (the external read
of the pre-dispatch commits, 2026-10-16; a shared group waits on a probe of whether a
job pending review holds the group's one slot). A run's files live
under `/run/leaveimpact/<run id>/` on tmpfs, owned by the image's user and readable
by nobody else, bind-mounted into every container of the run; a reboot clears them,
`work` says so and stops, and every other word remakes the directory and fetches the
pinned registration, `inventory` taking its scope (the admission's world version and
registration commit) from the payload the driver read off `status`, so a closed
attempt is published and listed after a reboot. Secrets reach the
container through the process environment only, and a Parameter Store read that
fails ends the step with the CLI's error. The work container is named for its
attempt: the SSM agent ends a timed-out command with SIGKILL to the host's process
tree and the container outlives its client (the step's two probes), so `status`
reports that container first and the driver reads the state again while it runs
instead of re-sending work, and `work` refuses to start beside another attempt's
running container as a fault for an operator; a work process the host killed (137 under the memory
limit) is read the same way, and only the process's own exits 2 and 3 end the job at
once. The launch's three containers (plan, threshold, admit) are named for the attempt
and the step the same way, `launch` refuses to run a step beside a running one as a
fault, and `status` lists every container of the attempt the host still runs, so a
reader deciding whether the host can still admit (the dispatcher's release of a failed
run) has the host's word and not the clock's (the replay step's third external read). The driver's poll is bounded and classifies its failures, and a send it cannot
read past ends the job naming `continue-run`, which takes the attempt's approval
policy and its ledger as inputs: `status` prints the ledger the attempt's row records
beside the scope, and the host refuses an inventory whose ledger input differs from
it, after a reboot as before one (the demo milestone's replay step and its external
read, which found the first form of this check reading `run.env`, a file the reboot
clears). Both scripts' headers carry the rules; the fake-binary tests
under `tests/unit/` run every step and every branch of the walk, and CI runs
shellcheck over this directory and `../runner/`.

## Backup and recovery (the demo milestone's backup step, 2026-10-24)

The database is the application's one durable state: the run log and its ledgers, the
publishable attempts, the corpus cache. Its backup is the platform's (`projects/leave-impact/`
in the platform repository, its runbook the operations): `leave-impact-backup.timer` dumps the
whole database nightly at 03:30 UTC into the backup bucket under `daily/leaveimpact-<date>.dump`
by conditional create, with the `ledger_capture` view's rows as the object's metadata, read in
the dump's own transaction; `leave-impact-restore-check.timer` restores the newest object
monthly into a scratch database on the live service and runs this image's
`python -m leaveimpact.app verify-restore` with that capture on stdin. The command runs both
bootstraps on the scratch database first, then seven checks, one printed line each, and exits
0 only on seven of seven (what each checks: the `restore` module's docstring). The first drill,
2026-10-24: `daily/leaveimpact-2026-10-23.dump`, seven of seven, 214 closed attempts recharged
(`probes/FINDINGS.md`, backup-restore-drill). The command reads only, so it also runs against
the live database as a check after a recovery (the compose default `DATABASE_URL`).

**The recovery point.** A nightly dump loses up to a day: admissions, settlements and
publications made after the last dump are gone from the database and not from the bill of the
vendor that served them. After a real recovery the live flag stays off (off by default; a
recovery flips nothing) until the lost window is reconciled from billing on the host:

```
docker compose run --rm app python -m leaveimpact.agent import-spend --request <identity, held across retries> --ledger <ledger id> --amount <pico-dollars> --authority "<who, from what bill>" --registration-commit <sha>
```

one import per ledger that spent in the window, the Bedrock bill as the authority; the
102 sends still unimported are the precedent for the form.

**The procedure.** Stop the worker and the app (`docker compose stop worker app`, the worker
first so no attempt is mid-flight over the restore); choose the object (the key and
the version id from the bucket's listing, read with the administrator identity from a
workstation, since the instance role holds no list); restore it into the live database with
the platform's restore script's own restore line (it verifies the digest against the object's
metadata first); re-run the deploy for the deployed sha from Actions, so both bootstraps, the
identity check and the readiness check run as at every landing; then run `verify-restore`
against the live database with the object's capture on stdin from a file, and keep the live
flag off until the import above is done.

## The worker service (the worker service's step, 2026-10-28)

The third container of the stack: `python -m leaveimpact.app worker`, the single-flight
loop that runs a visitor's attempt (the sweeper's pass and one attempt per tick, each
attempt worked in a child the service supervises; `src/leaveimpact/app/worker.py` carries
the design, `probes/FINDINGS.md` under `worker-blocked` the probe that chose the child).
It is the one service whose environment names the investigator's vendor principals: the
deploy reads the five parameters under `/leave-agent/` and exports them with the two base
URLs for `compose up`, and the lifecycle's `work` step runs its one-off container as this
service for the same reason; `app` names none, held by `tests/unit/test_compose_edge.py`.
Its memory limit is the baseline's reservation (512 MiB) until a public attempt runs under
it, which is the live path's first acceptance; the three limits sum to the budget line
`tests/unit/test_memory_baseline.py` holds.

**Reading it.** `docker compose ps` shows the three containers and the worker's health;
`docker compose logs worker` is one line per tick action, claim and ending (ids, kinds and
exit codes, nothing of a scenario). The health is the heartbeat the loop writes
(`/tmp/leaveimpact-worker-heartbeat.json` inside the container): idle, a deadline three
intervals ahead rewritten per tick; working, the claim's instant plus the wall plus a
cleanup allowance; the check (`python -m leaveimpact.app.heartbeat`, standard library
only, so it costs the interpreter's start) compares the clock with the deadline. Unhealthy
means the loop stopped ticking or a child is past its wall and its cleanup; Docker restarts
nothing on it, `up --wait` and the platform's monitor read it.

**The deploy's order and its window.** The script reads every parameter and pulls every
image first, with the target's compose file fetched beside the installed one, then stops
the worker under the installed file when that file names the service (`compose stop`,
under `stop_grace_period: 15s`: the
service's own chain is the child's terminate, the supervisor's ten-second grace, the kill
and the reap, measured at 10.2 s; an attempt mid-flight ends its segment where the store
answers and the replacement's start pass closes it), installs the target's file, runs the
cache load and the two bootstraps, swaps the app, and starts the worker last when the
target names it. A service is stopped and started by name in the file compose reads, and
a file that does not name it answers "no such service", so a rollback to a release
before the worker drains the running worker under the installed file and starts none
(its stopped container stays as an orphan compose warns about until a deploy that names
the service again, or `docker compose rm worker`). Between the stop and the swap the
previous app container serves, and a schema advance makes it refuse every log read until
the swap; the window's length is read off the phase stamps the script prints, and this
step's first deploy is where it was first measured. A deploy that fails after the stop
leaves the worker stopped, since a container `compose stop` stopped does not return under
`unless-stopped`, a reboot included: before the first bootstrap the script's trap starts
the previous worker again (the window holds only the stop and the file's replacement);
after one, the worker stays stopped until a deploy succeeds, the trap says so with the
rerun line, `docker compose ps` shows it exited, its heartbeat is absent, and the public
attempts are untended until the rerun (this script with the same sha and digest, or the
rollback's older ones). A failure after the worker's own start (its wait, the prune) is
different: a detached start leaves the container running whatever its wait said, so the
trap claims nothing about it beyond what `docker compose ps` shows, and the marker stays
unwritten. On a host that ran no worker before the deploy, the trap says so instead.

**A reboot.** The daemon stops the containers in parallel under its own shutdown cap, so
PostgreSQL may be gone before the worker's last append; the segment is left open and the
replacement's start pass fences and closes it under the sweeper's rule, the same path the
probe's fourth blocked case exercises. A reboot is crash recovery, not a drain, and needs
no stop ordering between the services and no change to the daemon's configuration (the
step's fork 9, decided under the fifteen-second grace).
