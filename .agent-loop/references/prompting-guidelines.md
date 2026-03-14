# Prompting Guidelines For High-Quality Autonomous Loops

`ReAct` here means the Shunyu Yao et al. paper pattern, `Reason + Act`, not the frontend framework `React`.

## Shared Rules

Use a thin prompt and a thick protocol.

- State the objective, gates, and stop conditions directly.
- Avoid long prose about how to think.
- Persist decisions in files instead of chat.
- Force one scoped version at a time.
- Make real validation, report writing, and publication mandatory artifacts.
- Persist the requested loop count before the first iteration so the model does not have to remember it from chat.
- Require deep analysis before execution, but keep that reasoning mostly implicit and store only concise conclusions.
- Treat GitHub publication as project-local. If the target repo for the current project is unclear, ask before pushing.

If the user launches with only a count, such as `循环3次`, treat that as a full loop start command. The protocol supplies the missing requirements.

## What Raises Quality

- Clear target outcome in `PLANS.md`
- Real acceptance gates in `.agent-loop/config.json`
- Durable state in `.agent-loop/state.json`
- Small backlog items in `.agent-loop/backlog.json`
- Report-driven reflection after each version
- ReAct-style evidence gathering before code edits

## What Lowers Quality

- Placeholder validation commands left in place
- Prompting the model to be “very smart” without defining gates
- Asking for infinite loops without stop conditions
- Relying on chat context for memory
- Passing tests by hard-coding edge cases
- Making large edits before inspecting the relevant code, architecture, and test surface

## ReAct Pattern

Within each iteration, use this cadence:

1. Reason from current evidence.
2. Take the smallest useful action.
3. Observe the result.
4. Update the next step.

The model should think deeply before executing, especially before architectural changes, destructive actions, or expensive refactors. Do not force long chain-of-thought in chat. Persist only concise conclusions, observations, and decisions.

## Codex Wrapper Style

For Codex, keep the wrapper concise.

- Prefer direct rules over motivational language.
- Do not force verbose chain-of-thought or long preambles.
- Point Codex to files, commands, and scripts.
- Tell Codex what must be true before it can publish.
- Instruct Codex to do silent pre-execution analysis and then act in short ReAct cycles.

## Claude Wrapper Style

For Claude Code, keep the wrapper structured.

- Use clear sections or tags to separate load order, gates, loop steps, and stop conditions.
- Use examples only when they constrain output format or behavior.
- Do not over-specify internal reasoning if a simple protocol already exists.
- Instruct Claude to reason deeply before acting, then execute in small observe-and-update steps.

## Prompt Pattern

The highest-signal pattern for this workflow is:

1. Define the target outcome.
2. Define non-negotiable gates.
3. Define the iteration state machine.
4. Define stop conditions.
5. Define the files that hold durable state.

Anything beyond that should be justified by a real failure mode.

## Minimal User Input Pattern

Support a minimal launch where the user only specifies iteration count.

Expected interpretation:

- `循环3次` means:
  - start the autonomous loop in the current repo
  - persist the session with 3 iterations
  - use ReAct reasoning-plus-action cadence inside each iteration
  - run one scoped version at a time
  - require full validation before publication
  - require a report for every version
  - require Git publication for every version
  - stop automatically after the third published version or earlier on stop conditions
