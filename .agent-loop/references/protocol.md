# Autonomous Dev Loop Protocol

## Purpose

Use this protocol when the user wants repeated, self-directed software delivery instead of a single edit. The protocol is designed to maximize delivery quality by separating durable state from the chat and by making every bundled release pass explicit gates.

This protocol uses `ReAct` in the sense of the Shunyu Yao et al. paper, `Reason + Act`, not the frontend framework `React`.

## Required Artifacts

- `PLANS.md`
- `.agent-loop/config.json`
- `.agent-loop/state.json`
- `.agent-loop/backlog.json`
- `.agent-loop/references/data-quality-acquisition.md`
- `.agent-loop/references/committee-driven-delivery.md`
- `.agent-loop/templates/project-data-template.json`
- `.agent-loop/data/project-data.json` when collected
- `.agent-loop/data/data-quality.json` when scored
- `docs/reports/`
- `docs/releases/`

Do not rely on the conversation as the only source of truth.

Run `.agent-loop/scripts/*.py` sequentially. They share `.agent-loop/state.json` and should not be launched in parallel.

## Entry Conditions

Before the first autonomous iteration in a repo, confirm:

1. `PLANS.md` explains the target outcome, constraints, and open risks.
2. `.agent-loop/config.json` contains the real validation commands for this repo.
3. The loop session has a persisted bundled-release limit. Run `python3 .agent-loop/scripts/set-loop-session.py --iterations N`.
4. The Git strategy is explicit: `push-branch`, `direct-push`, or `commit-only`.
5. The discovery and committee settings in `.agent-loop/config.json` require research, committee review, and post-validation reflection.
6. The next bundled release has been defined before task selection, and each task inside it is still small enough to implement and validate in one iteration.

If any condition is missing, create or update the artifacts before attempting autonomous delivery.

## State Machine

Every bundled release is delivered through repeated task iterations plus one release closeout:

1. `analyze`
   - Review current repo state, recent reports, current branch, open risks, and remaining backlog.
   - Reconcile what exists now against the target outcome in `PLANS.md`.
   - Do a silent deep-thinking pass before acting: identify assumptions, unknowns, risks, and the smallest next high-signal action.
   - If data quality is unclear, consult `.agent-loop/references/data-quality-acquisition.md` and gather missing signals before editing.
   - Prefer using `.agent-loop/state.json` to locate the latest project-data snapshot and quality assessment instead of reconstructing that state from chat memory.
   - If project data is missing, stale, or low-confidence, run:
     - `python3 .agent-loop/scripts/collect-project-data.py`
     - `python3 .agent-loop/scripts/score-data-quality.py`
2. `research`
   - Perform explicit pre-goal research using repo files, tests, generated artifacts, recent reports, and product context.
   - Meet the configured minimum research inputs before choosing a goal.
   - Capture only concise research conclusions that materially affect scope or risk.
3. `committee-review`
   - Run `python3 .agent-loop/scripts/render-committee.py` to restate the configured committees.
   - Challenge the candidate version through all configured roles:
     - product manager committee
     - technical architect committee
     - user committee
   - Narrow or reject the candidate if the committee exposes unclear value, design risk, or user friction.
   - Persist concise research findings, committee feedback, and scope decisions with `python3 .agent-loop/scripts/capture-review.py`.
   - Treat the persisted review state as goal-aware: later steps may reuse it automatically only when the captured goal matches the active goal.
4. `release-plan`
   - Define the next bundled release before selecting tasks.
   - Use `python3 .agent-loop/scripts/plan-release.py` to bundle multiple pending goals into one user-facing release.
   - The loop count provided by the user refers to bundled releases, not tiny task commits.
5. `select`
   - Choose exactly one scoped task goal from the active bundled release.
   - Favor the smallest task that materially advances the target while remaining fully testable.
   - Refuse goal selection when project-data quality is insufficient or when the research gate explicitly says more context is required.
   - Refuse to start a new bundled release if the configured session limit has already been reached.
6. `implementation-readiness`
   - Record the scope decision and evaluator result in durable state.
   - Run `python3 .agent-loop/scripts/assert-implementation-readiness.py`.
   - Refuse to start implementation if committee review is required but the active goal lacks a matching passing evaluator result.
7. `implement`
   - Use short ReAct cycles inside implementation:
     - reason from the current evidence
     - take one concrete action
     - observe the result
     - update the next action
   - Make the minimum coherent code change.
   - Update or add tests for the real behavior.
8. `validate`
   - Run the full configured validation suite.
   - No publish step is allowed if validation is red.
9. `reflect`
   - Reflect on what the research and committee review got right, wrong, or incomplete after seeing validation results.
   - Update the next-step recommendation based on the new evidence.
