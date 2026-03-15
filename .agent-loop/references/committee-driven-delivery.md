# Committee-Driven Delivery

Use this reference when the autonomous loop needs stronger pre-execution challenge than a single internal monologue can provide.

## Purpose

Before implementation starts, force the loop through three distinct lenses:

1. Product manager committee
2. Technical architect committee
3. User committee

The goal is not role-play for style. The goal is to surface requirement gaps, architectural risks, and usability blind spots before code changes begin.

## Required Behavior Per Iteration

Every iteration should include all of the following:

1. Research
   - Gather repo evidence, validation context, recent reports, and relevant product context.
   - Meet or exceed the configured minimum research inputs in `.agent-loop/config.json`.
2. Committee review
   - Product manager committee challenges user value, acceptance criteria, and scope.
   - Technical architect committee challenges design, interfaces, migration cost, and validation depth.
   - User committee challenges clarity, trust, workflow fit, and real usage friction.
3. Decision
   - Narrow to one scoped goal only after the committee feedback is reconciled.
4. Reflection
   - After validation, reflect on what the research or committee got wrong, right, or missed.

## Committee Composition

The default config requires three roles:

- `product-manager`
- `technical-architect`
- `user`

Each role must define 3 to 5 named members with:

- `name`
- `style`
- `focus`

This keeps the committee concrete enough to produce differentiated feedback instead of bland generic advice.

## How To Use The Committees

The committees should ask questions such as:

- Product managers:
  - Is this the smallest high-value thing we can ship next?
  - Are the acceptance criteria user-visible and testable?
  - What should be cut from this version?
- Technical architects:
  - What is the least risky design that satisfies the goal?
  - What breaks if this assumption is wrong?
  - Are tests and rollback paths strong enough?
- Users:
  - Would this behavior be understandable under time pressure?
  - What would feel confusing, noisy, or untrustworthy?
  - What real workflow friction does this create or remove?

## Output Expectations

The loop should persist concise conclusions, not hidden reasoning dumps.

Every report should record:

- research findings that changed the plan
- committee objections or endorsements that changed the scope
- the final decision taken after reconciliation
- post-validation reflection on what the committee missed

## Failure Modes This Prevents

- shipping work that is technically clean but low-value
- shipping work that sounds valuable but breaks architectural constraints
- shipping work that passes tests but is confusing for real users
- over-scoping an iteration because no one challenged the initial plan
