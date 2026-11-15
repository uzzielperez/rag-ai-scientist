import json
import tempfile
import unittest
from pathlib import Path

from rag_ai_scientist import dali_onboard as ob


class ParseTests(unittest.TestCase):
    def test_parse_json_array_from_fenced_reply(self):
        text = '```json\n[{"a": 1}, {"a": 2}]\n```'
        self.assertEqual(ob._parse_json_array(text), [{"a": 1}, {"a": 2}])

    def test_parse_json_object_from_prose(self):
        text = 'sure! {"command": "ls -1"} hope that helps'
        self.assertEqual(ob._parse_json_object(text), {"command": "ls -1"})

    def test_parse_returns_none_on_garbage(self):
        self.assertIsNone(ob._parse_json_array("no array here"))
        self.assertIsNone(ob._parse_json_object("no object here"))


class PlanNormalisationTests(unittest.TestCase):
    def test_keeps_benchmarks_with_sources_and_flags_them(self):
        plan = ob._normalise_plan([
            {"id": "skim", "description": "select candidates", "command": "python sel.py",
             "check": "counts match", "depends_on": [],
             "benchmarks": [{"quantity": "PNNK threshold", "value": 0.05, "unit": "none",
                             "source": "docs/skimming.rst"}]},
        ])
        self.assertEqual(len(plan), 1)
        bench = plan[0]["benchmarks"][0]
        self.assertEqual(bench["value"], 0.05)
        self.assertEqual(bench["source"], "docs/skimming.rst")
        self.assertEqual(bench["confidence"], "extracted-unverified")

    def test_drops_benchmark_without_value_or_source(self):
        plan = ob._normalise_plan([
            {"id": "fit", "description": "fit", "benchmarks": [
                {"quantity": "made up"}, {"quantity": "yield", "value": 65215}]},
        ])
        self.assertEqual(len(plan[0]["benchmarks"]), 1)
        self.assertEqual(plan[0]["benchmarks"][0]["source"], "(no source given)")

    def test_drops_unknown_and_self_dependencies(self):
        plan = ob._normalise_plan([
            {"id": "a", "description": "a", "depends_on": ["ghost", "a"]},
            {"id": "b", "description": "b", "depends_on": ["a", "ghost"]},
        ])
        self.assertEqual(plan[0]["depends_on"], [])
        self.assertEqual(plan[1]["depends_on"], ["a"])

    def test_deduplicates_ids(self):
        plan = ob._normalise_plan([{"id": "x"}, {"id": "x"}])
        self.assertEqual([s["id"] for s in plan], ["x", "x-2"])

    def test_benchmarks_are_capped(self):
        many = [{"quantity": f"q{i}", "value": i} for i in range(30)]
        plan = ob._normalise_plan([{"id": "a", "benchmarks": many}])
        self.assertEqual(len(plan[0]["benchmarks"]), ob.MAX_BENCHMARKS_PER_STEP)


class RenderTests(unittest.TestCase):
    PLAN = [
        {"id": "environment", "description": "build the code", "command": ". build.sh",
         "check": "build/lib exists", "depends_on": [], "benchmarks": []},
        {"id": "skimming", "description": "apply the selection", "command": "python selector.py",
         "check": "counts match the AN table", "depends_on": ["environment"],
         "benchmarks": [{"quantity": "PNNK threshold", "value": 0.05, "unit": "none",
                         "source": "docs/skimming.rst", "confidence": "extracted-unverified"}]},
    ]
    SUMMARY = {"goal": "count how often matter and antimatter differ",
               "result": "sensitivity 3.4e-4",
               "plan": "skimming -> fits -> asymmetries"}

    def test_markdown_has_goal_result_route_and_table(self):
        md = ob.render_workflow_markdown(self.SUMMARY, self.PLAN)
        self.assertIn("count how often matter and antimatter differ", md)
        self.assertIn("3.4e-4", md)
        self.assertIn("skimming -> fits -> asymmetries", md)
        self.assertIn("PNNK threshold: **0.05**", md)
        self.assertIn("docs/skimming.rst", md)
        self.assertIn("_none extracted - human to supply_", md)
        self.assertIn("never by a guessed number", md)

    def test_render_artifacts_writes_all_three_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = ob.render_artifacts({"workspace": tmp, "summary": self.SUMMARY,
                                       "plan": json.loads(json.dumps(self.PLAN))})
            for name, path in out["artifacts"].items():
                self.assertTrue(Path(path).exists(), name)
            yaml_text = Path(out["artifacts"]["state/pipeline.yaml"]).read_text()
            self.assertIn("extracted-unverified", yaml_text)
            self.assertIn("max_attempts", yaml_text)
            dot = Path(out["artifacts"]["reports/pipeline-dag.dot"]).read_text()
            self.assertIn('"environment" -> "skimming"', dot)
            self.assertTrue(out["checks"]["artifacts"]["ok"])


