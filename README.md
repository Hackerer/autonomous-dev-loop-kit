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
- task reports in the active project workspace under `docs/projects/<project-id>/docs/reports/`
- a detailed release report in `docs/projects/<project-id>/docs/releases/`
- Git publication for the active target repository at both task and release closeout
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
- an opt-in experiment layer that treats each version as a candidate against a durable base and only promotes improvements
- bundled release planning before task selection
- PM-driven release briefs for bundled release planning
- detailed release closeout reports that aggregate what the included task iterations delivered
- per-project usage logs, reports, and release records stored under `docs/projects/<project-id>/`
- stop and escalation assessment plus report rendering
- goal-bound review-state capture and non-destructive session continuation

## Safety Rules

- Each project must publish to its own GitHub repository.
- If the active target repository's GitHub remote is missing or unclear, the agent should stop and ask before publishing.
- The loop should never push one project to another project's remote.

## Repository Layout

```text
.agents/skills/autonomous-dev-loop/
.claude/skills/autonomous-dev-loop/
.agent-loop/
AGENTS.md
CLAUDE.md
PLANS.md
docs/projects/
```

## Install Into A Project

Register the target project without copying kit assets into it. The installer records project-specific state, logs, and reports inside the kit workspace under `docs/projects/<project-id>/`.

```bash
./scripts/install-into-project.sh --target /path/to/project
```

After registration, replace the placeholder validation command in the kit workspace config for that project with the real commands, for example:

- lint
- typecheck
- unit test
- integration test
- build
- e2e

Do not leave the placeholder validation step in place for real use.

Also customize the committee members in the kit workspace config if the default product-manager, technical-architect, and user personas do not match the target project.

## Install Into A Target Project

To register a project as a target for the committee-driven kit, run:

```bash
./scripts/install-into-project.sh --target /path/to/project
```

The installer does not copy kit assets or scripts into the target project. It records the target path in the per-project workspace under `docs/projects/<project-id>/`.

When all tasks in the active release are published, close out the bundled release with:

```bash
python3 .agent-loop/scripts/write-release-report.py
python3 .agent-loop/scripts/publish-release.py
```

The kit records lightweight usage logs in the kit workspace, with one project folder per target under `docs/projects/`. The registry that maps targets to project folders lives at `docs/projects/index.json`:

```text
docs/projects/<project-id>/.agent-loop/data/usage-log.jsonl
```

If you are operating on an external repository from the kit workspace, set the target explicitly before running the scripts:

```bash
export AUTONOMOUS_DEV_LOOP_TARGET=/path/to/project
python3 .agent-loop/scripts/loop-status.py
```

If you need to redirect the kit workspace itself for a test harness, set `AUTONOMOUS_DEV_LOOP_WORKSPACE=/path/to/workspace` as an explicit override. The default remains the kit repository's own `docs/projects/<project-id>/` tree.

You can summarize one or more repos with:

```bash
python3 .agent-loop/scripts/analyze-usage-logs.py
python3 .agent-loop/scripts/analyze-usage-logs.py --repo /path/to/ai-trade --repo /path/to/info-rss
```

To inspect the live loop state or diagnose common blockers, use:

```bash
python3 .agent-loop/scripts/loop-status.py
python3 .agent-loop/scripts/loop-doctor.py
```

If research is still insufficient before goal selection, record that explicitly instead of pushing ahead:

```bash
python3 .agent-loop/scripts/capture-review.py --research-status need_more_context --research-summary "..." --open-gap "..."
```

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

- start the autonomous loop for the active target repository
- persist the session target as 3 iterations
- run one version at a time
- validate every version fully
- write a report for every version in the kit workspace project folder
- publish every version to the active target repository's own GitHub repo
- stop after the third published version or earlier on stop conditions

When committee review is required, the loop will now refuse to write a report or publish a version until `python3 .agent-loop/scripts/capture-review.py` has recorded matching review state for the active goal.

When the evaluator gate is enabled, the loop will also require a matching passing evaluator result for the active goal before implementation readiness, reporting, and publication. The explicit pre-implementation check is:

```bash
python3 .agent-loop/scripts/assert-implementation-readiness.py
```

Reports should also surface durable open gaps, stop conditions, and escalation status so later operators can see why a version was blocked, risky, or one step away from escalation.

When a loop feels stuck, prefer checking `loop-status.py` first and `loop-doctor.py` second before editing state manually.

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

The loop persists kit-controlled state in the per-project workspace:

- `.agent-loop/config.json`
- `.agent-loop/state.json`
- `.agent-loop/backlog.json`
- `PLANS.md`
- `docs/projects/<project-id>/`

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

- This kit is intentionally workspace-local. It is designed to live in the kit repository and control one or more target projects through per-project folders under `docs/projects/`.
- The Codex and Claude wrappers share the same core protocol but present it in different styles.
- For public repositories, a project-specific README and real validation commands are still your responsibility.
