# Autonomous Loop Plan

Updated: 2026-03-15

## Target Outcome

- Turn `autonomous-dev-loop-kit` into a stronger cross-CLI kit that gathers high-quality project data and context before acting, then challenges each version through committee-driven review.
- Make high-quality data acquisition and committee-driven requirement review first-class parts of the loop, not implicit side effects.
- Add an opt-in experiment layer so each candidate version can be compared against a durable base and only promoted when it is better.
- Keep the kit usable from minimal prompts such as `循环10`, while preserving strict validation, reporting, and Git publication rules.
- Strengthen the lightweight committee baseline with archetype-aware data-quality thresholds, richer review packets, explicit secretariat artifacts, and more usable evaluator/readiness tooling without turning the kit into heavyweight enterprise process.

## Current State

- The repo already contains Codex and Claude wrappers, loop scripts, ReAct guidance, committee-driven review config, and a public README.
- The repo now has explicit project-data acquisition, evidence schema, scoring, and committee configuration for pre-implementation challenge.
- The loop now stores research and committee review conclusions in durable state and can flow that review context back into collected project data and report generation.
- The repo now uses the kit workspace as the control plane, with one per-project folder under `docs/projects/<project-id>/` for project-specific state, logs, and reports.
- The loop now enforces matching review-state capture before report writing and publication when committee review is required.
- The committee layer is now a lightweight V2 baseline with councils, secretariat, evaluator briefs, readiness gating, escalation assessment, stop-and-escalation reporting, and goal-bound review-state capture.
- The committee layer now also includes archetype-aware quality profiles, live review packets, explicit secretariat durability and visibility, evaluator score helpers, and configurable implementation readiness mode with strict report/publish safety.
- The repo now supports non-destructive session continuation for longer autonomous runs.
- The installer, example workflow, and entrypoint skills now point to the same research-gated, evaluator-aware lightweight committee V2 flow.
- The repo now treats loop-count requests as bundled release counts while preserving smaller task-level iterations underneath each release.
- The repo now has an experiment-lane architecture in progress so candidate versions can be judged against a base before promotion.
- Target repos still need repository-specific validation commands instead of the placeholder validation step when installed from this kit.
- Published versions should continue to stay small, testable, and directly connected to better pre-execution data quality, committee review quality, or operator clarity.
- The lightweight baseline now includes bundled release planning, release reports, and release closeout as first-class protocol concepts.

## Non-Negotiable Constraints

- Keep the core protocol shared across Codex CLI and Claude Code CLI.
- Use ReAct in the Shunyu Yao paper sense: reason, act, observe, update.
- Do not require verbose chain-of-thought in user-visible chat.
- Every published version must pass real validation, write a report, and publish to the active target repository's GitHub remote.
- Favor deterministic scripts and durable repo state over purely prompt-based behavior.

## Acceptance Gates

- Before the session starts, persist the requested loop count with `python3 .agent-loop/scripts/set-loop-session.py --iterations N`.
- Every version must pass the commands configured in `.agent-loop/config.json`.
- Every version must produce a report in the active project workspace under `docs/projects/<project-id>/docs/reports/`.
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
- 2026-03-15: Add a non-invasive installer that registers target projects while storing their loop state in the kit workspace under per-project folders.
- 2026-03-15: Make matching review-state capture a hard gate for report writing and publication.
- 2026-03-15: Start a lighter-weight committee V2 roadmap focused on structured councils, scope decisions, dissent, evaluator scoring, and escalation without overloading the kit.
- 2026-03-15: Finish the lightweight committee V2 baseline with research blocking, evaluator briefs, escalation assessment, stop-and-escalation reporting, session continuation, aligned installer guidance, and goal-bound review resets.
- 2026-03-15: Start the next committee session with a lighter-weight enhancement track focused on archetype-aware thresholds, richer review packets, explicit secretariat artifacts, and better evaluator ergonomics.
- 2026-03-15: Extend the lightweight baseline with archetype-aware quality scoring, live review packets, explicit secretariat visibility, deterministic evaluator scoring, configurable implementation readiness mode, and aligned bootstrap guidance.
- 2026-03-15: Start the bundled-release upgrade so user-requested loop counts represent larger user-visible versions rather than tiny single-task commits.
- 2026-03-15: Finish the bundled-release upgrade with release planning, release reports, release publication, protocol alignment, and validator coverage.

## Backlog Notes

- Keep `.agent-loop/backlog.json` aligned with this plan.
- Prefer small, testable items over large rewrites.
- Prioritize improvements that increase evidence quality and committee challenge quality before implementation quality.
- Preserve backward compatibility where practical so target repositories can adopt the stronger committee model incrementally.
- Treat the current lightweight committee V2 baseline as the default starting point for future sessions rather than an experimental branch of the protocol.
- Keep committee upgrades compact and explicit: prefer one new durable artifact or one new gate behavior per version over broad protocol rewrites.
- Keep bundled-release upgrades practical: preserve task-level commits and validation while making the top-level version feel like a real packaged release.

## Open Questions

- Which repo archetypes deserve distinct minimum data-quality expectations by default?
- Which readiness gates should support advisory mode versus strict blocking mode by default?
- How much evaluator scoring should be automated without obscuring operator judgment?
- What is the right amount of secretariat detail to persist before the state becomes noisy?
- How opinionated should automatic release bundling be before users need to name or curate the release explicitly?

## Session 63-66: Reliability And Review Remediation

### Target Outcome

- Eliminate publish-time state drift so durable loop state, backlog progress, and release history are recorded in the same committed version that gets published.
- Reset new loop sessions cleanly so old review failures, escalation pressure, and stale committee artifacts do not bleed into fresh sessions.
- Make review gating, usage-log analysis, and operator recovery tooling resilient to real-world malformed inputs and publish-target misconfiguration.
- Extend validator coverage so these reliability guarantees are enforced continuously and regressions are caught before release.

### Optimization Focus

1. **Publish transaction correctness**: preflight remotes before state mutation, persist publish state in the committed artifact, and prevent failed publish attempts from consuming goals.
2. **State reset correctness**: reset review, escalation, and failure counters when a new session is started while preserving long-term release history intentionally.
3. **Review-state compatibility**: treat structured council, secretariat, scope, and evaluator artifacts as valid review content.
4. **Operational resilience**: tolerate malformed usage-log rows and make `loop-doctor.py` surface the same remote/publish blockers as the real publish scripts.
5. **Validator enforcement**: prove clean post-publish state and failed-publish rollback expectations with deterministic tests.
