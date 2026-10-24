# The instance probe — the production client's own path, from the instance role

The read-principals probes beside this directory ran from the workstation and the runner;
this one runs inside the deployed image on the app host, under the instance role and the
investigator's five read-only parameters, because a workstation pass says nothing about
the instance's address space, credentials or image (the lesson of the generator's first
cloud run). It is the acceptance run of the investigator-principals grant and of the
counting grant, both requested from the platform repository.

`send.ps1 -dir <scratch>` splices `probe.py` into `host.sh` as base64 and sends the result
over `ssm send-command`; `host.sh` reads the deployed sha, the image and the disk, checks
the five parameters are put without printing a value, exports them into one
`docker compose run` of the deployed image, and runs the probe there. The probe prints
status words, counts and request ids only:

- P0 the development world's manifest read from the world bucket and the three readers
  built from it under the investigator principals;
- P3 to P5 one list and one by-id read per vendor (Frappe employees, Jira work items,
  Calendar events in a fixed span);
- P6 one `Converse` on the registered `eu.` Haiku 4.5 profile, five output tokens at most;
- P7 the production `CountingClient` against the profile id and against the base model id;
- P8 the world bucket's create-only rule from the instance (a put with `If-None-Match: *`,
  the same put again, a put without the header), on a disposable key under `runs/probe-…/`.

Two runs, their stdout under `probes/captures/investigator-principals/`:

| run | date | deployed sha | SSM command | what it decided |
|---|---|---|---|---|
| `instance-run-01.txt` | 2026-10-11 | `8b27e525…` | `0ef3e1ab…` | P3 to P5 green (28, 33, 25), P6 `end_turn`, P7 denied on both ids (the counting grant's finding), P8 200 / 412 / AccessDenied |
| `instance-run-02.txt` | 2026-10-13 | `8cb71803…` | `bce58840…`, 24 s | the same reads; P7 `Counted` on the base model id (30 tokens, 52 ms), still denied on the profile id, as the grant states; P8 omitted |

Run 2 is this `probe.py` with the three P8 lines removed, so the disposable object of run 1
(`runs/probe-20261011T175023Z/instance-create-only.txt`) stays the only one; its removal
is pending. The error messages in the captures carry the probe's own `#`
masking of account, instance and region identifiers (`CountServiceError.message_signature`);
the bucket's AccessDenied in run 1 is the vendor's text as returned.
