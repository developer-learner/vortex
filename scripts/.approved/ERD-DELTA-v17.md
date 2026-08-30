# ERD-DELTA v17 — errata: T1 smoke_check must not require FS writes

Behavioral delta: none. Test bytes: none changed. Source bytes: none changed.
This is a one-line correction to the v16 smoke_check that guards T1
(`src/vortex/manager.py`, CARRIED NO-EDIT).

## What v16 got wrong

v16 pinned the T1 smoke_check as:

```
python3 -m py_compile src/vortex/manager.py
```

That command writes `src/vortex/__pycache__/manager.cpython-XX.pyc`. But the
D-30 Podman lane orchestrate uses for smoke checks mounts the repo READ-ONLY
(no `--rw` grant is issued for a smoke check, and none should be — the whole
point of the NO-EDIT invariant is that nothing in this pass writes to the
file's directory). The smoke_check therefore fails deterministically with OSError errno 30
`Read-only file system` on the target path
`src/vortex/__pycache__/manager.cpython-312.pyc.NUMERIC`, reproduced under
`scripts/sandbox-run.sh python3 -m py_compile src/vortex/manager.py` inside
the dev VM.

T1 halts orchestrate before T2/T3/T4 can run. First observed on the v16
orchestrate launch (session log at `/tmp/orch-v16.log`, operator review at
`.pipeline-state/operator-review/T1.md`, EM diagnosis:
`transient_or_environmental`).

## What v17 fixes

The smoke_check becomes a write-free equivalent that checks the same
invariant (the file parses as valid Python):

```
python3 -c "compile(open('src/vortex/manager.py').read(), 'src/vortex/manager.py', 'exec')"
```

Same guarantee as `py_compile`: the source is parsed and compiled to bytecode
in-memory. The bytecode is discarded; nothing is written to disk. The check
passes in the RO sandbox and continues to fail closed on any real syntax
regression in `manager.py`.

## Changed acceptance criteria

None. v17 is doc-level errata: no PRD AC is added, removed, or reworded.
The AC block carried forward from v15/v16 (AC-1..AC-6) stays immutable.

## Superseded acceptance criteria

None (v17 is doc-level errata; no AC bytes change). The v16 smoke_check
string in `contracts.smoke_checks["src/vortex/manager.py"]` is superseded by
the v17 string above.

## Changed files

- `contracts.json` — `smoke_checks["src/vortex/manager.py"]` changes to the
  write-free form. Every other contracts entry is unchanged.
- `src/vortex/manager.py` — carried byte-identical (still `no_edit_files`).
- `src/vortex/discovery.py`, `src/vortex/app.py`, `src/vortex/ui.py` — carried
  from v16 unchanged; still in `changed_files` for the coder to reach.

## Test-to-file mapping

Unchanged from v16. Every v14/v15/v16 frozen test node-id keeps its owning
task after the mechanical B3 synthesizer replans on v17.

## Follow-up (post-v17, out of scope for this errata)

The plan gate should dry-run every declared smoke_check inside the RO
sandbox at refreeze time so this class of defect fails at freeze, not at
orchestrate. Filed as a `sw-dev-blueprint` backlog item, not a v17 change.
