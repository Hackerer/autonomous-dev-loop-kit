# Committee-Driven Delivery

Use this reference when the autonomous loop needs stronger pre-execution challenge than a single internal monologue can provide.

## Purpose

This kit uses a lightweight committee architecture to improve scope quality without turning the repo into enterprise governance.

The committee system exists to answer five practical questions before implementation starts:

1. Is this the right goal now?
2. What is the smallest safe scope?
3. What must stay out of scope?
4. What evidence or objections still matter?
5. Is the iteration ready to implement?

The output must be durable. Important decisions belong in `.agent-loop/state.json`, not only in chat or reports.

## Lightweight V2 Structure

The committee system now has five logical units:

1. Product Council
2. Architecture Council
3. Operator Council
4. Secretariat
5. Independent Evaluator

This is intentionally lightweight:

- councils produce differentiated pressure
- secretariat converges that pressure into a scope decision
- evaluator scores readiness independently
- reports and project-data snapshots expose the result in compact form

## Council Roles

### Product Council

Focus:

- goal selection
- why now
- scope discipline
- user-facing value

Default personas:

- Outcome PM
- Scope PM
- User PM

### Architecture Council

Focus:

- source-of-truth boundaries
- protocol integrity
- validation truthfulness
- release safety

Default personas:

- Repo Architect
- Protocol Architect
- Quality & Safety Architect

### Operator Council

Focus:

- solo-project usability
- handoff quality
- auditability
- operator clarity

Default personas:

- Solo Builder
- Team Maintainer
- Security & Compliance User

## Secretariat

The secretariat is not another debate group. It is the convergence layer.

### Delivery Secretary

Converts committee pressure into an executable scope decision:

- selected goal
- scope in
- scope out
- assumptions
- required validation
- stop conditions
- next action

### Audit Secretary

Converts the same decision into durable state:

- research summary
- evidence refs
- council summaries
- scope decision
- dissent
- open gaps
- escalation reasons

## Independent Evaluator

The independent evaluator is a separate readiness gate.

It should judge:

- goal clarity
- scope fitness
- repo safety
- validation readiness
- state durability
- publish safety

The evaluator uses the rubric in:

- `.agent-loop/references/iteration-readiness-rubric.json`

When the evaluator gate is enabled, the loop requires a matching `pass` result before implementation readiness, reporting, and publication.

## Durable State Model

The committee system should populate these durable lanes in `review_state`:

- `research_gate`
- `councils`
- `scope_decision`
- `evaluation`
- `escalation`

The older flat fields remain for compatibility, but the structured blocks are now the higher-signal contract.

## Expected Workflow

The practical flow is:

1. collect project data
2. score data quality
3. render the committee brief
4. capture research-gate findings
5. capture council summaries and dissent
6. capture the scope decision
7. capture evaluator result
8. run `python3 .agent-loop/scripts/assert-implementation-readiness.py`
9. implement
10. validate
11. report
12. publish

## Output Rules

The committee system should produce concise structured artifacts, not transcripts.

Prefer:

- summaries
- decisions
- dissent bullets
- open gaps
- readiness scores

Avoid:

- narrative meeting minutes
- long persona monologues
- duplicated state across multiple files
- free-form debate dumps

## Dissent And Escalation

The committee model does not require fake consensus.

Keep:

- dissent in council slots or scope decision
- open gaps in research or reports
- escalation reasons in `review_state.escalation`

Escalation should stay deterministic and lightweight. Typical triggers include:

- repeated evaluator revise or fail
- repeated validation failure
- unresolved scope churn
- missing evidence that blocks safe selection

## Failure Modes This Prevents

- shipping work with no durable scope boundary
- mixing council advice with final readiness judgment
- reporting a clean narrative without showing dissent or open gaps
- letting an old evaluator pass authorize a new goal
- making the process so heavy that solo or small-project usage collapses
