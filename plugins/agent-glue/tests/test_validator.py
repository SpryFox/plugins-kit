from pathlib import Path

import pytest

from agent_glue_lib import (
    Catalog,
    ComponentSchema,
    EntityInstance,
    EntityTypeDef,
    FieldSchema,
    load_instances,
    load_kit,
    load_with_instances,
    validate_all,
    validate_instance,
    validate_kit,
)


def test_shipped_kit_is_self_consistent(plugin_root: Path):
    catalog = load_kit(plugin_root)
    assert validate_kit(catalog) == []


def test_sample_graph_validates_clean(plugin_root: Path, fixtures_root: Path):
    catalog = load_with_instances(
        plugin_root, [fixtures_root / "sample_graph"]
    )
    errors = validate_all(catalog)
    assert errors == [], "sample_graph should validate clean; got: " + "\n".join(errors)


# --- The test gate: every broken fixture must produce a rejection ---


@pytest.mark.parametrize(
    "broken_dir, expected_match",
    [
        ("broken_missing_required", "missing required component 'Topology'"),
        ("broken_unknown_component", "not a known component"),
        ("broken_disallowed_component", "not allowed on this entity type"),
        ("broken_wrong_field_type", "expected string, got int"),
        ("broken_bad_enum", "not in allowed enum values"),
        ("broken_unknown_entity_type", "unknown entity type 'Bogus'"),
    ],
)
def test_broken_fixtures_are_rejected(
    plugin_root: Path, fixtures_root: Path, broken_dir: str, expected_match: str
):
    catalog = load_with_instances(plugin_root, [fixtures_root / broken_dir])
    errors = validate_all(catalog)
    assert errors, f"expected validation errors for {broken_dir}; got none"
    joined = "\n".join(errors)
    assert expected_match in joined, (
        f"expected '{expected_match}' in errors for {broken_dir}; got:\n{joined}"
    )


def test_validate_kit_catches_dangling_component_reference():
    catalog = Catalog(
        component_schemas={
            "Name": ComponentSchema(
                kind="Name",
                fields={"name": FieldSchema(type="string", required=True)},
            )
        },
        entity_types={
            "Thing": EntityTypeDef(
                name="Thing",
                required_components=["Name", "DoesNotExist"],
            )
        },
    )
    errors = validate_kit(catalog)
    assert any("DoesNotExist" in m for m in errors)


def test_validate_instance_catches_unknown_field():
    catalog = Catalog(
        component_schemas={
            "Name": ComponentSchema(
                kind="Name",
                fields={"name": FieldSchema(type="string", required=True)},
            )
        },
        entity_types={
            "Thing": EntityTypeDef(name="Thing", required_components=["Name"]),
        },
    )
    instance = EntityInstance(
        type="Thing",
        components={"name": {"name": "ok", "bogus_field": 1}},
        source_path="<inline>",
    )
    errors = validate_instance(instance, catalog)
    assert any("unknown field 'bogus_field'" in m for m in errors)


def test_validate_instance_catches_missing_required_field():
    catalog = Catalog(
        component_schemas={
            "Name": ComponentSchema(
                kind="Name",
                fields={"name": FieldSchema(type="string", required=True)},
            )
        },
        entity_types={
            "Thing": EntityTypeDef(name="Thing", required_components=["Name"]),
        },
    )
    instance = EntityInstance(
        type="Thing",
        components={"name": {}},
        source_path="<inline>",
    )
    errors = validate_instance(instance, catalog)
    assert any("missing required field 'name'" in m for m in errors)


def test_validate_instance_list_item_type_check():
    catalog = Catalog(
        component_schemas={
            "L": ComponentSchema(
                kind="L",
                fields={
                    "items": FieldSchema(
                        type="list",
                        required=True,
                        items=FieldSchema(type="string"),
                    )
                },
            )
        },
        entity_types={
            "T": EntityTypeDef(name="T", required_components=["L"]),
        },
    )
    instance = EntityInstance(
        type="T",
        components={"l": {"items": ["a", 2, "c"]}},
        source_path="<inline>",
    )
    errors = validate_instance(instance, catalog)
    assert any("expected string" in m and "[1]" in m for m in errors)


def test_validate_instance_map_with_structured_keys():
    catalog = Catalog(
        component_schemas={
            "M": ComponentSchema(
                kind="M",
                fields={
                    "pair": FieldSchema(
                        type="map",
                        required=True,
                        keys={
                            "a": FieldSchema(type="string", required=True),
                            "b": FieldSchema(type="int", required=True),
                        },
                    )
                },
            )
        },
        entity_types={
            "T": EntityTypeDef(name="T", required_components=["M"]),
        },
    )
    instance = EntityInstance(
        type="T",
        components={"m": {"pair": {"a": "ok", "b": "not-an-int", "c": "extra"}}},
        source_path="<inline>",
    )
    errors = validate_instance(instance, catalog)
    joined = "\n".join(errors)
    assert "expected int" in joined
    assert "unknown key 'c'" in joined


def test_validate_instance_open_map_with_value_type():
    catalog = Catalog(
        component_schemas={
            "M": ComponentSchema(
                kind="M",
                fields={
                    "values": FieldSchema(
                        type="map",
                        required=True,
                        value_type=FieldSchema(type="int"),
                    )
                },
            )
        },
        entity_types={
            "T": EntityTypeDef(name="T", required_components=["M"]),
        },
    )
    instance = EntityInstance(
        type="T",
        components={"m": {"values": {"x": 1, "y": "not-int"}}},
        source_path="<inline>",
    )
    errors = validate_instance(instance, catalog)
    assert any("expected int" in m for m in errors)


def test_validate_instance_any_field_accepts_anything():
    catalog = Catalog(
        component_schemas={
            "F": ComponentSchema(
                kind="F",
                fields={"value": FieldSchema(type="any", required=True)},
            )
        },
        entity_types={
            "T": EntityTypeDef(name="T", required_components=["F"]),
        },
    )
    for payload in [{"nested": {"deep": [1, 2]}}, "hello", [1, 2, 3], 42, True]:
        instance = EntityInstance(
            type="T",
            components={"f": {"value": payload}},
            source_path="<inline>",
        )
        assert validate_instance(instance, catalog) == []
