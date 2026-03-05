"""Tests for bootstrap lib/log.py."""

import os
import re

from log import LOG_FILENAME, MAX_LOG_LINES, write_log


class TestWriteLog:
    def test_creates_log_file(self, data_dir):
        write_log(data_dir, ["test entry"])
        log_path = os.path.join(data_dir, LOG_FILENAME)
        assert os.path.exists(log_path)

    def test_appends_entries(self, data_dir):
        write_log(data_dir, ["first"])
        write_log(data_dir, ["second"])
        log_path = os.path.join(data_dir, LOG_FILENAME)
        with open(log_path) as f:
            lines = f.readlines()
        assert len(lines) == 2
        assert "first" in lines[0]
        assert "second" in lines[1]

    def test_entries_have_timestamps(self, data_dir):
        write_log(data_dir, ["timestamped"])
        log_path = os.path.join(data_dir, LOG_FILENAME)
        with open(log_path) as f:
            line = f.readline()
        # ISO 8601 UTC: [2024-01-15T12:00:00Z]
        assert re.match(r"\[\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z\]", line)

    def test_trims_at_max_lines(self, data_dir):
        # Write more than MAX_LOG_LINES
        for i in range(MAX_LOG_LINES + 50):
            write_log(data_dir, [f"entry-{i}"])
        log_path = os.path.join(data_dir, LOG_FILENAME)
        with open(log_path) as f:
            lines = f.readlines()
        assert len(lines) <= MAX_LOG_LINES
        # Oldest entries should be trimmed, newest kept
        assert "entry-" in lines[-1]
