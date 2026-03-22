from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path

from tests.support import ROOT, load_common


common = load_common()


def make_workspace(base: Path) -> Path:
    root = base / "repo"
    (root / ".agent-loop").mkdir(parents=True, exist_ok=True)
    return root


class CommonHelperTests(unittest.TestCase):
    def test_path_and_json_helpers(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_root = Path(tmp) / "repo"
            (tmp_root / ".agent-loop").mkdir(parents=True)
            (tmp_root / "docs" / "projects").mkdir(parents=True)
            self.assertEqual(common.kit_root(), ROOT)
            self.assertTrue(common.utc_now().endswith("Z"))
            self.assertEqual(common.projects_index_path(ROOT), ROOT / "docs" / "projects" / "index.json")
            self.assertEqual(common.project_root(str(tmp_root)), tmp_root.resolve())
            os.environ["AUTONOMOUS_DEV_LOOP_TARGET"] = str(tmp_root)
            self.assertEqual(common.project_root(), tmp_root.resolve())
            os.environ.pop("AUTONOMOUS_DEV_LOOP_TARGET", None)
            self.assertEqual(common.relpath(tmp_root / "docs" / "projects", tmp_root), "docs/projects")

            json_path = tmp_root / "payload.json"
            common.save_json(json_path, {"answer": 42})
            self.assertEqual(common.load_json(json_path), {"answer": 42})
            self.assertEqual(common.load_json(tmp_root / "missing.json", default={"ok": True}), {"ok": True})

            jsonl_path = tmp_root / "rows.jsonl"
            common.append_jsonl(jsonl_path, {"id": 1})
            common.append_jsonl(jsonl_path, {"id": 2})
            self.assertEqual(
                jsonl_path.read_text(encoding="utf-8").strip().splitlines(),
                [json.dumps({"id": 1}, ensure_ascii=True), json.dumps({"id": 2}, ensure_ascii=True)],
            )

            self.assertTrue(common.is_placeholder_text("Summarize the repo, product, user, and architecture research completed before selecting this version."))
            placeholder_report = tmp_root / "report.md"
            placeholder_report.write_text("- Summarize the repo, product, user, and architecture research completed before selecting this version.\n", encoding="utf-8")
            self.assertEqual(common.report_placeholder_lines(placeholder_report), ["Summarize the repo, product, user, and architecture research completed before selecting this version."])
            with self.assertRaises(common.LoopError):
                common.require_no_report_placeholders(placeholder_report, "report")

            self.assertEqual(common.slugify("Hello, World!"), "hello-world")
            self.assertIn("truncated", common.trim_output("x" * 5000))
            shell = common.run_shell("printf hello", tmp_root)
            self.assertEqual(shell["exit_code"], 0)
            self.assertEqual(shell["stdout"], "hello")

            kit = Path(tmp) / "kit"
            (kit / "docs" / "projects").mkdir(parents=True)
            self.assertEqual(common.load_projects_index(kit), {"version": 1, "projects": []})
            index = {"version": 1, "projects": [{"project_id": "p1"}]}
            common.save_projects_index(kit, index)
            self.assertEqual(common.load_projects_index(kit), index)

    def test_repo_identity_helpers(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            kit = Path(tmp) / "kit"
            target = Path(tmp) / "target"
            kit.mkdir()
            target.mkdir()
            (kit / "docs" / "projects").mkdir(parents=True)
            common.save_projects_index(kit, {"version": 1, "projects": []})

            os.environ["AUTONOMOUS_DEV_LOOP_PROJECT_ID"] = "explicit-project"
            self.assertEqual(common.project_fingerprint(target), "explicit:explicit-project")
            self.assertTrue(common.project_key(target).startswith("target-"))
            os.environ.pop("AUTONOMOUS_DEV_LOOP_PROJECT_ID", None)

            workspace = kit / "docs" / "projects" / "sample-project"
            common.save_projects_index(
                kit,
                {
                    "version": 1,
                    "projects": [
                        {
                            "project_id": "sample-project",
                            "workspace": str(workspace),
                            "target_root": str(target.resolve()),
                            "fingerprint": common.project_fingerprint(target),
                            "label": "sample-project",
                        }
                    ],
                },
            )
            self.assertEqual(common.project_workspace_root(kit, target), workspace.resolve())
            self.assertEqual(common.resolve_execution_roots(str(target))[0], common.kit_root())
            self.assertEqual(common.project_label(target), "target")

    def test_git_helpers(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / "repo"
            repo.mkdir()
            (repo / ".agent-loop").mkdir()
            common.git(repo, "init")
            common.git(repo, "config", "user.name", "Tester")
            common.git(repo, "config", "user.email", "tester@example.com")
            (repo / "README.md").write_text("x", encoding="utf-8")
            common.git(repo, "add", "README.md")
            common.git(repo, "commit", "-m", "init")
            common.git(repo, "remote", "add", "origin", "https://github.com/example/sample.git")

            branch = common.current_branch(repo)
            self.assertIn(branch, {"main", "master"})
            self.assertEqual(common.safe_current_branch(repo), branch)
            self.assertTrue(common.remote_exists(repo, "origin"))
            remotes = common.git_remotes(repo)
            self.assertIn("origin", remotes)
            self.assertIn("https://github.com/example/sample.git", remotes["origin"])
            self.assertEqual(common.git_remote_url(repo), "https://github.com/example/sample.git")
            self.assertTrue(common.ensure_git_repo(repo) is None)
            self.assertTrue(common.find_repo_root(repo) == repo.resolve())

    def test_config_and_state_helpers(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = make_workspace(Path(tmp))
            config = json.loads((ROOT / ".agent-loop" / "config.json").read_text(encoding="utf-8"))
            common.save_json(root / ".agent-loop" / "config.json", config)
            state = common.default_state()
            common.save_state(root, state)
            backlog = [{"id": "goal-1", "title": "Goal 1", "status": "pending"}]
            common.save_backlog(root, backlog)

            self.assertEqual(common.load_config(root), config)
            self.assertEqual(common.load_state(root)["session"]["status"], state["session"]["status"])
            self.assertEqual(common.load_backlog(root), backlog)
            self.assertGreater(common.next_release_number(state), 0)

            self.assertTrue(common.usage_logging_config(config)["enabled"])
            self.assertIsInstance(common.planning_config(config), dict)
            self.assertIsInstance(common.experiment_config(config), dict)
            self.assertIsInstance(common.release_planning_config(config), dict)
            self.assertEqual(common.derive_session_id({"started_at": "2026-03-22T00:00:00Z"}), "session-20260322-000000")

            discovery = common.discovery_config(config)
            profiles = common.archetype_profiles_config(config)
            profile = common.archetype_profile_summary(config, "agent-skill-kit")
            self.assertIsInstance(discovery, dict)
            self.assertIn("default_profile", profiles)
            self.assertTrue(profile["id"])
            self.assertTrue(common.validate_committee(config) == [])
            committee_summary = common.committee_summary(config)
            persona_catalog = common.persona_catalog(config)
            council_summary = common.council_summary(config)
            evaluator_summary = common.evaluator_summary(config)
            self.assertIsInstance(committee_summary, list)
            self.assertIsInstance(persona_catalog, dict)
            self.assertIsInstance(council_summary, list)
            self.assertIsInstance(evaluator_summary, dict)
            self.assertGreater(len(committee_summary), 0)
            self.assertGreater(len(persona_catalog), 0)

    def test_review_and_release_helpers(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = make_workspace(Path(tmp))
            config = json.loads((ROOT / ".agent-loop" / "config.json").read_text(encoding="utf-8"))
            common.save_json(root / ".agent-loop" / "config.json", config)
            state = common.default_state()
            goal = {"id": "goal-1", "title": "Goal 1"}
            state["current_goal"] = goal
            state["session"]["status"] = "active"
            state["session"]["target_releases"] = 2
            state["session"]["completed_releases"] = 1
            state["release"] = {
                "number": 1,
                "status": "planned",
                "goal_ids": ["goal-1"],
                "goal_titles": ["Goal 1"],
                "completed_goal_ids": [],
                "task_iterations": [],
                "brief": {
                    "objective": "Objective",
                    "target_user_value": "Value",
                    "why_now": "Now",
                    "packaging_rationale": "Reason",
                    "scope_in": [],
                    "scope_out": [],
                    "release_acceptance": [],
                    "deferred_items": [],
                },
            }
            state["review_state"]["status"] = "captured"
            state["review_state"]["research_findings"] = ["finding"]
            state["review_state"]["committee_feedback"] = ["feedback"]
            state["review_state"]["committee_decision"] = ["decision"]
            state["review_state"]["reflection_notes"] = ["reflection"]
            state["review_state"]["evaluation"] = {
                "status": "captured",
                "rubric_version": "v1",
                "scores": {"goal_clarity": 5.0},
                "weighted_score": 5.0,
                "result": "pass",
                "critique": [],
                "minimum_fixes_required": [],
            }
            state["last_validation"] = {"status": "passed", "ran_at": "2026-03-22T00:00:00Z", "results": []}
            common.save_state(root, state)

            self.assertTrue(common.require_selected_goal(state)["id"] == "goal-1")
            self.assertTrue(common.review_state_matches_goal(state["review_state"], goal))
            self.assertTrue(common.review_state_has_content(state["review_state"]))
            self.assertTrue(common.require_review_state(config, state, goal)["status"] == "captured")
            self.assertEqual(common.require_evaluator_pass(config, state, goal)["result"], "pass")
            self.assertEqual(common.implementation_gate_status(config, state["review_state"]["evaluation"])["status"], "pass")
            self.assertEqual(common.session_summary(state)["target_releases"], 2)
            self.assertEqual(common.require_session_capacity(config, state)["target_releases"], 2)
            self.assertEqual(common.active_release(state)["number"], 1)
            self.assertEqual(common.active_release_goal_ids(state), ["goal-1"])
            self.assertEqual(common.release_summary(state)["status"], "planned")
            self.assertEqual(common.require_active_release(config, state)["number"], 1)
            self.assertEqual(common.require_goal_in_active_release(config, state, goal)["number"], 1)
            self.assertIsNotNone(common.release_reporting_path(root, config, 1))
            self.assertEqual(common.goal_selection_blockers(config, state, "ready", []), [])
            self.assertEqual(common.current_evaluation_result(state), "pass")
            self.assertEqual(common.consecutive_review_blocks(state), 0)
            self.assertEqual(common.consecutive_goal_churn(state), 0)
            self.assertEqual(common.assess_escalation(config, state)["status"], "not_needed")
            self.assertEqual(common.require_green_validation(state)["status"], "passed")
            self.assertTrue(common.reporting_path(root, config, 1).name.endswith(".md"))

    def test_usage_and_experiment_helpers(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = make_workspace(Path(tmp))
            config = json.loads((ROOT / ".agent-loop" / "config.json").read_text(encoding="utf-8"))
            common.save_json(root / ".agent-loop" / "config.json", config)
            state = common.default_state()
            state["current_goal"] = {"id": "g1", "title": "Goal 1"}
            state["session"]["status"] = "active"
            state["review_state"]["status"] = "captured"
            state["review_state"]["evaluation"] = {
                "status": "captured",
                "rubric_version": "v1",
                "scores": {"goal_clarity": 5.0},
                "weighted_score": 5.0,
                "result": "pass",
                "critique": [],
                "minimum_fixes_required": [],
            }
            state["review_state"]["experiment"] = {
                "candidate": {"metric_value": 6.0},
                "comparison": {"direction": "higher"},
                "promotion": {"decision": "promote"},
            }
            state["release"] = {
                "number": 2,
                "status": "planned",
                "goal_ids": ["g1"],
                "goal_titles": ["Goal 1"],
                "completed_goal_ids": [],
                "task_iterations": [],
                "brief": {"scope_in": [], "scope_out": [], "release_acceptance": [], "deferred_items": []},
            }
            state["history"] = [{"number": 2, "candidate_metric_value": 5.0}]
            common.save_state(root, state)

            self.assertEqual(common.usage_log_path(root, config).name, "usage-log.jsonl")
            self.assertTrue(common.detected_usage_client() is None or isinstance(common.detected_usage_client(), str))
            context = common.usage_log_context(root)
            self.assertIn("session", context)
            log_path = common.append_usage_log(root, config, "test_event", {"x": 1})
            self.assertTrue(log_path.exists())
            self.assertEqual(common.goal_title({"title": "Goal 1"}), "Goal 1")
            promoted, reason, baseline, candidate = common.promote_candidate_decision(state)
            self.assertTrue(promoted)
            self.assertIn("improves", reason)
            self.assertEqual(baseline, 5.0)
            self.assertEqual(candidate, 6.0)
            self.assertEqual(common.latest_promoted_release_record(state)["number"], 2)
            self.assertEqual(common.latest_promoted_metric_value(state), 5.0)
            self.assertEqual(common.current_candidate_metric(state), 6.0)
            self.assertEqual(common.experiment_status(state)["promotion"]["decision"], "promote")


if __name__ == "__main__":
    unittest.main()
