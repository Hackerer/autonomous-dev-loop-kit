# ReAct Reasoning And Acting Guide

This file describes `ReAct` as introduced by Shunyu Yao et al. in `ReAct: Synergizing Reasoning and Acting in Language Models`.

`ReAct` here does not mean the frontend library `React`.

## Why Use ReAct In An Autonomous Dev Loop

An autonomous coding loop fails when it jumps straight from a rough idea to a large code change. ReAct reduces that failure mode by forcing an evidence-driven cycle:

1. Reason about the current state.
2. Take one concrete action.
3. Observe what changed.
4. Update the next step from the new evidence.

This pattern is especially useful for:

- unfamiliar codebases
- ambiguous requirements
- risky architecture changes
- debugging
- long-running multi-version loops

## ReAct Inside One Version

Use a small repeated cycle inside each version:

1. Inspect the relevant code, tests, config, and recent reports.
2. Form a concise hypothesis about what should change next.
3. Execute one bounded action:
   - read a file
   - edit a file
   - run a test
   - run a build
   - inspect output
4. Record the key observation.
5. Decide whether to continue, revise the plan, or stop.

## Deep Thinking Before Execution

Before major edits, silently think through:

- current behavior
- desired behavior
- likely root causes
- architecture boundaries
- test surface
- failure modes
- rollback or recovery path

Do not dump long reasoning traces into chat. Externalize only:

- concise decisions
- critical assumptions
- surprising observations
- risks
- why the chosen next step is justified

## Architecture Use

Before implementation, ask:

- Is this the right module or layer to change?
- Who should own this state or behavior?
- Can the change remain local?
- What regression surface will this create?
- What is the smallest validated version that moves the product forward?

## Debugging Use

When debugging:

- avoid guessing
- reproduce first
- inspect evidence
- change one thing at a time when possible
- re-run the relevant validation quickly before the full suite

## Reporting Use

Every version report should retain:

- the key observations that changed the plan
- the validation evidence
- the requirement or architecture reflection that informs the next version

The report should make it obvious why the next action was chosen.
