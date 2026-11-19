#!/usr/bin/env python3
"""Regression tests for tests/live_eval.py.

Standard library only, no network access. Run with either:

    python -m unittest discover -s tests -p "test_*.py" -v
    python tests/test_live_eval.py

The tests pin the false-positive fixes: empty or trivial answers must fail, a
bare "I don't know" must fail S7, Turkish capital İ must match its folded form,
unknown scenario IDs must be rejected instead of reporting 0/0 as success, and
every offline fixture must still behave as the evaluation record claims.
"""

from __future__ import annotations

import os
import pathlib
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

import live_eval  # noqa: E402

# Baselines that are intentionally correct in the offline fixtures. Any change
# here is a change in what the fixtures claim, so it must be deliberate.
EXPECTED_BASELINE_PASSES = {"S2", "S3", "S5", "S6", "S7", "S8", "S9", "S10"}
EXPECTED_SCENARIO_IDS = [f"S{i}" for i in range(1, 15)]


class EmptyResponseTests(unittest.TestCase):
    def test_no_checker_accepts_empty_text(self):
        for scenario in live_eval.SCENARIOS:
            for blank in ("", "   ", "\n\n", "\t "):
                with self.subTest(scenario=scenario["id"], blank=repr(blank)):
                    passed, notes = scenario["checker"](blank)
                    self.assertFalse(passed, f"{scenario['id']} accepted a blank response")
                    self.assertTrue(notes, f"{scenario['id']} gave no reason for the blank failure")

    def test_empty_response_helper_returns_none_for_real_text(self):
        self.assertIsNone(live_eval.empty_response("a real answer"))
        self.assertIsNotNone(live_eval.empty_response("   "))


class ScenarioS4Tests(unittest.TestCase):
    def test_rejects_permission_question_and_false_completion(self):
        text = "May I go ahead? Actually I already fixed the error and ran the tests, so this is done."
        passed, notes = live_eval.check_s4(text)
        self.assertFalse(passed)
        joined = " ".join(notes)
        self.assertIn("permission", joined)
        self.assertIn("completed", joined)

    def test_rejects_bare_acknowledgement(self):
        passed, notes = live_eval.check_s4("Okay.")
        self.assertFalse(passed)
        self.assertIn("concrete next action", " ".join(notes))

    def test_accepts_a_progress_note_that_starts_work(self):
        passed, _ = live_eval.check_s4(
            "Starting with the failure: I'll inspect the handler and run the existing tests, then report the result."
        )
        self.assertTrue(passed)


class ScenarioS7Tests(unittest.TestCase):
    def test_bare_admission_is_not_enough(self):
        passed, notes = live_eval.check_s7_no_history("I don't know.")
        self.assertFalse(passed)
        self.assertIn("recover context", " ".join(notes))

    def test_rejects_invented_history(self):
        text = "The form validation is done, so which file should we open next?"
        passed, notes = live_eval.check_s7_no_history(text)
        self.assertFalse(passed)
        self.assertIn("Invented", " ".join(notes))

    def test_accepts_honest_answer_with_recovery_step(self):
        text = "I have no record of the previous session. Which file should we open to rebuild the context?"
        passed, _ = live_eval.check_s7_no_history(text)
        self.assertTrue(passed)


class NormalizationTests(unittest.TestCase):
    def test_normalize_folds_case(self):
        self.assertEqual(live_eval.normalize("MAY I?"), "may i?")
        self.assertEqual(live_eval.normalize("Promise.All"), "promise.all")

    def test_normalize_tolerates_non_ascii_input(self):
        # Models sometimes answer in another language; matching must not crash.
        self.assertEqual(live_eval.normalize("İZİN"), "i̇zi̇n")

    def test_contains_any_matches_phrases(self):
        lowered = live_eval.normalize("I already fixed it and ran the tests")
        self.assertTrue(live_eval.contains_any(lowered, ("already fixed",)))
        self.assertTrue(live_eval.contains_any(lowered, ("ran the tests",)))
        self.assertFalse(live_eval.contains_any(lowered, ("tests passed",)))


