# Autonomous Dev Loop Trigger

Use `.claude/skills/autonomous-dev-loop` when the user asks for autonomous iteration, repeated version shipping, “自主循环开发”, “自动迭代开发”, or any request to keep delivering successive versions with testing, Git publication, and reports.

Also trigger it when the user only gives a loop count or loop-count phrase, including:

- `循环3次`
- `来两轮`
- `做 5 轮`
- `开始循环 3 次`
- `run 3 iterations`
- `ship 2 versions`

Before the first iteration of a session, read:

- `PLANS.md`
- `.agent-loop/config.json`
- `.agent-loop/state.json`
- `.agent-loop/backlog.json`
- `.agent-loop/references/protocol.md`
- `.agent-loop/references/committee-driven-delivery.md`

If the user specifies or implies a loop count, persist it with `python3 .agent-loop/scripts/set-loop-session.py --iterations N` before selecting the first goal.

Treat a count-only request as a full autonomous loop launch in the current repo. Do not ask the user to restate the loop requirements unless repo setup is missing.

Interpret `ReAct` as the Shunyu Yao paper method, `Reason + Act`, not the frontend framework `React`.

Within each iteration, require:

- deep analysis before execution
- explicit research before goal selection
- product-manager, technical-architect, and user committee review before implementation
- explicit blocking when research says `need_more_context`
- rendering the independent evaluator brief before readiness judgment
- readiness gating before implementation
- short reason -> act -> observe -> update cycles
- post-validation reflection
- escalation assessment when repeated review or validation failures appear
- key observations from research, committee review, and execution written into the report

Git publication must target the current project's own GitHub repository. If the current project's remote or publication target is unclear, stop and ask the user before publishing.

Do not skip the validation gate, report gate, or Git publication gate.
