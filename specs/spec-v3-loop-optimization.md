---
version: 3
name: loop-optimization
display_name: "Loop-Based Automation Optimization"
status: draft
created: 2026-04-20
depends_on: [1]
tags: [loop, browser-harness, optimization, prompt-engineering]
---

# Loop-Based Automation Optimization

## Why (Problem Statement)

> As a developer, I want a self-improving /loop process that iterates on the Takeout automation script until it runs cleanly end-to-end, documenting what it learns at each step.

### Context

- Browser automation against real sites requires empirical discovery — the optimal click sequence can't be fully known in advance
- A prompt+path are a versioned unit: the prompt determines the execution path, and both evolve together
- `docs/takeout-loop-prompts.md` tracks this versioning: each entry names the prompt, records the actual path taken, and notes the outcome
- The goal is convergence: a stable prompt that produces a reliable, documented path every time

---

## What (Requirements)

### Acceptance Criteria

- AC-1: `/loop` prompt causes Claude to attempt the Takeout automation, observe the result, update `docs/findings.md`, and refine `request_takeout.py` between attempts
- AC-2: Each attempt is recorded as a versioned entry in `docs/takeout-loop-prompts.md` with prompt, expected path, actual path, and outcome
- AC-3: Loop sleeps 30 minutes between attempts when Google rate-limits
- AC-4: Loop stops when export is confirmed AND script runs cleanly from scratch
- AC-5: Final prompt + path pair is stable enough to serve as the canonical run recipe

### Out of Scope

- Automating the download of the completed export (v2)
- Generalizing to other Google Takeout data types

---

## How (Approach)

### Phase 1: Establish baseline prompt (v1)

- Document the v1 loop prompt in `docs/takeout-loop-prompts.md`
- Run it; record the actual path taken and outcome
- Identify divergences between expected and actual path

### Phase 2: Iterate toward convergence

- For each failed attempt: update findings, fix the identified bug in `request_takeout.py`, increment prompt version
- Track which bugs were discovered by the loop vs. known in advance
- Stop when actual path matches expected path on two consecutive runs

### Phase 3: Canonicalize

- Write the final stable prompt into `docs/takeout-loop-prompts.md` as the canonical version
- Ensure `request_takeout.py` reflects all discovered fixes
- Update `CLAUDE.md` run instructions with the confirmed sequence

---

## Technical Notes

### Prompt versioning convention (`docs/takeout-loop-prompts.md`)

Each entry:
- **Version** (v1, v2, …)
- **Status** (ready / ran / canonical)
- **Prompt** — exact text passed to `/loop`
- **Expected path** — predicted step sequence
- **Actual path** — filled in after run
- **Outcome** — success / rate-limited / new error / other
- **Changes made** — what was fixed before next version

### Risks & Mitigations

| Risk | Mitigation |
| ---- | ---------- |
| Loop runs indefinitely if bug is unfixable | Add max-attempts guard (e.g., 5) before escalating to human |
| Google changes Takeout DOM between iterations | Screenshots at every step catch this immediately |

---

## Open Questions

1. Should the loop also update `docs/findings.md` automatically, or keep that manual?
2. At what point is a prompt "stable" — two clean runs, or three?

---

## Changelog

| Date       | Change        |
| ---------- | ------------- |
| 2026-04-20 | Initial draft |
