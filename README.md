# autonomous-dev-loop-kit

A cross-CLI autonomous development loop kit for:

- Codex CLI
- Claude Code CLI

The kit lets you start an autonomous multi-version development session with a minimal user command such as:

```text
循环3次
```

or:

```text
按 ReAct 循环3次
```

`ReAct` here means the paper pattern from Shunyu Yao et al., `Reason + Act`, not the frontend framework `React`.

## Committee-Driven Iteration Model

Each iteration now enforces:

- explicit research before goal selection
- a lightweight committee system before implementation
- post-validation reflection before publication

The lightweight committee system is now split into:

- Product Council
- Architecture Council
- Operator Council
- Secretariat
- Independent Evaluator

The councils and evaluator are defined in `.agent-loop/config.json`. The repo also renders their responsibilities and output contracts with:

```bash
python3 .agent-loop/scripts/render-committee.py
```

## What It Enforces

For every version, the loop requires:

- one scoped goal at a time
- deep analysis before execution
- short reason -> act -> observe -> update cycles
- full validation before publication
- a report in `docs/reports/`
- Git publication for the current project
- reflection before the next version starts

The session stops automatically when the requested iteration count is reached or when a configured stop condition is hit.

## Safety Rules

- Each project must publish to its own GitHub repository.
- If the current project's GitHub remote is missing or unclear, the agent should stop and ask before publishing.
- The loop should never push one project to another project's remote.

## Repository Layout

```text
.agents/skills/autonomous-dev-loop/
.claude/skills/autonomous-dev-loop/
.agent-loop/
AGENTS.md
CLAUDE.md
PLANS.md
docs/reports/
```

## Install Into A Project

Copy the following into the root of the target project:

- `.agents/`
- `.claude/`
- `.agent-loop/`
- `AGENTS.md`
- `CLAUDE.md`
- `PLANS.md`

Then replace the placeholder validation command in `.agent-loop/config.json` with the real commands for that project, for example:

- lint
- typecheck
- unit test
- integration test
- build
- e2e

Do not leave the placeholder validation step in place for real use.

Also customize the committee members in `.agent-loop/config.json` if the default product-manager, technical-architect, and user personas do not match the target project.

## Install Into A Target Project

To install the committee-driven kit into a project root, run:

```bash
./scripts/install-into-project.sh --target /path/to/project
```

The installer syncs reusable kit assets such as:

- `.agents/`
- `.claude/`
- `.agent-loop/scripts/`
- `.agent-loop/references/`
- `.agent-loop/templates/`

It also seeds these files if they are missing:

- `AGENTS.md`
- `CLAUDE.md`
- `PLANS.md`
- `.agent-loop/config.json`
- `.agent-loop/state.json`
- `.agent-loop/backlog.json`

By default, the installer preserves an existing target project's `.agent-loop/config.json`, `.agent-loop/state.json`, `.agent-loop/backlog.json`, `AGENTS.md`, `CLAUDE.md`, and `PLANS.md`.

Optional flags:

- `--overwrite-config`
- `--overwrite-state`
- `--overwrite-backlog`
- `--overwrite-top-level`

## Install Into Local CLI Skill Directories

To install this kit into your user-level Codex and Claude Code skill folders, run:

```bash
./scripts/install-to-clis.sh
```

Optional flags:

- `--codex-only`
- `--claude-only`
- `--name custom-bundle-name`

The installer copies the full kit into:

- `~/.codex/skills/<bundle-name>/`
- `~/.claude/skills/<bundle-name>/`

## Minimal Launch

Once installed in a project, the user can launch the loop with a count-only prompt:

```text
循环3次
```

The wrappers interpret that as:

- start the autonomous loop in the current project
- persist the session target as 3 iterations
- run one version at a time
- validate every version fully
- write a report for every version
- publish every version to the current project's own GitHub repo
- stop after the third published version or earlier on stop conditions

When committee review is required, the loop will now refuse to write a report or publish a version until `python3 .agent-loop/scripts/capture-review.py` has recorded matching review state for the active goal.

When the evaluator gate is enabled, the loop will also require a matching passing evaluator result for the active goal before implementation readiness, reporting, and publication. The explicit pre-implementation check is:

```bash
python3 .agent-loop/scripts/assert-implementation-readiness.py
```

## Data-First Workflow

This kit now assumes a data-first loop:

1. collect project data
2. score project-data quality
3. render the committee brief
4. research and challenge the scope through the councils
5. capture the scope decision and evaluator result
6. run implementation readiness
7. implement and validate
8. reflect, refresh data if the repo changed materially
9. report and publish

High-quality data does not require a package manager. Script-first repos can also reach `ready` if the snapshot captures direct automation signals such as `.agent-loop/scripts`, agent-skill directories, and the repo archetype.

Core commands:

```text
python3 .agent-loop/scripts/collect-project-data.py
python3 .agent-loop/scripts/score-data-quality.py
python3 .agent-loop/scripts/render-committee.py
python3 .agent-loop/scripts/assert-implementation-readiness.py
python3 .agent-loop/scripts/select-next-goal.py
python3 .agent-loop/scripts/run-full-validation.py
python3 .agent-loop/scripts/write-report.py
python3 .agent-loop/scripts/publish-iteration.py
```

## Under The Hood

The loop persists state in repo files:

- `.agent-loop/config.json`
- `.agent-loop/state.json`
- `.agent-loop/backlog.json`
- `PLANS.md`
- `docs/reports/`

Key scripts:

- `.agent-loop/scripts/set-loop-session.py`
- `.agent-loop/scripts/collect-project-data.py`
- `.agent-loop/scripts/score-data-quality.py`
- `.agent-loop/scripts/render-committee.py`
- `.agent-loop/scripts/assert-implementation-readiness.py`
- `.agent-loop/scripts/select-next-goal.py`
- `.agent-loop/scripts/run-full-validation.py`
- `.agent-loop/scripts/write-report.py`
- `.agent-loop/scripts/publish-iteration.py`

## Notes

- This kit is intentionally repo-local. It is designed to live inside the project that is being developed.
- The Codex and Claude wrappers share the same core protocol but present it in different styles.
- For public repositories, a project-specific README and real validation commands are still your responsibility.
