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
5. Render the committee brief:
   - `python3 .agent-loop/scripts/render-committee.py`
6. Do research and committee review, then persist the findings:
   - `python3 .agent-loop/scripts/capture-review.py --research ... --committee-feedback ... --decision ...`
7. Select the next goal:
   - `python3 .agent-loop/scripts/select-next-goal.py`
8. Implement the version.
9. Run full validation:
   - `python3 .agent-loop/scripts/run-full-validation.py`
10. Reflect on research and committee feedback after validation.
11. Refresh project data if the repo changed materially:
   - `python3 .agent-loop/scripts/collect-project-data.py`
   - `python3 .agent-loop/scripts/score-data-quality.py`
12. Write the report:
   - `python3 .agent-loop/scripts/write-report.py`
13. Publish:
   - `python3 .agent-loop/scripts/publish-iteration.py`

## Why This Matters

This sequence makes the loop data-first:

- context is gathered explicitly
- data quality is evaluated explicitly
- requirements are challenged by distinct product, architecture, and user lenses
- planning responds to evidence gaps
- reports can explain their evidence base
