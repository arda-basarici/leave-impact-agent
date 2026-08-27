# Deploying the agent to the app host

The host is operated from the **platform** repository
(github.com/arda-basarici/platform): the instance, its network and security
group, the instance role, the GitHub OIDC deploy role, the SSM parameter
names, the budget, and the cloud-init that lays the host down all live in its
`terraform/stacks/leave-impact-prod/`; the contract values this repository
consumes are published in its `projects/leave-impact/README.md`. This
directory holds what the application itself owns: its deployment entrypoint
(`deploy.sh`, the only thing the workflow's deploy job runs on the host).

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
