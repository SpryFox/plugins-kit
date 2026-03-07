"""Tests for bootstrap lib/log.py."""

import os
import re

from log import LOG_FILENAME, MAX_LOG_LINES, write_log_block


class TestWriteLogBlock:
    def test_creates_log_file(self, data_dir):
        write_log_block(data_dir, "Test", ["test entry"])
        log_path = os.path.join(data_dir, LOG_FILENAME)
        assert os.path.exists(log_path)

    def test_writes_header_and_entries(self, data_dir):
        write_log_block(data_dir, "Engine", ["first", "second"])
        log_path = os.path.join(data_dir, LOG_FILENAME)
        with open(log_path) as f:
            lines = f.readlines()
        assert len(lines) == 3
        assert lines[0].startswith("--- Engine ")
        assert lines[0].strip().endswith(" ---")
        assert "first" in lines[1]
        assert "second" in lines[2]

    def test_entries_are_plain_text(self, data_dir):
        write_log_block(data_dir, "Engine", ["timestamped"])
        log_path = os.path.join(data_dir, LOG_FILENAME)
        with open(log_path) as f:
            lines = f.readlines()
        # Entry lines are plain text (no timestamp prefix); header has the timestamp
        assert lines[1].strip() == "timestamped"
        assert re.match(r"--- Engine \d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z ---", lines[0])

    def test_separate_blocks_have_separate_headers(self, data_dir):
        write_log_block(data_dir, "Shell", ["entry one"])
        write_log_block(data_dir, "Engine", ["entry two"])
        log_path = os.path.join(data_dir, LOG_FILENAME)
        with open(log_path) as f:
            lines = f.readlines()
        assert len(lines) == 4
        assert lines[0].startswith("--- Shell ")
        assert "entry one" in lines[1]
        assert lines[2].startswith("--- Engine ")
        assert "entry two" in lines[3]

    def test_empty_entries_noop(self, data_dir):
        write_log_block(data_dir, "Engine", [])
        log_path = os.path.join(data_dir, LOG_FILENAME)
        assert not os.path.exists(log_path)

    def test_trims_at_max_lines(self, data_dir):
        # Write more than MAX_LOG_LINES across multiple blocks
        for i in range(MAX_LOG_LINES + 50):
            write_log_block(data_dir, "Test", [f"entry-{i}"])
        log_path = os.path.join(data_dir, LOG_FILENAME)
        with open(log_path) as f:
            lines = f.readlines()
        assert len(lines) <= MAX_LOG_LINES
        # Newest entries should be kept
        assert "entry-" in lines[-1]
