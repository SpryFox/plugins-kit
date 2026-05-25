from pathlib import Path

import pytest
import yaml

from agent_glue_lib import (
    LoaderError,
    dump_instance,
    load_component_schemas,
    load_entity_types,
    load_instances,
    load_kit,
    load_with_instances,
)


def test_load_kit_picks_up_every_schema(plugin_root: Path):
    catalog = load_kit(plugin_root)
    # 6 cross-cutting + 22 graph + 21 work = 49 (Phase 1 total)
    assert len(catalog.component_schemas) == 49
    assert "Name" in catalog.component_schemas
    assert "SourceRunId" in catalog.component_schemas
    assert "Topology" in catalog.component_schemas
    assert "WorkerSelection" in catalog.component_schemas


def test_load_kit_picks_up_every_entity_type(plugin_root: Path):
    catalog = load_kit(plugin_root)
    assert len(catalog.entity_types) == 10
    expected = {
        "Graph", "Node", "Edge", "Cohort", "Fixture", "ExpectedOutcome",
        "WorkRequest", "WorkResult", "Worker", "WorkRecord",
    }
    assert set(catalog.entity_types) == expected


def test_entity_type_required_optional_lists_populated(plugin_root: Path):
    catalog = load_kit(plugin_root)
    node = catalog.entity_types["Node"]
    assert "Name" in node.required_components
    assert "Topology" in node.required_components
    assert "Implementation" in node.required_components
    assert "Rules" in node.optional_components
    assert "Prompt" in node.optional_components
    assert "Outputs" in node.optional_components


def test_load_instances_skips_non_instance_yamls(fixtures_root: Path):
    instances = load_instances(fixtures_root / "sample_graph")
    types_present = sorted(i.type for i in instances)
    assert types_present == ["Edge", "Edge", "Graph", "Node", "Node"]


def test_load_with_instances(plugin_root: Path, fixtures_root: Path):
    catalog = load_with_instances(
        plugin_root, [fixtures_root / "sample_graph"]
    )
    assert len(catalog.entities) == 5


def test_round_trip_dump_matches_source(fixtures_root: Path):
    src = fixtures_root / "sample_graph" / "nodes" / "load" / "node.yaml"
    instances = load_instances(src)
    assert len(instances) == 1
    instance = instances[0]

    dumped = dump_instance(instance)
    redumped_loaded = yaml.safe_load(dumped)
    original_loaded = yaml.safe_load(src.read_text(encoding="utf-8"))
    assert redumped_loaded == original_loaded


def test_round_trip_dump_all_sample_instances(fixtures_root: Path):
    sample_dir = fixtures_root / "sample_graph"
    for path in sorted(sample_dir.rglob("*.yaml")):
        original = yaml.safe_load(path.read_text(encoding="utf-8"))
        if not isinstance(original, dict) or "type" not in original:
            continue
        instances = load_instances(path)
        assert len(instances) == 1
        redumped = yaml.safe_load(dump_instance(instances[0]))
        assert redumped == original, f"round-trip mismatch for {path}"


def test_component_schema_filename_must_match_kind(tmp_path: Path):
    bad = tmp_path / "Whatever.yaml"
    bad.write_text("kind: Different\nfields: {}\n", encoding="utf-8")
    with pytest.raises(LoaderError, match="does not match kind"):
        load_component_schemas(tmp_path)


def test_component_schema_duplicate_kind_rejected(tmp_path: Path):
    d1 = tmp_path / "a"
    d2 = tmp_path / "b"
    d1.mkdir()
    d2.mkdir()
    (d1 / "Foo.yaml").write_text("kind: Foo\nfields: {}\n", encoding="utf-8")
    (d2 / "Foo.yaml").write_text("kind: Foo\nfields: {}\n", encoding="utf-8")
    with pytest.raises(LoaderError, match="duplicate component schema kind 'Foo'"):
        load_component_schemas(d1, d2)


def test_entity_type_filename_must_match_name(tmp_path: Path):
    bad = tmp_path / "Whatever.yaml"
    bad.write_text("name: Different\n", encoding="utf-8")
    with pytest.raises(LoaderError, match="does not match entity-type name"):
        load_entity_types(tmp_path)


def test_instance_extra_top_level_keys_rejected(tmp_path: Path):
    bad = tmp_path / "x.yaml"
    bad.write_text(
        "type: Node\ncomponents: {}\nextra_key: oops\n", encoding="utf-8"
    )
    with pytest.raises(LoaderError, match="unexpected keys"):
        load_instances(bad)


def test_instance_required_file_missing_type_rejected(tmp_path: Path):
    bad = tmp_path / "x.yaml"
    bad.write_text("components: {}\n", encoding="utf-8")
    with pytest.raises(LoaderError, match="missing required key 'type'"):
        load_instances(bad)


def test_load_instances_directory_ignores_files_without_type(tmp_path: Path):
    (tmp_path / "sidecar.yaml").write_text("foo: bar\n", encoding="utf-8")
    instances = load_instances(tmp_path)
    assert instances == []


def test_load_kit_against_missing_directory_returns_empty(tmp_path: Path):
    catalog = load_kit(tmp_path)
    assert catalog.component_schemas == {}
    assert catalog.entity_types == {}
