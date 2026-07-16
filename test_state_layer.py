#!/usr/bin/env python3
"""
Unit tests for state_layer's ground-state persistence, focused on the
hand-rolled cross-platform file locking in _write_locked().

Run: python -m unittest test_state_layer -v
"""
import json
import tempfile
import threading
import unittest
from pathlib import Path

import state_layer as sl


class TestSaveLoadRoundtrip(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmpdir.cleanup)
        self._orig_path = sl.GROUND_STATE_PATH
        sl.GROUND_STATE_PATH = Path(self.tmpdir.name) / "ground_state.json"
        self.addCleanup(lambda: setattr(sl, "GROUND_STATE_PATH", self._orig_path))

    def test_save_then_load_roundtrips_content(self):
        sl.save_state({"goal": "ship it"})
        loaded = sl.load_state()
        self.assertEqual(loaded["goal"], "ship it")
        self.assertIn("last_updated", loaded)  # save_state stamps this itself

    def test_save_overwrites_cleanly_not_append(self):
        sl.save_state({"version": 1, "big_field": "x" * 500})
        sl.save_state({"version": 2})
        loaded = sl.load_state()
        self.assertEqual(loaded["version"], 2)
        self.assertNotIn("big_field", loaded)  # confirms a full overwrite, not a merge/append


class TestConcurrentWrites(unittest.TestCase):
    """The whole point of _write_locked is that concurrent writers can't corrupt
    the file into something that isn't valid JSON, or an interleaved mix of two
    writes. This can't prove perfect ordering, but it can prove atomicity."""

    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmpdir.cleanup)
        self._orig_path = sl.GROUND_STATE_PATH
        sl.GROUND_STATE_PATH = Path(self.tmpdir.name) / "ground_state.json"
        self.addCleanup(lambda: setattr(sl, "GROUND_STATE_PATH", self._orig_path))
        # seed the file so load_state() doesn't exit(1) on a missing file
        sl.save_state({"marker": -1})

    def test_concurrent_writes_never_corrupt_the_file(self):
        N = 20
        # deliberately different payload sizes so a torn/interleaved write would
        # very likely fail to parse as JSON or land on a value we never wrote.
        errors = []

        def writer(i):
            try:
                payload = {"marker": i, "padding": str(i) * (50 + i * 7)}
                sl.save_state(payload)
            except Exception as e:  # pragma: no cover - failure path we're checking for
                errors.append(e)

        threads = [threading.Thread(target=writer, args=(i,)) for i in range(N)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        self.assertEqual(errors, [], f"writer thread(s) raised: {errors}")

        # The file must parse as complete, valid JSON -- not truncated or interleaved.
        raw = sl.GROUND_STATE_PATH.read_text(encoding="utf-8")
        state = json.loads(raw)  # raises if corrupted

        # And its content must be exactly one writer's complete payload, not a
        # mix of two (which would prove a lock actually held across the write).
        marker = state["marker"]
        self.assertIn(marker, range(N))
        expected_padding = str(marker) * (50 + marker * 7)
        self.assertEqual(state["padding"], expected_padding)


if __name__ == "__main__":
    unittest.main()