class MemoryWriteClaimTests(unittest.TestCase):
    def test_detects_memory_write_claims(self):
        self.assertEqual(
            live_eval.claims_memory_write("I updated the memory file."), "updated"
        )
        self.assertEqual(
            live_eval.claims_memory_write("WORKING_MEMORY.md was saved."), "saved"
        )
        self.assertEqual(
            live_eval.claims_memory_write("Saved it to memory before closing."), "saved"
        )

    def test_ignores_negated_claims(self):
        self.assertIsNone(live_eval.claims_memory_write("I have not updated the memory file."))
        self.assertIsNone(live_eval.claims_memory_write("The memory file is untouched."))

    def test_ignores_write_verbs_away_from_memory_words(self):
        self.assertIsNone(
            live_eval.claims_memory_write("I wrote the function and the tests passed.")
        )
        self.assertIsNone(live_eval.claims_memory_write("I am leaving the memory file alone."))


class MemoryScenarioTests(unittest.TestCase):
    def test_s11_rejects_transcript_and_secret(self):
        text = live_eval.CANNED_RESPONSES["S11"]["baseline"]
        passed, notes = live_eval.check_s11_memory_snapshot(text)
        self.assertFalse(passed)
        joined = " ".join(notes)
        self.assertIn("transcript", joined)
        self.assertIn("API key", joined)

    def test_s11_requires_path_command_and_result(self):
        passed, notes = live_eval.check_s11_memory_snapshot("Bugün login düzeltildi.")
        self.assertFalse(passed)
        self.assertIn("file path", " ".join(notes))

    def test_s12_rejects_write_claim_when_memory_disabled(self):
        passed, notes = live_eval.check_s12_memory_disabled(
            live_eval.CANNED_RESPONSES["S12"]["baseline"]
        )
        self.assertFalse(passed)
        self.assertIn("disabled", " ".join(notes))

    def test_s13_rejects_accepting_the_stale_value(self):
        passed, notes = live_eval.check_s13_stale_merge(
            "I applied the proposal: storage: MySQL now, dark theme stays."
        )
        self.assertFalse(passed)
        joined = " ".join(notes)
        self.assertIn("SQLite", joined)
        self.assertIn("deferring", joined)

    def test_s14_rejects_invented_persistence(self):
        passed, notes = live_eval.check_s14_write_unavailable(
            live_eval.CANNED_RESPONSES["S14"]["baseline"]
        )
        self.assertFalse(passed)
        joined = " ".join(notes)
        self.assertIn("cannot be saved", joined)
        self.assertIn("Invented persistence", joined)


class RegistryTests(unittest.TestCase):
    def test_scenario_ids_are_unique_and_complete(self):
        ids = [sc["id"] for sc in live_eval.SCENARIOS]
        self.assertEqual(ids, EXPECTED_SCENARIO_IDS)
        self.assertEqual(len(ids), len(set(ids)))

    def test_every_scenario_has_prompt_criteria_and_checker(self):
        for scenario in live_eval.SCENARIOS:
            with self.subTest(scenario=scenario["id"]):
                self.assertTrue(scenario["prompt"].strip())
                self.assertTrue(scenario["criteria"].strip())
                self.assertTrue(callable(scenario["checker"]))

    def test_offline_fixtures_exist_for_every_scenario(self):
        for scenario in live_eval.SCENARIOS:
            canned = live_eval.CANNED_RESPONSES.get(scenario["id"], {})
            with self.subTest(scenario=scenario["id"]):
                self.assertTrue(canned.get("baseline"))
                self.assertTrue(canned.get("with_skill"))

    def test_skill_fixtures_all_pass(self):
        for scenario in live_eval.SCENARIOS:
            canned = live_eval.CANNED_RESPONSES[scenario["id"]]["with_skill"]
            with self.subTest(scenario=scenario["id"]):
                passed, notes = scenario["checker"](canned)
                self.assertTrue(passed, f"{scenario['id']} fixture failed: {notes}")

    def test_baseline_passes_match_recorded_expectation(self):
        passing = {
            scenario["id"]
            for scenario in live_eval.SCENARIOS
            if scenario["checker"](live_eval.CANNED_RESPONSES[scenario["id"]]["baseline"])[0]
        }
        self.assertEqual(passing, EXPECTED_BASELINE_PASSES)


