"""The launcher: the piece between a dispatched workflow and the job seam's commands, run
inside the deployed image on the instance (the first live run's step, fork 1).

Nothing in the agent writes an admission request: the agent decodes no scenario, and the
request file its ``admit`` command reads is written by a launcher that may. This package is
that launcher. ``plan`` is the pure half: from the registration at its commit, the
committed price table, the registered cell and the scenario's specification it builds the
frozen inputs an admission records, through the same provenance functions the work command
composes with, so the admission and the worker's effective configuration cannot drift; it
reserves the run's money through ``core.pricing.run_reservation``; and it decides, from an
attempt's state alone, what the lifecycle sends next. ``__main__`` is the composition root:
it reads the scenario specification from the world store, draws the launch identity, writes
the request file and the work command's cell flags beside it, and reads an attempt's state
back for the workflow between sends.

A rank-4 shell above the agent: it imports the agent's provenance and the run log's reader,
the adapters' stores and the world's scenario codec, and never a benchmark job, so the
answer key stays unreachable from the launch path as it is from the agent (the import law's
denied edges). The scenario specification it decodes is the question a run is asked, which
the instance role may read; the key is in another object under another role.
"""
