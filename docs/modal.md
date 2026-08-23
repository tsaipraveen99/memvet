# Modal verification

MemVet can run recorded tests inside an ephemeral Modal Sandbox:

```bash
python -m pip install modal
modal setup
memvet verify decision-001 --run-tests --sandbox modal
```

The verifier copies the repository into a Debian-based image, runs the recorded `unittest` paths with `PYTHONPATH=src`, captures stdout and stderr, and cleans up the sandbox. Modal is optional; local verification remains the default and does not require cloud credentials.

The integration uses Modal’s asynchronous Sandbox API and filesystem image transfer. Set `MEMVET_MODAL_APP` to override the default app name `memvet-review`.