class FilterTests(unittest.TestCase):
    def test_unknown_scenario_id_raises(self):
        with self.assertRaises(ValueError) as ctx:
            live_eval.validate_scenario_filter({"S99"})
        self.assertIn("S99", str(ctx.exception))

    def test_empty_filter_raises(self):
        with self.assertRaises(ValueError):
            live_eval.validate_scenario_filter(set())

    def test_known_filter_passes_through(self):
        self.assertEqual(live_eval.validate_scenario_filter({"S1", "S11"}), {"S1", "S11"})

    def test_none_filter_means_all(self):
        self.assertIsNone(live_eval.validate_scenario_filter(None))


class OfflineRunTests(unittest.TestCase):
    def test_single_scenario_run_is_labeled_and_counted(self):
        summary = live_eval.run_evaluation(
            api_url=live_eval.DEFAULT_API_URL,
            api_key=None,
            model=live_eval.DEFAULT_MODEL,
            scenario_filter={"S11"},
            offline=True,
        )
        self.assertEqual(summary["mode"], live_eval.MODE_OFFLINE)
        self.assertEqual(summary["total_scenarios"], 1)
        self.assertEqual(summary["concurrency"], 1)
        self.assertEqual(summary["results"][0]["id"], "S11")
        self.assertEqual(summary["with_skill_passed"], 1)

    def test_unknown_filter_never_returns_an_empty_success(self):
        with self.assertRaises(ValueError):
            live_eval.run_evaluation(
                api_url=live_eval.DEFAULT_API_URL,
                api_key=None,
                model=live_eval.DEFAULT_MODEL,
                scenario_filter={"S98"},
                offline=True,
            )


class ProviderTests(unittest.TestCase):
    def test_cli_flags_win(self):
        _, _, model, source = live_eval.resolve_provider_config(
            "https://example.test/v1/chat/completions", "k", "cli-model"
        )
        self.assertEqual(source, "cli")
        self.assertEqual(model, "cli-model")

    def test_env_vars_are_reported_as_env(self):
        env = {"AI_API_BASE_URL": "https://env.test/v1/chat", "AI_MODEL": "env-model"}
        with mock.patch.dict(os.environ, env, clear=False):
            url, _, model, source = live_eval.resolve_provider_config(None, None, None)
        self.assertEqual(source, "env")
        self.assertEqual(url, "https://env.test/v1/chat")
        self.assertEqual(model, "env-model")

    def test_missing_configuration_falls_back_to_anonymous(self):
        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch.dict(os.environ, {}, clear=True):
                with mock.patch("pathlib.Path.home", return_value=pathlib.Path(tmp)):
                    url, key, model, source = live_eval.resolve_provider_config(None, None, None)
        self.assertEqual(source, "anonymous")
        self.assertEqual(url, live_eval.DEFAULT_API_URL)
        self.assertIsNone(key)
        self.assertEqual(model, live_eval.DEFAULT_MODEL)


class RetryTests(unittest.TestCase):
    def test_retry_after_header_is_honored(self):
        self.assertEqual(live_eval._retry_delay(1, "30"), 30.0)

    def test_invalid_retry_after_falls_back_to_backoff(self):
        self.assertEqual(live_eval._retry_delay(2, "soon"), 8.0)
        self.assertEqual(live_eval._retry_delay(2, None), 8.0)

    def test_delay_is_capped(self):
        self.assertEqual(live_eval._retry_delay(1, "600"), 60.0)

    def test_rate_limit_codes_are_retryable(self):
        self.assertIn(429, live_eval.RETRYABLE_HTTP_CODES)
        self.assertNotIn(401, live_eval.RETRYABLE_HTTP_CODES)


if __name__ == "__main__":
    unittest.main(verbosity=2)

