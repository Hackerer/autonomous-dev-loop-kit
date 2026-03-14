# High-Quality Project Data Acquisition

Use this reference when deciding whether the loop has enough project context to act safely.

## Goal

Collect enough high-signal project data to support:

- scoped next-goal selection
- safe code edits
- accurate validation choices
- correct Git publication decisions
- useful reflection after each version

## Required Data Categories

High-quality project data should cover all of these categories before high-impact edits:

1. Repository identity
   - repo root
   - current branch
   - remotes
   - clean or dirty worktree
2. Runtime and tooling
   - languages in use
   - package managers
   - test/build tools
   - framework signals
3. Validation surface
   - available lint, typecheck, test, build, and e2e commands
   - blocking acceptance gates
4. Product and architecture context
   - current target outcome from `PLANS.md`
   - key modules or boundaries
   - open risks and constraints
5. Evidence quality
   - where the information came from
   - whether it is current
   - whether it is inferred or directly observed

## Evidence Hierarchy

Prefer stronger evidence over weaker evidence:

1. Direct observation from repo files and commands
2. Structured project artifacts such as config files and lockfiles
3. Recent reports and plans in the repo
4. Stable inference from multiple observed signals
5. User chat memory alone

Do not treat chat memory by itself as high-quality data.

## Freshness

High-quality data should be fresh enough for the current iteration:

- Git state should be observed in the current session.
- Validation commands should be checked against current repo files.
- Architectural assumptions should be refreshed after major edits.
- Remote configuration should be checked before every publish step.

## Confidence Levels

Use these confidence levels when recording data:

- `direct`: observed from files or command output
- `derived`: inferred from multiple direct signals
- `assumed`: plausible but unverified
- `stale`: previously observed but not refreshed in the current context

Avoid taking high-risk actions from `assumed` or `stale` data.

## Snapshot Shape

When persisting collected project data, use the template in `.agent-loop/templates/project-data-template.json`.

The snapshot should be able to represent:

- repo identity and Git state
- detected tooling and framework signals
- configured validation commands
- target outcome and constraints
- evidence sources, freshness, confidence, and gaps

## Minimum Standard Before Acting

Before a meaningful code edit or publication step, the loop should know:

- what repo it is in
- what the current objective is
- which commands define success
- which remote will be used for publication
- which modules are likely affected

If one of these is missing, gather more data before acting.

## Minimum Standard Before Publishing

Before publishing, the loop must have direct evidence for:

- passing validation
- the current project's GitHub remote
- the intended branch
- the report file being published

If any of these are unclear, stop and ask or inspect further.

## Scoring

The loop should convert raw project data into an explicit quality assessment before relying on it for broad edits.

At minimum, the quality assessment should answer:

- Is the snapshot sufficient to act on?
- Which blocking gaps remain?
- Which signals should be refreshed first?
