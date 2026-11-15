import json

import pytest

from viza_sandbox.catalog import CATALOG_VERSION, load_catalog

BASE = [
    "ret_1d", "ret_5d", "ret_21d", "ret_63d", "ret_252d", "vol_21d", "vol_63d",
    "ma_20d", "ma_50d", "ma_200d", "rsi_14d", "adv_21d",
]


def _entry(key, formula="simple_return", inputs=("close",)):
    return {
        "key": key, "display_name": key, "description": key, "unit": "ratio",
        "formula": formula, "params": {"window": 1}, "inputs": list(inputs),
        "availability_rule": "eod_of_latest_input", "source_type": "viza_computed",
        "rights_class": "viza_computed",
    }


def _write(tmp_path, attributes):
    path = tmp_path / "catalog.json"
    path.write_text(json.dumps({"catalog_version": CATALOG_VERSION, "attributes": attributes}))
    return path


def test_catalog_has_the_24_seed_keys():
    catalog = load_catalog()
    assert catalog.catalog_version == CATALOG_VERSION == "viza_sandbox_catalog_v1"
    assert catalog.keys() == BASE + [f"{k}_sector_z" for k in BASE]
    assert [a.key for a in catalog.base()] == BASE


def test_sector_relative_entries_point_at_their_base_and_are_flagged():
    relative = load_catalog().sector_relative()
    assert len(relative) == 12
    for spec in relative:
        assert spec.formula == "sector_zscore"
        assert spec.inputs == [spec.key.removesuffix("_sector_z")]
        assert spec.classification_snapshot is True


def test_every_entry_is_viza_computed():
    for spec in load_catalog().attributes:
        assert (spec.source_type, spec.rights_class) == ("viza_computed", "viza_computed")
        assert spec.availability_rule == "eod_of_latest_input"


def test_base_entries_carry_their_window_and_inputs():
    by_key = {spec.key: spec for spec in load_catalog().attributes}
    assert by_key["ret_252d"].params == {"window": 252}
    assert by_key["vol_21d"].inputs == ["ret_1d"]
    assert by_key["adv_21d"].inputs == ["close", "volume"]
    assert by_key["rsi_14d"].formula == "rsi_cutler"


def test_loader_rejects_duplicate_keys(tmp_path):
    path = _write(tmp_path, [_entry("ret_1d"), _entry("ret_1d")])
    with pytest.raises(ValueError, match="duplicate attribute keys: ret_1d"):
        load_catalog(path)


def test_loader_rejects_unknown_inputs(tmp_path):
    path = _write(tmp_path, [_entry("x_sector_z", "sector_zscore", ("nope",))])
    with pytest.raises(ValueError, match="unknown input: nope"):
        load_catalog(path)
