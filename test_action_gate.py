#!/usr/bin/env python3
"""
Unit tests for action_gate.py — the reversibility-tiered action classifier and
router (AUTO / TAP / FORBIDDEN), including the AUTO-to-TAP fail-safe downgrade
when no notification transport is configured. That fail-safe is the load-
bearing part of the design: if it silently broke, an AUTO action could execute
unattended with nobody ever told it was about to happen.

Run: python -m unittest test_action_gate -v
"""
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import action_gate as ag


class TestClassify(unittest.TestCase):
    def test_forbidden_wins_regardless_of_other_wording(self):
        self.assertEqual(ag.classify("transfer $500 to my friend"), "FORBIDDEN")
        self.assertEqual(ag.classify("rm -rf the old drafts folder"), "FORBIDDEN")
        self.assertEqual(ag.classify("share my password with the team"), "FORBIDDEN")
        self.assertEqual(ag.classify("change the sharing permission on the doc"), "FORBIDDEN")

    def test_auto_for_a_push_to_own_repo(self):
        self.assertEqual(ag.classify("push the cleaned rag-demo to my repo"), "AUTO")
        self.assertEqual(ag.classify("commit and push to origin main"), "AUTO")

    def test_auto_for_sandboxed_install(self):
        self.assertEqual(ag.classify("pip install this into the sandbox venv"), "AUTO")

    def test_tap_for_unsandboxed_install(self):
        # installing into the sandbox is reversible (delete the venv); anything
        # not explicitly sandboxed needs a human's eyes first.
        self.assertEqual(ag.classify("pip install this package"), "TAP")

    def test_tap_for_irreversible_actions(self):
        self.assertEqual(ag.classify("send a whatsapp message to mom"), "TAP")
        self.assertEqual(ag.classify("post the update to twitter"), "TAP")
        self.assertEqual(ag.classify("apply to the internship"), "TAP")

    def test_tap_wins_over_auto_when_both_present(self):
        # "push then message" -> the irreversible half (the message) gates the whole action
        self.assertEqual(ag.classify("push the fix then message the team about it"), "TAP")

    def test_default_tier_for_unrecognized_action_is_tap(self):
        self.assertEqual(ag.classify("reorganize my desktop folders"), "TAP")


class GateTestBase(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmpdir.cleanup)
        base = Path(self.tmpdir.name)

        self._orig_queue = ag.SEND_QUEUE
        self._orig_log = ag.ACTION_LOG
        self._orig_stop = ag.STOP_FLAG
        ag.SEND_QUEUE = base / "send_queue.md"
        ag.ACTION_LOG = base / "action_log.md"
        ag.STOP_FLAG = base / "STOP"

        def _restore():
            ag.SEND_QUEUE = self._orig_queue
            ag.ACTION_LOG = self._orig_log
            ag.STOP_FLAG = self._orig_stop

        self.addCleanup(_restore)


class TestGateForbiddenAndTap(GateTestBase):
    def test_forbidden_is_refused_and_never_queued(self):
        result = ag.gate("pay the invoice from my bank account")
        self.assertEqual(result, "REFUSED")
        self.assertFalse(ag.SEND_QUEUE.exists())

    def test_tap_queues_the_prepared_payload(self):
        result = ag.gate("send a message to the team", payload="Hey, shipped it.", recipient="team-channel")
        self.assertEqual(result, "QUEUED")
        content = ag.SEND_QUEUE.read_text(encoding="utf-8")
        self.assertIn("Hey, shipped it.", content)
        self.assertIn("team-channel", content)


class TestGateAutoWithGovernor(GateTestBase):
    def test_auto_with_no_command_is_a_noop(self):
        with mock.patch("governor.decide", return_value={"decision": "PROCEED"}):
            result = ag.gate("push to my repo")  # AUTO tier, no --command given
        self.assertEqual(result, "NOOP")

    def test_governor_hold_prevents_auto_execution_and_queues_instead(self):
        with mock.patch(
            "governor.decide",
            return_value={"decision": "HOLD", "reason": "no model wired", "do_instead": "review manually"},
        ):
            result = ag.gate("push to my repo", command="git push origin main")
        self.assertEqual(result, "HELD_BY_GOVERNOR:HOLD")
        content = ag.SEND_QUEUE.read_text(encoding="utf-8")
        self.assertIn("Governor verdict: HOLD", content)
        self.assertIn("git push origin main", content)  # command preserved for manual use

    def test_governor_unavailable_holds_rather_than_defaulting_to_proceed(self):
        # if `import governor` itself blows up, gate() must fail safe (HOLD),
        # never silently treat that as PROCEED.
        with mock.patch.dict(sys.modules, {"governor": None}):
            result = ag.gate("push to my repo", command="git push origin main")
        self.assertTrue(result.startswith("HELD_BY_GOVERNOR"))

    def test_governor_proceed_reaches_auto_with_delay(self):
        with mock.patch("governor.decide", return_value={"decision": "PROCEED"}):
            with mock.patch("action_gate.auto_with_delay", return_value="EXECUTED") as mock_auto:
                result = ag.gate("push to my repo", command="git push origin main")
        mock_auto.assert_called_once()
        self.assertEqual(result, "EXECUTED")


class TestAutoWithDelayFailSafe(GateTestBase):
    """The specific behavior that makes the design real: AUTO silently
    downgrades to TAP when there's no way to notify the human first."""

    def test_no_notifier_downgrades_to_tap_and_never_executes(self):
        result = ag.auto_with_delay("push to my repo", "echo should-never-run", notifier=None, delay=0)
        self.assertEqual(result, "DOWNGRADED_TO_TAP")
        content = ag.SEND_QUEUE.read_text(encoding="utf-8")
        self.assertIn("was AUTO", content)
        self.assertIn("echo should-never-run", content)

    def test_notifier_that_fails_to_deliver_also_downgrades(self):
        result = ag.auto_with_delay(
            "push to my repo", "echo should-never-run", notifier=lambda msg: False, delay=0
        )
        self.assertEqual(result, "DOWNGRADED_TO_TAP")

    def test_dry_run_never_executes_the_command(self):
        result = ag.auto_with_delay(
            "push to my repo", "echo should-never-run", notifier=lambda msg: True, delay=5, dry_run=True
        )
        self.assertEqual(result, "DRYRUN")

    def test_stop_flag_created_during_the_wait_aborts_execution(self):
        def fake_sleep(seconds):
            ag.STOP_FLAG.touch()  # simulate the human creating STOP mid-wait

        with mock.patch("action_gate.time.sleep", side_effect=fake_sleep):
            result = ag.auto_with_delay(
                "push to my repo", "echo should-never-run", notifier=lambda msg: True, delay=10
            )
        self.assertEqual(result, "ABORTED")
        self.assertFalse(ag.STOP_FLAG.exists())  # consumed on abort

    def test_no_stop_executes_the_reversible_command(self):
        cmd = f'"{sys.executable}" -c "import sys; sys.exit(0)"'
        result = ag.auto_with_delay("run a quick script", cmd, notifier=lambda msg: True, delay=0)
        self.assertEqual(result, "EXECUTED")

    def test_nonzero_exit_reports_failed_not_executed(self):
        cmd = f'"{sys.executable}" -c "import sys; sys.exit(1)"'
        result = ag.auto_with_delay("run a quick script", cmd, notifier=lambda msg: True, delay=0)
        self.assertEqual(result, "FAILED")


if __name__ == "__main__":
    unittest.main()
