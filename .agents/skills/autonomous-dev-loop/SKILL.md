---
name: autonomous-dev-loop
description: Run a guarded autonomous software delivery loop with scoped version planning, implementation, full validation, Git publication, report writing, reflection, and next-goal selection. Use when the user asks Codex to autonomously iterate on a repo, keep shipping versions, continue to the next version, self-direct development, or do “自主循环开发” / “自动迭代开发”. Also use when the user only specifies a loop count in natural language, such as “循环3次”, “做5轮”, “来两轮”, “run 3 iterations”, or “ship 2 versions”. Treat that count-only request as a full autonomous loop launch in the current repo after reading PLANS.md and .agent-loop files.
---

# Autonomous Dev Loop

## Overview

Use this skill to drive a repo through repeated, test-gated bundled releases instead of one-off edits. Keep the chat concise and store durable reasoning in repo files so the loop can survive context loss and handoffs.

This skill follows `ReAct` in the paper sense from Shunyu Yao et al.: `Reason + Act`, not the frontend framework `React`.

## Minimal Launch Mode

If the user only says a loop count, treat that as sufficient to start.

Examples:

- `循环3次`
- `来两轮`
- `做 5 轮`
- `run 3 iterations`
- `ship 2 versions`

In minimal launch mode, infer the rest of the workflow from this skill. Do not ask the user to restate the testing, report, Git, reflection, or stop requirements unless repo setup is missing.

## Load Order

Read these files before the first iteration of a session:

1. `../../../PLANS.md`
2. `../../../.agent-loop/config.json`
3. `../../../.agent-loop/state.json`
4. `../../../.agent-loop/backlog.json`
5. `../../../.agent-loop/references/protocol.md`
6. `../../../.agent-loop/references/prompting-guidelines.md`
7. `../../../.agent-loop/references/react-reasoning-acting.md`
8. `../../../.agent-loop/references/data-quality-acquisition.md`
9. `../../../.agent-loop/references/committee-driven-delivery.md`
10. `../../../.agent-loop/references/example-data-acquisition-workflow.md`

If any file is missing, initialize it from this kit before starting autonomous work.

Run `.agent-loop` state scripts sequentially. Do not parallelize goal selection, validation, report writing, or publishing.

## Entry Gate

Before the first implementation step, verify all of the following:

- `PLANS.md` states the current product outcome, constraints, and open risks.
- `.agent-loop/config.json` contains real validation commands. The placeholder failing command must be replaced.
- `.agent-loop/config.json` contains a valid committee definition for product-manager, technical-architect, and user review.
- The loop session target has been persisted with `python3 .agent-loop/scripts/set-loop-session.py --iterations N` when the user provided or implied a count.
- The repo has a usable Git strategy for this loop.
- The next bundled release has been defined before task selection, and each included task can still be scoped small enough to implement and validate in one iteration.

If any gate fails, stop and report the missing setup instead of improvising around it.

## Iteration Loop

For each iteration, follow this exact order:

1. Analyze the current repo state, the stated target, recent reports, and the backlog. Think deeply before acting.
2. If the user provided or implied a loop count and the session is not configured yet, run `python3 .agent-loop/scripts/set-loop-session.py --iterations N`.
3. If project data is missing, stale, or low-quality, run `python3 .agent-loop/scripts/collect-project-data.py` and `python3 .agent-loop/scripts/score-data-quality.py`.
4. Run `python3 .agent-loop/scripts/render-committee.py`, do explicit research, and challenge the candidate scope through the product-manager, technical-architect, and user committees.
5. If research still says the repo lacks enough context, record that explicitly with `python3 .agent-loop/scripts/capture-review.py --research-status need_more_context ...` and stop goal selection until the missing context is gathered.
6. Define the next bundled release first with `python3 .agent-loop/scripts/plan-release.py`, then select exactly one scoped task goal from that release with `python3 .agent-loop/scripts/select-next-goal.py` unless the user has already fixed the goal.
7. Capture the scope decision, render the independent evaluator input with `python3 .agent-loop/scripts/render-evaluator-brief.py`, then capture the evaluator result and run `python3 .agent-loop/scripts/assert-implementation-readiness.py`. Do not implement if it fails.
8. Execute the version in short ReAct cycles: reason from evidence, take one concrete action, observe the result, then update the next action.
9. Implement the smallest coherent change set that satisfies the chosen goal.
10. Add or update tests so the change is verified by the repo's real validation suite.
11. Run full validation with `python3 .agent-loop/scripts/run-full-validation.py`.
12. If validation fails, do not commit or push. Fix the issue or stop with a blocker report.
13. Run `python3 .agent-loop/scripts/assess-escalation.py` when validation, evaluator review, or repeated goal churn suggests the loop may need to watch or escalate.
14. Reflect on what the research and committee review got right, wrong, or incomplete.
15. Refresh project data if the repo changed materially, then write the task-iteration report with `python3 .agent-loop/scripts/write-report.py`, including research findings, committee observations, and stop/escalation signals.
16. Publish the iteration with `python3 .agent-loop/scripts/publish-iteration.py`.
17. When all planned tasks for the active release are published, write the bundled release report with `python3 .agent-loop/scripts/write-release-report.py` and publish it with `python3 .agent-loop/scripts/publish-release.py`.
18. Reflect in `PLANS.md` and `.agent-loop/backlog.json`, then decide whether another high-value bundled release should start.

## Non-Negotiable Rules

- Unless the user says otherwise, interpret a count-only launch as permission to run the full autonomous loop in the current repo.
- Think deeply before execution, especially before architectural changes, large edits, or high-cost commands.
- Never skip research or committee review when the config requires them.
- Never publish a version without a green full-validation run from the configured commands.
- Never publish a task iteration without a report file in `docs/reports/`.
- Never publish a bundled release without a detailed release report in `docs/releases/`.
- Never publish one project to another project's GitHub remote.
- If the current project's GitHub target is missing or unclear, stop and ask the user before publishing.
- Never broaden scope mid-iteration. Finish one version, then reassess.
- Never rely on chat history as the only state. Persist decisions in repo files.
- Never exceed the configured session release limit.
- Never optimize for passing tests by hard-coding or adding brittle special cases.
- Never push a risky or destructive change without explicit user approval.

## Operating Style

- Keep user-facing progress updates short.
- Store the detailed plan, evidence, and reflection in repo files.
- Prefer precise commands and deterministic scripts over free-form prose.
- Use Git as the durable audit log for completed versions.

## References

- Protocol: `../../../.agent-loop/references/protocol.md`
- Prompting guidance: `../../../.agent-loop/references/prompting-guidelines.md`
- ReAct guide: `../../../.agent-loop/references/react-reasoning-acting.md`
- Data quality guide: `../../../.agent-loop/references/data-quality-acquisition.md`
- Committee guide: `../../../.agent-loop/references/committee-driven-delivery.md`
- Example workflow: `../../../.agent-loop/references/example-data-acquisition-workflow.md`
- Project data template: `../../../.agent-loop/templates/project-data-template.json`
- Report template: `../../../.agent-loop/templates/report-template.md`

## Typical Trigger Phrases

- “循环3次”
- “来两轮”
- “做 5 轮”
- “自主循环开发”
- “自动迭代开发”
- “开始循环 3 次”
- “按 ReAct 循环 3 次”
- “继续下一个版本，完整测试后提交 GitHub”
- “run 3 iterations”
- “ship 2 versions”
- “Keep shipping versions until the backlog is exhausted”
- “Run a self-directed loop with reports after every version”