10. `report`
   - Write a task-iteration report in `docs/reports/`.
   - Prefer the durable review state in `.agent-loop/state.json` for research, committee feedback, decisions, and reflection when it matches the active goal.
   - Refuse to write the report if committee review is required but no matching recorded review state exists yet.
   - Refuse to write the report if evaluator pass is required but no matching passing evaluator result exists yet.
   - Surface open gaps, stop conditions, and escalation status from durable state so a later operator can see why the loop stopped, would stop, or should escalate.
   - Record the research findings, committee feedback, goal, key observations, delivered behavior, validation evidence, reflection, and a proposed next task.
11. `publish`
   - Commit the complete task iteration.
   - Refuse to publish if committee review is required but no matching recorded review state exists for the draft goal.
   - Refuse to publish if evaluator pass is required but no matching passing evaluator result exists for the draft goal.
   - Push or otherwise publish according to config.
12. `release-closeout`
   - When every planned task in the active bundled release is published, write a detailed release report in `docs/releases/`.
   - The release report must explain what the bundled demand delivered, whether technical validation passed, and the detailed output across the included task iterations.
   - Publish the bundled release with `python3 .agent-loop/scripts/publish-release.py`.
13. `loop-reflect`
   - Update `PLANS.md` and `.agent-loop/backlog.json`.
   - Decide whether the next version should start or whether the loop should stop.

## Release Gate

A bundled release is publishable only if all of these are true:

- The scoped goal is completed or explicitly narrowed and explained in the report.
- A recorded `review_state` exists for the active goal when committee review is required.
- A passing evaluator result exists for the active goal when evaluator pass is required.
- The configured full-validation suite passes.
- Task reports exist in `docs/reports/` for the included task iterations.
- A bundled release report exists in `docs/releases/`.
- The worktree state being published is intentional and understood.

## Report Requirements

Every task report must include:

- Iteration number
- Date
- Current state analysis
- Research performed before goal selection
- Committee feedback and decision
- Version goal
- Key observations from execution
- Evidence sources
- Data quality status
- Delivered behavior
- Full validation evidence
- Reflection on requirements and architecture
- Proposed next task

Every bundled release report must include:

- Release number
- Release title and summary
- The bundled goals or features included in the release
- What the demand specifically delivered
- Technical validation status
- Detailed output notes across the included task iterations
- Traceability back to the task reports

Keep the report factual. Do not hide regressions or open risks. Store concise conclusions and observations, not verbose hidden reasoning traces.

## Git Policy

Treat Git as the durable release log for completed versions.

- `push-branch`
  - Create or reuse a branch with the configured prefix.
  - Push the branch after the version commit succeeds.
- `direct-push`
  - Push the current branch only when the user has explicitly accepted that workflow.
- `commit-only`
  - Create the version commit locally and stop before network publication.

Git publication must always target the current project's own GitHub repository, using the remote configured in that project.

- Do not reuse a remote from another project.
- Do not infer a publication target from memory of prior repos.
- If the current project's remote is missing, non-GitHub, or otherwise unclear, stop and ask the user before publishing.

Never publish an unvalidated version.

## Stop Conditions

Stop and report instead of continuing when any of the following is true:

- Requirements conflict or materially changed mid-iteration
- Credentials, secrets, or external access are missing
- The next action is destructive or high-risk
- Validation has failed repeatedly and the root cause is not yet understood
- The configured session release limit has been reached
- The current project's GitHub publication target is unclear
- No remaining task has a clear, high-value, testable scope

## Scope Discipline

Autonomous loops degrade when scope expands inside the same version.

- Finish one version before selecting another.
- Do not mix refactors, feature growth, and infra churn unless the repo genuinely requires all of them for the same acceptance gate.
- Prefer incremental, auditable progress over ambitious rewrites.

## ReAct Execution Rules

- Think deeply before high-cost actions, but keep that reasoning concise in external artifacts.
- If evidence is missing, inspect or test before editing.
- After each meaningful command, test, or code change, observe the result and update the plan.
- If observations contradict the prior plan, revise the plan before taking the next action.
- Prefer many small evidence-backed actions over one large speculative rewrite.
- Use the evidence hierarchy and freshness rules in `.agent-loop/references/data-quality-acquisition.md` when deciding whether current project data is good enough.
- Use `.agent-loop/references/committee-driven-delivery.md` when reconciling product, architecture, and user objections before implementation.

## Cross-CLI Notes

- Codex performs best with short, hard constraints and repo-based state.
- Claude performs best when the same protocol is presented with explicit structure.
- Keep the core protocol the same across CLIs. Change wrapper style, not release criteria.

## Example Workflow

See `.agent-loop/references/example-data-acquisition-workflow.md` for a concrete sequence that starts from a count-only launch.
