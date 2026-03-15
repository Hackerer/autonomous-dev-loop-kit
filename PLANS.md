# Autonomous Loop Plan

Updated: 2026-03-14

## Target Outcome

- Turn `autonomous-dev-loop-kit` into a stronger cross-CLI kit that gathers high-quality project data and context before acting, then challenges each version through committee-driven review.
- Make high-quality data acquisition and committee-driven requirement review first-class parts of the loop, not implicit side effects.
- Keep the kit usable from minimal prompts such as `循环10`, while preserving strict validation, reporting, and Git publication rules.

## Current State

- The repo already contains Codex and Claude wrappers, loop scripts, ReAct guidance, committee-driven review config, and a public README.
- The repo now has explicit project-data acquisition, evidence schema, scoring, and committee configuration for pre-implementation challenge.
- The repo still needs repository-specific validation commands instead of the placeholder validation step when installed into a target project.
- The repo should keep each published version small, testable, and directly connected to better pre-execution data quality and committee review.

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

## Backlog Notes

- Keep `.agent-loop/backlog.json` aligned with this plan.
- Prefer small, testable items over large rewrites.
- Prioritize improvements that increase evidence quality and committee challenge quality before implementation quality.

## Open Questions

- Which data signals should be considered mandatory before an autonomous loop edits a repo?
- How should the kit score "enough context" across different project types?
- How opinionated should the default committee personas be across very different products?
- What is the right balance between universal scripts and repo-specific overrides?
