# autonomous-dev-loop-kit

A cross-CLI autonomous development loop kit for:

- Codex CLI
- Claude Code CLI

The kit lets you start an autonomous multi-release development session with a minimal user command such as:

```text
循环3次
```

or:

```text
按 ReAct 循环3次
```

`ReAct` here means the paper pattern from Shunyu Yao et al., `Reason + Act`, not the frontend framework `React`.

## Committee-Driven Release Model

Each task iteration now enforces:

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

And once a scope decision exists for the active goal, the repo can render the independent evaluator input contract with:

```bash
python3 .agent-loop/scripts/render-evaluator-brief.py
```

## What It Enforces

For every bundled release, the loop requires:

- explicit release definition before task selection
- multiple scoped goals bundled into one user-facing release
- a PM-style release brief with objective, user value, why-now logic, scope boundaries, and release acceptance
- one scoped task goal at a time during implementation
- deep analysis before execution
- short reason -> act -> observe -> update cycles
- full validation before publication
- task reports in `docs/reports/`
- a detailed release report in `docs/releases/`
- Git publication for the current project at both task and release closeout
- reflection before the next release starts

The session stops automatically when the requested bundled release count is reached or when a configured stop condition is hit.

## Current Baseline

The current lightweight committee V2 baseline includes:

- research blocking when project-data quality is insufficient or review state says `need_more_context`
- Product, Architecture, and Operator councils plus secretariat and independent evaluator roles
- lightweight repo archetype profiles that can tune quality expectations and committee emphasis
- a live committee review packet that includes the active goal, quality context, and recent repo evidence
- explicit delivery and audit secretary summaries in durable state, project snapshots, and reports
- a dedicated evaluator brief before readiness checks
- a deterministic evaluator score helper driven by the committed rubric
- configurable implementation readiness gate mode while keeping report and publish safety strict
- evaluator-pass gating remains strict for reporting and publication
- bundled release planning before task selection
- PM-driven release briefs for bundled release planning
- detailed release closeout reports that aggregate what the included task iterations delivered
- repo-local usage logs for install, session start/extension, and published iterations
- stop and escalation assessment plus report rendering
- goal-bound review-state capture and non-destructive session continuation

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
docs/releases/
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

After installation, the target repo bootstrap should follow the same lightweight V2 flow:

```bash
# Review the defaults you want for this repo first:
# - discovery.archetype_profiles
# - committee.evaluator.implementation_gate_mode
python3 .agent-loop/scripts/collect-project-data.py
python3 .agent-loop/scripts/score-data-quality.py
python3 .agent-loop/scripts/plan-release.py
python3 .agent-loop/scripts/render-committee.py
python3 .agent-loop/scripts/render-evaluator-brief.py
python3 .agent-loop/scripts/score-evaluator-readiness.py --score goal_clarity=4.0 --score scope_fitness=4.0 --score repo_safety=4.0 --score validation_readiness=4.0 --score state_durability=4.0 --score publish_safety=4.0
python3 .agent-loop/scripts/assert-implementation-readiness.py
```

`implementation_gate_mode=advisory` can allow implementation to start with a warning, but report and publish still require evaluator pass.

When all tasks in the active release are published, close out the bundled release with:

```bash
python3 .agent-loop/scripts/write-release-report.py
python3 .agent-loop/scripts/publish-release.py
```

The installed kit also records lightweight usage logs in:

```text
.agent-loop/data/usage-log.jsonl
```

You can summarize one or more repos with:

```bash
python3 .agent-loop/scripts/analyze-usage-logs.py
python3 .agent-loop/scripts/analyze-usage-logs.py --repo /path/to/ai-trade --repo /path/to/info-rss
```

If research is still insufficient before goal selection, record that explicitly instead of pushing ahead:

```bash
python3 .agent-loop/scripts/capture-review.py --research-status need_more_context --research-summary "..." --open-gap "..."
```

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

Reports should also surface durable open gaps, stop conditions, and escalation status so later operators can see why a version was blocked, risky, or one step away from escalation.

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

High-quality data does not require a package manager. Script-first repos can also reach `ready` if the snapshot captures direct automation signals such as `.agent-loop/scripts`, agent-skill directories, and the repo archetype. The config can now map those repo archetypes to lightweight profile defaults, and `score-data-quality.py` will evaluate the active profile's required signals instead of assuming one generic expectation for every project.

Core commands:

```text
python3 .agent-loop/scripts/collect-project-data.py
python3 .agent-loop/scripts/score-data-quality.py
python3 .agent-loop/scripts/render-committee.py
python3 .agent-loop/scripts/render-evaluator-brief.py
python3 .agent-loop/scripts/score-evaluator-readiness.py --score goal_clarity=4.5 --score scope_fitness=4.5 --score repo_safety=4.5 --score validation_readiness=4.5 --score state_durability=4.5 --score publish_safety=4.5
python3 .agent-loop/scripts/assert-implementation-readiness.py
python3 .agent-loop/scripts/continue-loop-session.py --add 5
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
- `.agent-loop/scripts/render-evaluator-brief.py`
- `.agent-loop/scripts/assert-implementation-readiness.py`
- `.agent-loop/scripts/continue-loop-session.py`
- `.agent-loop/scripts/select-next-goal.py`
- `.agent-loop/scripts/run-full-validation.py`
- `.agent-loop/scripts/write-report.py`
- `.agent-loop/scripts/publish-iteration.py`

## Notes

- This kit is intentionally repo-local. It is designed to live inside the project that is being developed.
- The Codex and Claude wrappers share the same core protocol but present it in different styles.
- For public repositories, a project-specific README and real validation commands are still your responsibility.