class GraphShapeTests(unittest.TestCase):
    def test_graph_holds_summary_plan_and_gate_nodes(self):
        nodes = set(ob.build_graph().get_graph().nodes)
        for expected in ("summarize", "approve_summary", "plan_dag",
                         "render_artifacts", "approve_plan"):
            self.assertIn(expected, nodes)

    def test_routing_after_each_gate(self):
        ok = lambda name: {"checks": {name: {"ok": True}}}
        bad = lambda name: {"checks": {name: {"ok": False}}}
        self.assertEqual(ob.after_brain_test(ok("brain_test")), "summarize")
        self.assertEqual(ob.after_brain_test(bad("brain_test")), "build_brain")
        self.assertEqual(ob.after_summary_test(ok("summary_test")), "plan_dag")
        self.assertEqual(ob.after_summary_test(bad("summary_test")), "build_brain")
        self.assertEqual(ob.after_plan_test(ok("plan_test")), "execute")
        self.assertEqual(ob.after_plan_test(bad("plan_test")), "build_brain")

    def test_summarize_without_llm_flags_itself_incomplete(self):
        out = ob.summarize({"workspace": "."})
        self.assertIn("summary", out)
        self.assertFalse(out["checks"]["summary"]["ok"])

    def test_plan_dag_without_llm_falls_back_to_human_verified_steps(self):
        out = ob.plan_dag({"workspace": ".", "summary": {}})
        self.assertEqual(len(out["plan"]), len(ob._FALLBACK_PLAN))
        self.assertTrue(all(s["benchmarks"] == [] for s in out["plan"]))
        self.assertTrue(out["checks"]["plan"]["ok"])


