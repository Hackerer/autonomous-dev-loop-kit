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

If the user specifies or implies a loop count, persist it with `python3 .agent-loop/scripts/set-loop-session.py --iterations N` before planning the first release.
If the active target repository is external to the kit workspace, set `AUTONOMOUS_DEV_LOOP_TARGET=/path/to/project` before invoking the scripts. Durable state, logs, and reports stay in the kit workspace under `docs/projects/<project-id>/`.

Treat a count-only request as a full autonomous loop launch for the active target repository. Do not ask the user to restate the loop requirements unless repo setup is missing.

Interpret `ReAct` as the Shunyu Yao paper method, `Reason + Act`, not the frontend framework `React`.

Within each iteration, require:

- deep analysis before execution
- explicit release definition before task selection
- treat the user-provided loop count as bundled release count, not tiny task count
- explicit research before goal selection
- product-manager, technical-architect, and user committee review before implementation
- explicit blocking when research says `need_more_context`
- rendering the independent evaluator brief before readiness judgment
- readiness gating before implementation
- short reason -> act -> observe -> update cycles
- post-validation reflection
- escalation assessment when repeated review or validation failures appear
- key observations from research, committee review, and execution written into the task report
- a detailed bundled release report when the active release is complete

Git publication must target the active target repository's own GitHub repository. If the active target repository's remote or publication target is unclear, stop and ask the user before publishing.

Do not skip the validation gate, report gate, or Git publication gate.
