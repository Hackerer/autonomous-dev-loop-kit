from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from pypdf import PdfReader
from reportlab.pdfgen import canvas

from tests.support import ROOT, load_module


capture_review = load_module("capture_review", "capture-review.py")
plan_release = load_module("plan_release", "plan-release.py")
render_committee = load_module("render_committee", "render-committee.py")
render_evaluator_brief = load_module("render_evaluator_brief", "render-evaluator-brief.py")
record_usage_event = load_module("record_usage_event", "record-usage-event.py")
write_report = load_module("write_report", "write-report.py")
write_release_report = load_module("write_release_report", "write-release-report.py")
select_next_goal = load_module("select_next_goal", "select-next-goal.py")
analyze_usage_logs = load_module("analyze_usage_logs", "analyze-usage-logs.py")
score_data_quality = load_module("score_data_quality", "score-data-quality.py")
loop_doctor = load_module("loop_doctor", "loop-doctor.py")

common = load_module("common_again", "common.py")


def make_pdf(path: Path, text: str = "Sample") -> None:
    c = canvas.Canvas(str(path), pagesize=(595, 842))
    c.drawString(50, 780, text)
    c.save()


class ScriptHelperTests(unittest.TestCase):
    def test_record_usage_fields(self) -> None:
        self.assertEqual(record_usage_event.parse_fields(["a=1", "b=two"]), {"a": "1", "b": "two"})

    def test_capture_review_helpers(self) -> None:
        self.assertEqual(capture_review.merge_unique(["a", "b"], ["b", "c"]), ["a", "b", "c"])
        slot = capture_review.update_council_slot({"status": "not_started", "dissent": ["x"]}, "summary", "decision", ["x", "y"])
        self.assertEqual(slot["status"], "captured")
        self.assertEqual(slot["dissent"], ["x", "y"])
        self.assertEqual(capture_review.parse_scores(["goal=4.5"])["goal"], 4.5)

    def test_plan_release_helpers(self) -> None:
        goals = [
            {"title": "Improve billing translation", "acceptance": ["A"]},
            {"title": "Improve billing layout", "acceptance": ["B"]},
            {"title": "Ship the billing loop", "acceptance": ["C"]},
        ]
        backlog = [
            {"id": "a", "title": "Improve billing translation", "priority": "critical", "status": "pending", "acceptance": ["A"]},
            {"id": "b", "title": "Improve billing layout", "priority": "high", "status": "pending", "acceptance": ["B"]},
            {"id": "c", "title": "Ship the billing loop", "priority": "low", "status": "done", "acceptance": ["C"]},
        ]
        self.assertEqual(plan_release.common_theme(goals), "billing")
        self.assertTrue(plan_release.auto_title(3, goals).startswith("R3:"))
        self.assertIn("将这些目标打包成一个面向用户的发布", plan_release.auto_summary(goals))
        self.assertEqual([item["id"] for item in plan_release.pick_pending(backlog, 2)], ["a", "b"])
        self.assertEqual([item["id"] for item in plan_release.resolve_goals(backlog, [], 1)], ["a"])
        self.assertEqual(plan_release.pending_titles(backlog, ["a"]), ["Improve billing layout"])
        self.assertEqual(plan_release.aggregate_acceptance(goals), ["A", "B", "C"])
        config = {"planning": {"release": {"archetypes": {"docs": {"keywords": ["pdf"], "objective_template": "Ship docs."}}}}}
        self.assertIn("docs", plan_release.release_archetypes(config))
        self.assertEqual(plan_release.detect_archetype(goals, plan_release.release_archetypes(config)), "docs")
        self.assertGreaterEqual(len(plan_release.packaging_signals(goals, "pdf", "docs", plan_release.release_archetypes(config))), 2)
        brief = plan_release.build_release_brief(
            SimpleNamespace(
                archetype="docs",
                deferred_item=[],
                release_acceptance=[],
                scope_in=[],
                scope_out=[],
                objective="",
                target_user_value="",
                why_now="",
                packaging_rationale="",
                launch_story="",
            ),
            goals,
            backlog,
            config,
            common.default_state(),
        )
        self.assertEqual(brief["archetype"], "docs")
        self.assertEqual(brief["release_acceptance"], ["A", "B", "C"])

    def test_write_report_helpers(self) -> None:
        self.assertEqual(write_report.bullet_lines([], "fallback"), ["- fallback"])
        self.assertEqual(write_report.merge_unique(["A"], ["A", "B"]), ["A", "B"])
        self.assertEqual(write_report.prefixed_lines("x: ", ["a", ""]), ["x: a"])

    def test_write_release_report_helpers(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "report.md"
            path.write_text("## Delivered\n- A\n## Technical Validation\n- PASS\n", encoding="utf-8")
            sections = write_release_report.section_map(path)
            self.assertEqual(sections["Delivered"], ["- A"])
            self.assertEqual(write_release_report.bulletize([], "fallback"), ["- fallback"])
            self.assertEqual(write_release_report.optional_bulletize(["A"]), ["- A"])

    def test_select_next_goal_helpers(self) -> None:
        state = common.default_state()
        state["project_data"]["quality_path"] = ".agent-loop/data/data-quality.json"
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / ".agent-loop" / "data").mkdir(parents=True)
            (root / ".agent-loop" / "data" / "data-quality.json").write_text(
                json.dumps({"status": "blocked", "blocking_gaps": ["Missing evidence"]}),
                encoding="utf-8",
            )
            self.assertEqual(select_next_goal.load_quality_context(root, state), ("blocked", ["Missing evidence"]))
            item = {"id": "g1", "title": "Fix missing evidence", "notes": "", "acceptance": []}
            self.assertLess(select_next_goal.gap_priority(item, "blocked", ["Missing evidence"]), 0)
            self.assertEqual(select_next_goal.pick_goal(root, [item], state)["id"], "g1")

    def test_render_committee_and_brief_helpers(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            snapshot = {
                "repo": {"current_branch": "main"},
                "project": {"repo_archetype": "agent-skill-kit", "archetype_profile": {"label": "Baseline", "id": "baseline"}},
                "product_context": {"target_outcome": "Deliver value", "constraints": ["No regressions"]},
                "evidence": {"confidence": "high", "freshness": "fresh", "sources": ["docs"]},
                "latest_review_state": {"matches_current_goal": True, "research_gate": {"status": "captured", "open_gaps": []}},
            }
            (root / ".agent-loop" / "data").mkdir(parents=True)
            (root / ".agent-loop" / "data" / "snapshot.json").write_text(json.dumps(snapshot), encoding="utf-8")
            state = common.default_state()
            state["current_goal"] = {"id": "g1", "title": "Goal 1"}
            state["project_data"]["snapshot_path"] = ".agent-loop/data/snapshot.json"
            state["project_data"]["quality_path"] = ".agent-loop/data/snapshot.json"
            review_packet = render_committee.build_review_packet(root, state)
            self.assertEqual(review_packet["active_goal"]["id"], "g1")
            self.assertEqual(review_packet["project_context"]["repo_archetype"], "agent-skill-kit")

            brief_state = common.default_state()
            brief_state["current_goal"] = {"id": "g1", "title": "Goal 1"}
            brief_state["project_data"]["snapshot_path"] = ".agent-loop/data/snapshot.json"
            brief_state["review_state"] = {
                "status": "captured",
                "scope_decision": {
                    "status": "captured",
                    "selected_goal": "g1",
                    "why_selected": "Needed",
                    "scope_in": ["A"],
                    "scope_out": ["B"],
                    "assumptions": ["C"],
                    "risks": ["D"],
                    "required_validation": ["E"],
                    "stop_conditions": ["F"],
                },
                "evaluation": {
                    "status": "captured",
                    "rubric_version": "v1",
                    "scores": {},
                    "weighted_score": 5.0,
                    "result": "pass",
                    "critique": [],
                    "minimum_fixes_required": [],
                },
            }
            (root / ".agent-loop" / "state.json").write_text(json.dumps(brief_state), encoding="utf-8")
            project_context = render_evaluator_brief.build_project_context(root, brief_state)
            self.assertEqual(project_context["current_branch"], "main")
            self.assertEqual(project_context["target_outcome"], "Deliver value")

    def test_analyze_usage_helpers(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            log = Path(tmp) / "usage.jsonl"
            log.write_text(
                json.dumps({"timestamp": "2026-03-22T00:00:00Z", "event": "session_started", "session": {"id": "s1"}})
                + "\n"
                + json.dumps({"timestamp": "2026-03-22T00:01:00Z", "event": "iteration_published", "release": {"number": 1}, "payload": {}})
                + "\n",
                encoding="utf-8",
            )
            rows, invalid = analyze_usage_logs.load_jsonl(log)
            self.assertEqual(invalid, 0)
            self.assertEqual(analyze_usage_logs.session_id_for(rows[0]), "s1")
            normalized, invalid_by_path = analyze_usage_logs.normalize_rows([log])
            self.assertEqual(invalid_by_path[str(log)], 0)
            summary = analyze_usage_logs.summarize_session("s1", normalized)
            self.assertEqual(summary["events_by_type"]["session_started"], 1)
            payload = analyze_usage_logs.summarize_usage(normalized, [log], invalid_by_path)
            self.assertGreaterEqual(payload["session_count"], 1)

    def test_score_data_and_doctor_helpers(self) -> None:
        self.assertTrue(score_data_quality.has_tooling_signals({"tooling_signals": ["python-cli-scripts"]}))
        profile = score_data_quality.profile_summary({"project": {"archetype_profile": {"id": "baseline", "label": "Baseline"}}})
        self.assertEqual(profile["id"], "baseline")
        self.assertIsInstance(score_data_quality.signal_checks({"project": {"tooling_signals": ["python-cli-scripts"]}}), dict)
        diagnosis = loop_doctor.diagnose(
            {"planning": {"release": {"require_release_plan": False}}, "committee": {"evaluator": {"implementation_gate_mode": "blocking"}}},
            {"session": {"status": "not_configured"}},
            Path("/tmp/workspace"),
            Path("/tmp/target"),
        )
        self.assertTrue(diagnosis)
        self.assertIn("next_step", diagnosis[0])


if __name__ == "__main__":
    unittest.main()
