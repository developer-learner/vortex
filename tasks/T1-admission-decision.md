# T1 — Fail-safe admission under uncertain occupancy (decision note)

> Milestone kickoff. This note records the problem, the policy options, a
> recommendation, and the blind-test plan. The policy choice is the CEO/TPM's;
> once chosen, the implementation lands through a controlled Vortex milestone
> (blind tests → refreeze → implementation → full gates). This is fail-safe
> accounting, not a missing Manager slot lock (the slot lock is correct).

## Problem

`Manager.all_ready()` is the admission/eviction accounting set. It includes only
entries where `owner_status == "ready"` — i.e. the port is owned by a process
modelmux identifies (PID + start-time sidecar match). Two classes of non-target
occupancy are therefore **excluded** from the accounting:

1. **`SCAN_UNKNOWN`** — the port scan was incomplete (some processes unreadable,
   no listener identified). `occupying_pid()` returns `SCAN_UNKNOWN`.
2. **Unidentified occupant** — a process is on the port but its sidecar is
   missing or invalid, so it cannot be identified. `owner_status` is not
   `"ready"`.

Because these entries are excluded from `all_ready()`, `eviction_required()`
undercounts catalog-associated RAM while host state is uncertain, so admission
can allow a load that would overcommit RAM.

Note: the **identified-but-unverified** case is already counted (an identified,
RAM-consuming runtime counts toward admission even before this session verifies
it). T1 is specifically about the **uncertain / unidentified** case.

## Policy options

1. **Refuse new loads** when any non-target entry is `SCAN_UNKNOWN` or
   unidentified.
   - Pro: maximally fail-safe (never overcommit).
   - Con: a single uncertain entry blocks all new loads (availability hit).
2. **Conservatively count the catalog RAM estimate** for uncertain non-target
   entries.
   - Pro: fail-safe (counts the worst-case RAM), simple, no availability hit.
   - Con: overcounts (the entry may not be using its full estimate).
3. **Incorporate actual host-available memory** as an additional bound (use
   `psutil.virtual_memory().available` rather than 80% of total).
   - Pro: reflects the actual host state (accounts for other processes).
   - Con: less predictable (depends on the host's current state).
4. **A documented combination** (e.g. option 2 + option 3).
   - Pro: most robust.
   - Con: most complex.

## Recommendation

**Option 2** (conservatively count the catalog RAM estimate for uncertain
non-target entries), optionally combined with **option 3** (host-available
memory) for extra robustness.

Rationale: option 2 is fail-safe (never undercounts RAM), simple, and has no
availability hit (a single uncertain entry does not block all loads). It
directly closes the gap — the uncertain entries are counted in the admission
accounting. Option 3 is an optional enhancement that makes the available-memory
calculation more accurate (it accounts for other processes' usage) but is less
predictable.

## Implementation sketch (for the milestone)

In `Manager.eviction_required()`, when computing `used`, add the uncertain
non-target entries' catalog estimates:

```python
used = sum((e.ram_estimate_gb or 0) for e in loaded)
# T1: conservatively count uncertain non-target entries with their catalog
# estimate, so admission never undercounts RAM while host state is uncertain.
for e in self.catalog.entries:
    if e.public_id == entry.public_id or e in loaded:
        continue
    if self.lifecycle.owner_status(e, self.lifecycle.occupying_pid(e)) != "ready":
        used += e.ram_estimate_gb or 0
```

The uncertain entries are counted in `used` (the RAM calculation) but **not** in
the eviction candidates, because an entry modelmux cannot identify cannot be
evicted. The target entry is excluded (it is the load being admitted, and if it
itself is uncertain `_preflight_load` already refuses the load).

## Blind-test plan

The blind tests must discriminate the uncertain case from the already-counted
identified-unverified case:

1. **Uncertain non-target entry is counted** — a non-target entry that is
   `SCAN_UNKNOWN` (or has an unidentified occupant) is counted in the admission
   accounting, so a load that would otherwise overcommit is refused.
2. **Identified-unverified entry is still counted** — an identified,
   RAM-consuming but unverified runtime still counts (no regression).
3. **Identified-verified entry is counted** — an identified, verified runtime
   still counts (no regression).
4. **No uncertain entries** — with no uncertain occupancy, admission behaves as
   before (no regression).

Tests are authored blind (before the implementation) and must pass after the
implementation lands through refreeze.

## Done when

- The policy is recorded (this note + the CEO/TPM's choice).
- The blind tests discriminate the uncertain case without regressing the
  identified-unverified case.
- The implementation lands through refreeze.
- The full product / static / manifest gates pass.
