"""Tests for LoaderConfig: validation, env overlay, file loading."""

from __future__ import annotations

import dataclasses
import json
from pathlib import Path

import pytest

from flashcards.config import LoaderConfig, _coerce
from flashcards.exceptions import ConfigError


class TestDefaultsAndValidation:
    def test_defaults_are_sane(self):
        config = LoaderConfig()
        assert config.max_cards == 10_000
        assert config.on_invalid_card == "raise"
        assert config.dedupe is True

    @pytest.mark.parametrize(
        "field",
        [
            "max_file_bytes",
            "max_cards",
            "max_field_length",
            "max_tags",
            "max_tag_length",
        ],
    )
    @pytest.mark.parametrize("bad", [0, -1, 1.5, "10", True])
    def test_positive_int_fields_reject_bad_values(self, field, bad):
        with pytest.raises(ConfigError, match=field):
            LoaderConfig(**{field: bad})

    def test_cache_size_zero_allowed_negative_rejected(self):
        assert LoaderConfig(cache_size=0).cache_size == 0
        with pytest.raises(ConfigError, match="cache_size"):
            LoaderConfig(cache_size=-1)

    def test_invalid_policy_rejected(self):
        with pytest.raises(ConfigError, match="on_invalid_card"):
            LoaderConfig(on_invalid_card="explode")

    @pytest.mark.parametrize(
        "bad", [0, -2, "5", True, float("nan"), float("inf"), float("-inf")]
    )
    def test_timeout_must_be_positive_number(self, bad):
        with pytest.raises(ConfigError, match="request_timeout"):
            LoaderConfig(request_timeout=bad)

    @pytest.mark.parametrize("field", ["dedupe", "allow_empty"])
    def test_bool_fields_reject_non_bool(self, field):
        with pytest.raises(ConfigError, match=field):
            LoaderConfig(**{field: "yes"})

    def test_unknown_encoding_rejected(self):
        with pytest.raises(ConfigError, match="encoding"):
            LoaderConfig(encoding="klingon-8")

    def test_config_is_immutable(self):
        config = LoaderConfig()
        with pytest.raises(dataclasses.FrozenInstanceError):
            config.max_cards = 1  # type: ignore[misc]
        assert config.max_cards == 10_000


class TestReplaceAndMapping:
    def test_replace_returns_new_validated_instance(self):
        base = LoaderConfig()
        updated = base.replace(max_cards=5)
        assert updated.max_cards == 5 and base.max_cards == 10_000

    def test_replace_rejects_unknown_option(self):
        with pytest.raises(ConfigError, match="Unknown config option"):
            LoaderConfig().replace(colour="blue")

    def test_replace_validates_new_value(self):
        with pytest.raises(ConfigError):
            LoaderConfig().replace(max_cards=0)

    def test_from_mapping(self):
        config = LoaderConfig.from_mapping({"dedupe": False, "max_tags": 3})
        assert config.dedupe is False and config.max_tags == 3


class TestFromFile:
    def test_loads_json_object(self, tmp_path: Path):
        path = tmp_path / "cfg.json"
        path.write_text(json.dumps({"max_cards": 42}), encoding="utf-8")
        assert LoaderConfig.from_file(path).max_cards == 42

    def test_missing_file(self, tmp_path: Path):
        with pytest.raises(ConfigError, match="not found"):
            LoaderConfig.from_file(tmp_path / "nope.json")

    def test_directory_is_os_error(self, tmp_path: Path):
        with pytest.raises(ConfigError, match="Could not read"):
            LoaderConfig.from_file(tmp_path)

    def test_malformed_json(self, tmp_path: Path):
        path = tmp_path / "cfg.json"
        path.write_text("{bad json", encoding="utf-8")
        with pytest.raises(ConfigError, match="not valid JSON"):
            LoaderConfig.from_file(path)

    def test_non_object_rejected(self, tmp_path: Path):
        path = tmp_path / "cfg.json"
        path.write_text("[1, 2]", encoding="utf-8")
        with pytest.raises(ConfigError, match="single JSON object"):
            LoaderConfig.from_file(path)


class TestFromEnv:
    def test_no_variables_returns_base_unchanged(self):
        base = LoaderConfig(max_cards=7)
        assert LoaderConfig.from_env({}, base=base) is base

    def test_overlays_typed_values(self):
        env = {
            "FLASHCARD_MAX_CARDS": " 250 ",
            "FLASHCARD_DEDUPE": "FALSE",
            "FLASHCARD_ALLOW_EMPTY": "yes",
            "FLASHCARD_REQUEST_TIMEOUT": "2.5",
            "FLASHCARD_ENCODING": "latin-1",
            "FLASHCARD_ON_INVALID_CARD": "skip",
            "UNRELATED": "ignored",
        }
        config = LoaderConfig.from_env(env)
        assert config.max_cards == 250
        assert config.dedupe is False
        assert config.allow_empty is True
        assert config.request_timeout == 2.5
        assert config.encoding == "latin-1"
        assert config.on_invalid_card == "skip"

    def test_custom_prefix(self):
        config = LoaderConfig.from_env({"FC_MAX_TAGS": "3"}, prefix="FC_")
        assert config.max_tags == 3

    @pytest.mark.parametrize(
        "var, value",
        [
            ("FLASHCARD_MAX_CARDS", "lots"),
            ("FLASHCARD_DEDUPE", "maybe"),
            ("FLASHCARD_REQUEST_TIMEOUT", "soon"),
        ],
    )
    def test_bad_values_raise_config_error(self, var, value):
        with pytest.raises(ConfigError, match="not a valid"):
            LoaderConfig.from_env({var: value})

    def test_uses_process_environment_by_default(self, monkeypatch):
        monkeypatch.setenv("FLASHCARD_MAX_CARDS", "9")
        assert LoaderConfig.from_env().max_cards == 9


def test_coerce_passes_strings_through():
    assert _coerce("encoding", str, " utf-8 ") == "utf-8"
    assert _coerce("encoding", "str", "x") == "x"


class TestBoundariesAndMessages:
    def test_sub_second_timeout_is_valid(self):
        assert LoaderConfig(request_timeout=0.5).request_timeout == 0.5

    def test_env_error_names_the_field(self):
        with pytest.raises(ConfigError, match="'max_cards'"):
            LoaderConfig.from_env({"FLASHCARD_MAX_CARDS": "x"})

    def test_minimum_positive_values_accepted(self):
        config = LoaderConfig(
            max_cards=1, max_tags=1, max_tag_length=1, max_field_length=1
        )
        assert config.max_cards == 1