class LoopNodeTests(unittest.TestCase):
    """execute -> validate -> correct -> advance and the smoke test: the
    deterministic loop the harness runs after the plan is approved."""

    PLAN = [{"id": "fit", "description": "run the fit", "command": "python fit.py",
             "check": "rc 0", "depends_on": [], "benchmarks": []}]

    def test_validate_passes_only_on_zero_rc_and_not_stopped(self):
        ok = ob.validate({"last_result": {"returncode": 0}, "step": 0,
                          "checks": {}})
        self.assertTrue(ok["checks"]["validate_0"]["ok"])
        bad = ob.validate({"last_result": {"returncode": 1}, "step": 0, "checks": {}})
        self.assertFalse(bad["checks"]["validate_0"]["ok"])
        stopped = ob.validate({"last_result": {"returncode": 0, "stopped": True},
                               "step": 0, "checks": {}})
        self.assertFalse(stopped["checks"]["validate_0"]["ok"])

    def test_advance_bumps_step_and_resets_loops(self):
        out = ob.advance({"step": 2, "loops": 3})
        self.assertEqual(out, {"step": 3, "loops": 0})

    def test_correct_without_llm_burns_attempts_and_escalates(self):
        # no LLM key in the test env -> no fix -> the identical command cannot
        # change, so loops is pushed to MAX_LOOPS and the check records the
        # escalation instead of spinning.
        state = {"plan": json.loads(json.dumps(self.PLAN)), "step": 0, "loops": 0,
                 "last_result": {"returncode": 1, "stderr_tail": "boom"},
                 "checks": {}}
        out = ob.correct(state)
        self.assertEqual(out["loops"], ob.MAX_LOOPS)
        self.assertFalse(out["checks"]["correct_0_loop5"]["ok"])
        self.assertIn("escalating", out["checks"]["correct_0_loop5"]["evidence"])

    def test_correct_with_a_real_fix_rewrites_the_step(self):
        class _Reply:
            content = '{"command": "python fit.py --fix"}'

        class _LLM:
            def invoke(self, messages):
                return _Reply()

        real = ob._get_llm
        ob._get_llm = lambda: _LLM()
        try:
            state = {"plan": json.loads(json.dumps(self.PLAN)), "step": 0, "loops": 0,
                     "last_result": {"returncode": 1, "stderr_tail": "boom"},
                     "checks": {}}
            out = ob.correct(state)
        finally:
            ob._get_llm = real
        self.assertEqual(out["plan"][0]["command"], "python fit.py --fix")
        self.assertEqual(out["plan"][0]["fixes"], ["python fit.py --fix"])
        self.assertEqual(out["loops"], 0)
        self.assertTrue(out["checks"]["correct_0_loop0"]["ok"])

    def test_after_validate_routes_ok_fail_and_exhausted(self):
        ok = {"last_result": {"returncode": 0}, "step": 0, "loops": 0,
              "checks": {"validate_0": {"ok": True}}}
        self.assertEqual(ob.after_validate(ok), "advance")
        fail = {"last_result": {"returncode": 1}, "step": 0, "loops": 1,
                "checks": {"validate_0": {"ok": False}}}
        self.assertEqual(ob.after_validate(fail), "correct")
        exhausted = {"last_result": {"returncode": 1}, "step": 0,
                     "loops": ob.MAX_LOOPS, "checks": {"validate_0": {"ok": False}}}
        self.assertEqual(ob.after_validate(exhausted), "smoke_test")
        stopped = {"last_result": {"returncode": 0, "stopped": True}, "step": 0,
                   "loops": 0, "checks": {"validate_0": {"ok": True}}}
        self.assertEqual(ob.after_validate(stopped), "smoke_test")

    def test_after_advance_loops_until_plan_done(self):
        self.assertEqual(ob.after_advance({"step": 0, "plan": [1, 1]}), "execute")
        self.assertEqual(ob.after_advance({"step": 2, "plan": [1, 1]}), "smoke_test")


class GateNodeTests(unittest.TestCase):
    """The human gates record the verdict verbatim and drive the rebuild edge."""

    def _drive(self, node, resume):
        """Run a gate node in a throwaway graph and resume it with `resume`."""
        from langgraph.checkpoint.memory import MemorySaver
        from langgraph.graph import END, START, StateGraph
        from langgraph.types import Command

        g = StateGraph(ob.State)
        g.add_node("gate", node)
        g.add_edge(START, "gate")
        g.add_edge("gate", END)
        app = g.compile(checkpointer=MemorySaver())
        cfg = {"configurable": {"thread_id": "t"}}
        out = app.invoke({"checks": {}}, cfg)
        return app.invoke(Command(resume=resume), cfg)

    def test_approve_summary_approve_and_rebuild(self):
        approved = self._drive(ob.approve_summary, "approve")
        self.assertTrue(approved["checks"]["summary_test"]["ok"])
        self.assertIn("user: approve", approved["checks"]["summary_test"]["evidence"])
        rebuilt = self._drive(ob.approve_summary, "rebuild")
        self.assertFalse(rebuilt["checks"]["summary_test"]["ok"])

    def test_approve_plan_approve_and_rebuild(self):
        approved = self._drive(ob.approve_plan, {"verdict": "approve"})
        self.assertTrue(approved["checks"]["plan_test"]["ok"])
        rebuilt = self._drive(ob.approve_plan, {"verdict": "rebuild"})
        self.assertFalse(rebuilt["checks"]["plan_test"]["ok"])

    def test_smoke_test_pass_and_fail(self):
        self.assertTrue(self._drive(ob.smoke_test, "pass")["checks"]["smoke_test"]["ok"])
        self.assertFalse(self._drive(ob.smoke_test, "fail")["checks"]["smoke_test"]["ok"])


