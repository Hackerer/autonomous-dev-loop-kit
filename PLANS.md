# Autonomous Loop Plan

Updated: 2026-03-14

## Target Outcome

- Replace this placeholder with the concrete product or engineering outcome the repo should reach.

## Current State

- Describe what already works.
- Describe what is incomplete or unstable.
- Record the latest known blockers or risks.

## Non-Negotiable Constraints

- List safety, quality, compliance, runtime, or architectural constraints here.

## Acceptance Gates

- Before the session starts, persist the requested loop count with `python3 .agent-loop/scripts/set-loop-session.py --iterations N`.
- Every version must pass the commands configured in `.agent-loop/config.json`.
- Every version must produce a report in `docs/reports/`.
- Every version must be committed and published according to the configured Git strategy.

## Decision Log

- 2026-03-14: Initialize the autonomous dev loop kit.

## Backlog Notes

- Keep `.agent-loop/backlog.json` aligned with this plan.
- Prefer small, testable items over large rewrites.

## Open Questions

- Replace this section with repo-specific open questions that affect prioritization.
