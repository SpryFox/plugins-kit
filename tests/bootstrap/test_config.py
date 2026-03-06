"""Tests for bootstrap engine/config.py."""

import json
import os

from config import CURRENT_SCHEMA_VERSION, load_config, migrate_config, save_config


class TestLoadConfig:
    def test_copies_defaults_on_first_load(self, data_dir, defaults_dir):
        config = load_config(data_dir, defaults_dir)
        # Config file should now exist in data_dir
        config_path = os.path.join(data_dir, "config.json")
        assert os.path.exists(config_path)
        assert config["schema_version"] == CURRENT_SCHEMA_VERSION

    def test_loads_existing_config(self, data_dir, defaults_dir):
        # Pre-create a current-version config
        config_path = os.path.join(data_dir, "config.json")
        existing = {
            "schema_version": CURRENT_SCHEMA_VERSION,
            "custom_field": "keep_me", "enabled_plugins": [], "log_level": "info",
            "log_success_shell": False, "log_success_checks": False,
        }
        with open(config_path, "w") as f:
            json.dump(existing, f)

        config = load_config(data_dir, defaults_dir)
        assert config["custom_field"] == "keep_me"


class TestMigrateConfig:
    def test_migrates_v0_to_current(self):
        v0 = {"some_setting": True}
        migrated = migrate_config(v0)
        assert migrated["schema_version"] == CURRENT_SCHEMA_VERSION
        assert "enabled_plugins" not in migrated
        assert "no_bootstrap" in migrated
        assert "bootstrap_cache" in migrated
        assert "log_success_shell" in migrated
        assert "log_success_checks" in migrated
        assert migrated["some_setting"] is True

    def test_migrates_v1_to_current(self):
        v1 = {"schema_version": 1, "enabled_plugins": [], "log_level": "info"}
        migrated = migrate_config(v1)
        assert migrated["schema_version"] == CURRENT_SCHEMA_VERSION
        assert "enabled_plugins" not in migrated
        assert migrated["no_bootstrap"] == []
        assert migrated["bootstrap_cache"] == []
        assert migrated["log_success_shell"] is False
        assert migrated["log_success_checks"] is False

    def test_migrates_v2_to_current(self):
        v2 = {"schema_version": 2, "enabled_plugins": [], "log_level": "info",
               "log_success_shell": True, "log_success_checks": True}
        migrated = migrate_config(v2)
        assert migrated["schema_version"] == CURRENT_SCHEMA_VERSION
        assert "enabled_plugins" not in migrated
        assert migrated["no_bootstrap"] == []
        assert migrated["bootstrap_cache"] == []
        assert migrated["log_success_shell"] is False
        assert migrated["log_success_checks"] is False

    def test_migrates_v3_to_current(self):
        v3 = {"schema_version": 3, "enabled_plugins": ["kit:a"], "log_success_shell": False, "log_success_checks": False}
        migrated = migrate_config(v3)
        assert migrated["schema_version"] == CURRENT_SCHEMA_VERSION
        assert "enabled_plugins" not in migrated
        assert migrated["no_bootstrap"] == []
        assert migrated["bootstrap_cache"] == []

    def test_no_migration_on_current_version(self):
        current = {
            "schema_version": CURRENT_SCHEMA_VERSION,
            "enabled_plugins": [], "log_level": "info",
            "log_success_shell": False, "log_success_checks": False,
        }
        result = migrate_config(current)
        assert result is current  # Same object — no copy needed


class TestSaveConfig:
    def test_save_config_roundtrip(self, data_dir):
        original = {"schema_version": 1, "enabled_plugins": ["test"], "log_level": "debug"}
        save_config(data_dir, original)

        config_path = os.path.join(data_dir, "config.json")
        with open(config_path) as f:
            loaded = json.load(f)
        assert loaded == original
