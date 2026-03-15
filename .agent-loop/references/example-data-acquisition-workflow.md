# Example Data Acquisition Workflow

Use this workflow when the loop starts from a minimal prompt such as `循环10`.

## Example Sequence

1. Read:
   - `PLANS.md`
   - `.agent-loop/config.json`
   - `.agent-loop/state.json`
   - `.agent-loop/backlog.json`
2. Set the session:
   - `python3 .agent-loop/scripts/set-loop-session.py --iterations 10`
3. Collect project data:
   - `python3 .agent-loop/scripts/collect-project-data.py`
4. Score project data quality:
   - `python3 .agent-loop/scripts/score-data-quality.py`
   - Review the active repo archetype profile in `.agent-loop/data/project-data.json` if the repo needs different quality expectations.
5. Render the committee brief:
   - `python3 .agent-loop/scripts/render-committee.py`
6. Do research and committee review, then persist the findings:
   - `python3 .agent-loop/scripts/capture-review.py --research ... --committee-feedback ... --decision ...`
   - If the repo still lacks enough context, record that explicitly:
     - `python3 .agent-loop/scripts/capture-review.py --research-status need_more_context --research-summary "..." --open-gap "..."`
7. Select the next goal:
   - `python3 .agent-loop/scripts/select-next-goal.py`
   - If selection is blocked, gather the missing context first, refresh project data if needed, update research capture, then rerun goal selection.
8. Capture the scope decision for the selected goal.
9. Render the evaluator input:
   - `python3 .agent-loop/scripts/render-evaluator-brief.py`
10. Capture the evaluator result, then confirm readiness:
   - `python3 .agent-loop/scripts/score-evaluator-readiness.py --score goal_clarity=4.0 --score scope_fitness=4.0 --score repo_safety=4.0 --score validation_readiness=4.0 --score state_durability=4.0 --score publish_safety=4.0`
   - `python3 .agent-loop/scripts/assert-implementation-readiness.py`
   - `implementation_gate_mode=advisory` may allow implementation with a warning, but report and publish still require evaluator pass.
11. Implement the version.
12. Run full validation:
   - `python3 .agent-loop/scripts/run-full-validation.py`
13. Assess whether repeated failures or churn should trigger watch or escalation:
   - `python3 .agent-loop/scripts/assess-escalation.py`
14. Reflect on research and committee feedback after validation.
15. Refresh project data if the repo changed materially:
   - `python3 .agent-loop/scripts/collect-project-data.py`
   - `python3 .agent-loop/scripts/score-data-quality.py`
16. Write the report:
   - `python3 .agent-loop/scripts/write-report.py`
17. Publish:
   - `python3 .agent-loop/scripts/publish-iteration.py`

## Why This Matters

This sequence makes the loop data-first:

- context is gathered explicitly
- data quality is evaluated explicitly
- requirements are challenged by distinct product, architecture, and user lenses
- planning responds to evidence gaps
- reports can explain their evidence base
