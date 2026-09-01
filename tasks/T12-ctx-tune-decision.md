# T12 — `vortex ctx-tune <model>` build / no-build (decision note)

> Decision prep. This note records what the feature would do, the build /
> no-build / defer options, the tradeoffs, and a recommendation. The call is
> the CEO's; if approved, the implementation lands as a product milestone (L
> cost) with its own spec / tests / gates. This note is the decision artifact,
> not the implementation.

## What the feature would do

`vortex ctx-tune <model>` would automatically tune a loaded model's context
configuration to fit the observed workload. Per the backlog (item 19), a build
would cover:

1. **Workload profiling** — observe the request patterns for the model's working
   sessions (context lengths, request rates, token usage).
2. **Model context probes** — probe the model's context behavior (effective
   context window, degradation at the edges, latency vs. context length).
3. **Recommendation / application** — recommend (and optionally apply) a context
   configuration that fits the workload (e.g. the optimal context window /
   reserve).
4. **Bounded re-tuning policy** — re-tune as the workload shifts, but bounded
   (a defined cadence / trigger with a stable state, not continuous).

## Options

1. **Build** (L cost).
   - Pro: users get automatic context optimization (better performance / lower
     cost); differentiates Vortex as a full-featured model-management platform.
   - Con: L cost — profiling + probing + tuning + re-tuning is a large surface;
     the re-tuning policy must be bounded and stable (ongoing complexity).
2. **No-build** (decline).
   - Pro: no L cost; focus stays on the core (admission safety, readiness,
     robustness).
   - Con: users tune context manually; less differentiation.
3. **Defer** (revisit after the core is done).
   - Pro: no cost now; the option stays open.
   - Con: the feature is not available; the decision is deferred.

## Recommendation

**Defer** — revisit after the P1 safety work (T1 admission) is done. Rationale:
the core safety / robustness work (T1) is the priority, and ctx-tune is a
nice-to-have, not core. Building it now would divert effort from the safety
work.

If the product strategy is to differentiate Vortex as a full-featured
model-management platform (not just a robust multiplexer), then **build** is the
right call — but that is a product-strategy decision, not a technical one.

## If approved (milestone shape)

A build would be a product milestone (L cost) covering:

- The spec / ACs (workload profiling, model context probes, recommendation /
  application, bounded re-tuning policy).
- Blind tests (the profiling / probing / tuning / re-tuning behavior).
- The implementation (through refreeze).
- The full product / static / manifest gates.

## Done when

- The CEO makes the build / no-build / defer call.
- If declined / deferred: recorded here.
- If approved: specified as the milestone above and executed.
