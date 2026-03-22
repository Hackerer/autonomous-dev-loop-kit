---
name: autonomous-dev-loop
description: Run a guarded autonomous software delivery loop with scoped version planning, implementation, full validation, Git publication, report writing, reflection, and next-goal selection. Use when the user asks Claude Code to autonomously iterate on a target repo, keep shipping versions, continue to the next version, self-direct development, or do “自主循环开发” / “自动迭代开发”. Also use when the user only specifies a loop count in natural language, such as “循环3次”, “做5轮”, “来两轮”, “run 3 iterations”, or “ship 2 versions”. Treat that count-only request as a full autonomous loop launch for the active target repository after reading PLANS.md and .agent-loop files.
---

# Autonomous Dev Loop

Use this skill when the user wants repeated, test-gated delivery for the active target repository. This is a thin entry point: keep durable state in the kit workspace under `docs/projects/<project-id>/`, and read the references for the full protocol rather than re-deriving it in chat.

## Start Here

- If the user only gives a loop count, treat that as permission to run the full autonomous loop for the active target repository.
- Read `PLANS.md`, `.agent-loop/config.json`, `.agent-loop/state.json`, and `.agent-loop/backlog.json` before acting.
- If any required file is missing, initialize it from this kit before starting autonomous work.
- If the target repo is external to the kit workspace, set `AUTONOMOUS_DEV_LOOP_TARGET=/path/to/project` before invoking the scripts.
- Use `.agent-loop/scripts` sequentially. Do not parallelize goal selection, validation, report writing, or publishing.
- Define the next bundled release before selecting a task goal.
- Treat the selected task as a candidate against the current promoted base. If the experiment layer is enabled, the candidate must beat base before publish.
- Keep all durable reasoning in repo files. Do not rely on chat history as the only state.

## Hard Gates

Do not start implementation until all of these are true:

- `PLANS.md` states the current target, constraints, and open risks.
- `.agent-loop/config.json` contains real validation commands and a valid committee definition.
- The loop session target has been persisted when the user provided or implied a count.
- The Git publication target for the active target repository is explicit and local to that project.
- The next bundled release has been defined, and each included task still fits in one iteration.

## Iteration Outline

1. Analyze repo state, recent reports, and backlog.
2. Collect and score project data if stale or missing.
3. Render committee context and do explicit research.
4. Capture committee review and scope decision.
5. Capture evaluator result and implementation readiness.
6. Implement the smallest coherent change set.
7. Add or update tests.
8. Run full validation.
9. Reflect on research and committee feedback.
10. Write the task report.
11. Publish the iteration.
12. When the bundled release is complete, write and publish the release report.
13. Update `PLANS.md` and `backlog.json` for the next step.

## Safety Rules

- Never publish without green validation.
- Never write a report without the matching durable review state.
- Never publish to another project's GitHub remote.
- Stop if the active target repository's GitHub target is unclear before publishing.
- Stop if the Git target is unclear, validation is red, or requirements conflict.

## References

- Protocol: `../../../.agent-loop/references/protocol.md`
- Committee: `../../../.agent-loop/references/committee-driven-delivery.md`
- Prompting: `../../../.agent-loop/references/prompting-guidelines.md`
- ReAct: `../../../.agent-loop/references/react-reasoning-acting.md`
- Data quality: `../../../.agent-loop/references/data-quality-acquisition.md`
- Example workflow: `../../../.agent-loop/references/example-data-acquisition-workflow.md`
- Report template: `../../../.agent-loop/templates/report-template.md`
- Project data template: `../../../.agent-loop/templates/project-data-template.json`

## Trigger Examples

- `循环3次`
- `来两轮`
- `做 5 轮`
- `run 3 iterations`
- `ship 2 versions`
