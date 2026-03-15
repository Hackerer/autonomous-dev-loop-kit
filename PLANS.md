# Autonomous Loop Plan

Updated: 2026-03-15

## Target Outcome

- Turn `autonomous-dev-loop-kit` into a stronger cross-CLI kit that gathers high-quality project data and context before acting, then challenges each version through committee-driven review.
- Make high-quality data acquisition and committee-driven requirement review first-class parts of the loop, not implicit side effects.
- Keep the kit usable from minimal prompts such as `循环10`, while preserving strict validation, reporting, and Git publication rules.
- Strengthen the lightweight committee baseline with archetype-aware data-quality thresholds, richer review packets, explicit secretariat artifacts, and more usable evaluator/readiness tooling without turning the kit into heavyweight enterprise process.

## Current State

- The repo already contains Codex and Claude wrappers, loop scripts, ReAct guidance, committee-driven review config, and a public README.
- The repo now has explicit project-data acquisition, evidence schema, scoring, and committee configuration for pre-implementation challenge.
- The loop now stores research and committee review conclusions in durable state and can flow that review context back into collected project data and report generation.
- The repo now has a repo-local installer path for target projects while preserving target-specific loop config by default.
- The loop now enforces matching review-state capture before report writing and publication when committee review is required.
- The committee layer is now a lightweight V2 baseline with councils, secretariat, evaluator briefs, readiness gating, escalation assessment, stop-and-escalation reporting, and goal-bound review-state capture.
- The committee layer now also includes archetype-aware quality profiles, live review packets, explicit secretariat durability and visibility, evaluator score helpers, and configurable implementation readiness mode with strict report/publish safety.
- The repo now supports non-destructive session continuation for longer autonomous runs.
- The installer, example workflow, and entrypoint skills now point to the same research-gated, evaluator-aware lightweight committee V2 flow.
- Target repos still need repository-specific validation commands instead of the placeholder validation step when installed from this kit.
- Published versions should continue to stay small, testable, and directly connected to better pre-execution data quality, committee review quality, or operator clarity.
- The next session should deepen the lightweight baseline rather than replace it: improve context packing, make some quality gates archetype-aware, expose secretariat output more clearly, and keep readiness results easier to understand.

## Non-Negotiable Constraints

- Keep the core protocol shared across Codex CLI and Claude Code CLI.
- Use ReAct in the Shunyu Yao paper sense: reason, act, observe, update.
- Do not require verbose chain-of-thought in user-visible chat.
- Every published version must pass real validation, write a report, and publish to this repo's own GitHub remote.
- Favor deterministic scripts and durable repo state over purely prompt-based behavior.

## Acceptance Gates

- Before the session starts, persist the requested loop count with `python3 .agent-loop/scripts/set-loop-session.py --iterations N`.
- Every version must pass the commands configured in `.agent-loop/config.json`.
- Every version must produce a report in `docs/reports/`.
- Every version must be committed and published according to the configured Git strategy.
- Every version must improve either project-data acquisition quality, data-driven decision quality, or the visibility of those mechanisms.

## Decision Log

- 2026-03-14: Initialize the autonomous dev loop kit.
- 2026-03-14: Publish the repo to `https://github.com/Hackerer/autonomous-dev-loop-kit`.
- 2026-03-14: Use this repo itself as the first real autonomous loop target.
- 2026-03-14: Interpret "high-quality data acquisition" as higher-quality project and evidence gathering before code changes and publication decisions.
- 2026-03-15: Add committee-driven research and review using product-manager, technical-architect, and user councils.
- 2026-03-15: Start storing research and committee review conclusions as durable loop state instead of report-only output.
- 2026-03-15: Reuse goal-matched review state automatically in project snapshots and version reports.
- 2026-03-15: Add a repo-local installer that seeds target projects without overwriting their loop config by default.
- 2026-03-15: Make matching review-state capture a hard gate for report writing and publication.
- 2026-03-15: Start a lighter-weight committee V2 roadmap focused on structured councils, scope decisions, dissent, evaluator scoring, and escalation without overloading the kit.
- 2026-03-15: Finish the lightweight committee V2 baseline with research blocking, evaluator briefs, escalation assessment, stop-and-escalation reporting, session continuation, aligned installer guidance, and goal-bound review resets.
- 2026-03-15: Start the next committee session with a lighter-weight enhancement track focused on archetype-aware thresholds, richer review packets, explicit secretariat artifacts, and better evaluator ergonomics.
- 2026-03-15: Extend the lightweight baseline with archetype-aware quality scoring, live review packets, explicit secretariat visibility, deterministic evaluator scoring, configurable implementation readiness mode, and aligned bootstrap guidance.

## Backlog Notes

- Keep `.agent-loop/backlog.json` aligned with this plan.
- Prefer small, testable items over large rewrites.
- Prioritize improvements that increase evidence quality and committee challenge quality before implementation quality.
- Preserve backward compatibility where practical so target repositories can adopt the stronger committee model incrementally.
- Treat the current lightweight committee V2 baseline as the default starting point for future sessions rather than an experimental branch of the protocol.
- Keep committee upgrades compact and explicit: prefer one new durable artifact or one new gate behavior per version over broad protocol rewrites.

## Open Questions

- Which repo archetypes deserve distinct minimum data-quality expectations by default?
- Which readiness gates should support advisory mode versus strict blocking mode by default?
- How much evaluator scoring should be automated without obscuring operator judgment?
- What is the right amount of secretariat detail to persist before the state becomes noisy?
