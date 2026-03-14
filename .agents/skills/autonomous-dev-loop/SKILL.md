---
name: autonomous-dev-loop
description: Run a guarded autonomous software delivery loop with scoped version planning, implementation, full validation, Git publication, report writing, reflection, and next-goal selection. Use when the user asks Codex to autonomously iterate on a repo, keep shipping versions, continue to the next version, self-direct development, or do “自主循环开发” / “自动迭代开发”. Also use when the user only specifies a loop count in natural language, such as “循环3次”, “做5轮”, “来两轮”, “run 3 iterations”, or “ship 2 versions”. Treat that count-only request as a full autonomous loop launch in the current repo after reading PLANS.md and .agent-loop files.
---

# Autonomous Dev Loop

## Overview

Use this skill to drive a repo through repeated, test-gated versions instead of one-off edits. Keep the chat concise and store durable reasoning in repo files so the loop can survive context loss and handoffs.

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

If any file is missing, initialize it from this kit before starting autonomous work.

Run `.agent-loop` state scripts sequentially. Do not parallelize goal selection, validation, report writing, or publishing.

## Entry Gate

Before the first implementation step, verify all of the following:

- `PLANS.md` states the current product outcome, constraints, and open risks.
- `.agent-loop/config.json` contains real validation commands. The placeholder failing command must be replaced.
- The loop session target has been persisted with `python3 .agent-loop/scripts/set-loop-session.py --iterations N` when the user provided or implied a count.
- The repo has a usable Git strategy for this loop.
- The next version can be scoped small enough to implement and validate in one iteration.

If any gate fails, stop and report the missing setup instead of improvising around it.

## Iteration Loop

For each iteration, follow this exact order:

1. Analyze the current repo state, the stated target, recent reports, and the backlog. Think deeply before acting.
2. If the user provided or implied a loop count and the session is not configured yet, run `python3 .agent-loop/scripts/set-loop-session.py --iterations N`.
3. Select exactly one scoped version goal. Use `python3 .agent-loop/scripts/select-next-goal.py` unless the user has already fixed the goal.
4. Execute the version in short ReAct cycles: reason from evidence, take one concrete action, observe the result, then update the next action.
5. Implement the smallest coherent change set that satisfies the chosen goal.
6. Add or update tests so the change is verified by the repo's real validation suite.
7. Run full validation with `python3 .agent-loop/scripts/run-full-validation.py`.
8. If validation fails, do not commit or push. Fix the issue or stop with a blocker report.
9. Write the version report with `python3 .agent-loop/scripts/write-report.py`, including key observations.
10. Publish the iteration with `python3 .agent-loop/scripts/publish-iteration.py`.
11. Reflect in `PLANS.md` and `.agent-loop/backlog.json`, then decide whether another high-value version should start.

## Non-Negotiable Rules

- Unless the user says otherwise, interpret a count-only launch as permission to run the full autonomous loop in the current repo.
- Think deeply before execution, especially before architectural changes, large edits, or high-cost commands.
- Never publish a version without a green full-validation run from the configured commands.
- Never publish a version without a report file in `docs/reports/`.
- Never publish one project to another project's GitHub remote.
- If the current project's GitHub target is missing or unclear, stop and ask the user before publishing.
- Never broaden scope mid-iteration. Finish one version, then reassess.
- Never rely on chat history as the only state. Persist decisions in repo files.
- Never exceed the configured session iteration limit.
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
