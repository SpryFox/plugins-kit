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
        # Pre-create a config
        config_path = os.path.join(data_dir, "config.json")
        existing = {"schema_version": 1, "custom_field": "keep_me", "enabled_plugins": [], "log_level": "info"}
        with open(config_path, "w") as f:
            json.dump(existing, f)

        config = load_config(data_dir, defaults_dir)
        assert config["custom_field"] == "keep_me"


class TestMigrateConfig:
    def test_migrates_v0_to_v1(self):
        v0 = {"some_setting": True}
        migrated = migrate_config(v0)
        assert migrated["schema_version"] == 1
        assert "enabled_plugins" in migrated
        assert "log_level" in migrated
        assert migrated["some_setting"] is True

    def test_no_migration_on_current_version(self):
        v1 = {"schema_version": 1, "enabled_plugins": [], "log_level": "info"}
        result = migrate_config(v1)
        assert result is v1  # Same object — no copy needed


class TestSaveConfig:
    def test_save_config_roundtrip(self, data_dir):
        original = {"schema_version": 1, "enabled_plugins": ["test"], "log_level": "debug"}
        save_config(data_dir, original)

        config_path = os.path.join(data_dir, "config.json")
        with open(config_path) as f:
            loaded = json.load(f)
        assert loaded == original