if __name__ == "__main__":
    unittest.main()


DEMO_STATE = None


def _demo_state() -> dict:
    """Run the offline demo once and share it across the checks below."""
    global DEMO_STATE
    if DEMO_STATE is None:
        tmp = tempfile.mkdtemp()
        DEMO_STATE = ob.run_demo(tmp, verbose=False)
    return DEMO_STATE


class OfflineDemoTests(unittest.TestCase):
    """`dali-onboard-demo` must tell the whole story with no LLM key and no
    model download: only the embedding model and the chat model are stubbed."""

    def test_every_demo_check_passes(self):
        checks = _demo_state()["checks"]
        for name in ("chunks", "brain", "summary", "plan", "artifacts", "validate_0"):
            self.assertIn(name, checks, name)
            self.assertTrue(checks[name]["ok"], f"{name}: {checks[name]['evidence']}")

    def test_demo_brain_answers_a_real_question(self):
        state = _demo_state()
        answered, evidence = ob._brain_probe(state, "What is the statistical sensitivity?")
        self.assertTrue(answered, evidence)
        # the paper chunk must be the best hit; the demo hashes words, so the
        # ranking is exact but the excerpt is short
        first, _, rest = evidence.partition("\n")
        self.assertIn("paper/main.md", first)
        paper = ob._brain_hits(state, "What is the statistical sensitivity?", k=1)[0]
        self.assertIn("3.4e-4", paper[1])

    def test_demo_summary_comes_from_retrieval_not_a_string(self):
        state = _demo_state()
        hits = ob._brain_hits(state, "What is the statistical sensitivity?", k=3)
        self.assertTrue(hits)
        self.assertIn("3.4e-4", hits[0][1])

    def test_demo_workflow_lists_steps_with_sourced_benchmarks(self):
        state = _demo_state()
        workflow = Path(state["artifacts"]["WORKFLOW.md"]).read_text(encoding="utf-8")
        self.assertIn("Steps and golden benchmarks", workflow)
        self.assertIn("PNNK threshold: **0.05**", workflow)
        self.assertIn("paper/main.md", workflow)
        self.assertIn("_none extracted - human to supply_", workflow)

    def test_demo_dag_has_an_edge_per_dependency(self):
        state = _demo_state()
        dot = Path(state["artifacts"]["reports/pipeline-dag.dot"]).read_text(encoding="utf-8")
        self.assertIn('"skimming" -> "signal"', dot)
        self.assertIn('"efficiency" -> "fit"', dot)

    def test_demo_pipeline_yaml_marks_benchmarks_unverified(self):
        import yaml

        state = _demo_state()
        text = Path(state["artifacts"]["state/pipeline.yaml"]).read_text(encoding="utf-8")
        pipeline = yaml.safe_load(text)
        ids = [s["id"] for s in pipeline["steps"]]
        self.assertIn("cpv", ids)
        flagged = [b for s in pipeline["steps"] for b in s["benchmarks"]]
        self.assertTrue(flagged)
        self.assertTrue(all(b["confidence"] == "extracted-unverified" for b in flagged))
        self.assertTrue(all(b["source"] for b in flagged))

    def test_demo_leaves_the_real_factories_alone(self):
        _demo_state()
        # the demo patches module globals; it must restore them afterwards
        self.assertEqual(ob._get_llm(), None)  # no API keys in a test run
        self.assertTrue(callable(ob._get_embeddings))
