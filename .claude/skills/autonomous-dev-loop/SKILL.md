---
name: autonomous-dev-loop
description: Run a guarded autonomous software delivery loop with scoped version planning, implementation, full validation, Git publication, report writing, reflection, and next-goal selection. Use when the user asks Claude Code to autonomously iterate on a repo, keep shipping versions, continue to the next version, self-direct development, or do “自主循环开发” / “自动迭代开发”. Also use when the user only specifies a loop count in natural language, such as “循环3次”, “做5轮”, “来两轮”, “run 3 iterations”, or “ship 2 versions”. Treat that count-only request as a full autonomous loop launch in the current repo after reading PLANS.md and .agent-loop files.
---

# Autonomous Dev Loop

Use this skill to run a repo through repeated, test-gated versions. Keep durable state in files instead of relying on the conversation.

This skill follows `ReAct` in the paper sense from Shunyu Yao et al.: `Reason + Act`, not the frontend framework `React`.

<minimal_launch_mode>
If the user only says a loop count, treat that as sufficient to start.

Examples:
- 循环3次
- 来两轮
- 做 5 轮
- run 3 iterations
- ship 2 versions

In minimal launch mode, infer the rest of the workflow from this skill. Do not ask the user to restate the testing, report, Git, reflection, or stop requirements unless repo setup is missing.
</minimal_launch_mode>

<load_order>
Read these files before starting or resuming a loop:
1. ../../../PLANS.md
2. ../../../.agent-loop/config.json
3. ../../../.agent-loop/state.json
4. ../../../.agent-loop/backlog.json
5. ../../../.agent-loop/references/protocol.md
6. ../../../.agent-loop/references/prompting-guidelines.md
7. ../../../.agent-loop/references/react-reasoning-acting.md
</load_order>

Run `.agent-loop` state scripts sequentially. Do not parallelize goal selection, validation, report writing, or publishing.

<entry_gate>
Do not start implementation until all of these are true:
- PLANS.md states the current target, constraints, and open risks.
- .agent-loop/config.json contains real validation commands. The placeholder failing command must be replaced.
- The loop session target has been persisted with `python3 .agent-loop/scripts/set-loop-session.py --iterations N` when the user provided or implied a count.
- The repo has a valid Git publication strategy for this loop.
- The next version can be completed and validated in one iteration.
</entry_gate>

<iteration_loop>
Run this order exactly:
1. Analyze current state, target, recent reports, and backlog. Think deeply before acting.
2. If the user provided or implied a loop count and the session is not configured yet, run `python3 .agent-loop/scripts/set-loop-session.py --iterations N`.
3. Select one scoped version goal. Use `python3 .agent-loop/scripts/select-next-goal.py` unless the user fixed the goal.
4. Execute the version in short ReAct cycles: reason from evidence, take one concrete action, observe the result, then update the next action.
5. Implement the smallest coherent change set.
6. Add or update tests for the real behavior.
7. Run full validation with `python3 .agent-loop/scripts/run-full-validation.py`.
8. If validation fails, do not commit or push.
9. Write the report with `python3 .agent-loop/scripts/write-report.py`, including key observations.
10. Publish with `python3 .agent-loop/scripts/publish-iteration.py`.
11. Reflect in PLANS.md and .agent-loop/backlog.json, then decide whether another version should start.
</iteration_loop>

<non_negotiable_rules>
- Unless the user says otherwise, interpret a count-only launch as permission to run the full autonomous loop in the current repo.
- Think deeply before execution, especially before architectural changes, large edits, or high-cost commands.
- Never publish without a green full-validation run.
- Never publish without a report in docs/reports/.
- Never publish one project to another project's GitHub remote.
- If the current project's GitHub target is missing or unclear, stop and ask the user before publishing.
- Never broaden scope mid-iteration.
- Never use chat history as the only state.
- Never exceed the configured session iteration limit.
- Never hard-code behavior just to pass current tests.
- Stop and report when credentials, permissions, destructive actions, or conflicting requirements appear.
</non_negotiable_rules>

<operating_style>
- Keep chat updates short.
- Put evidence and reflection into repo files.
- Use deterministic scripts and exact commands whenever possible.
- Prefer one fully green version over a large partial rewrite.
</operating_style>

<references>
- Protocol: ../../../.agent-loop/references/protocol.md
- Prompting guidance: ../../../.agent-loop/references/prompting-guidelines.md
- ReAct guide: ../../../.agent-loop/references/react-reasoning-acting.md
- Report template: ../../../.agent-loop/templates/report-template.md
</references>
