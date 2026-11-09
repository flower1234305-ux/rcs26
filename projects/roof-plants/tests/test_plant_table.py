"""plants.csv is the copy people edit; plants.json is made from it, and nothing is lost either way."""

import json
import os

import pytest

from roof_plants.plant_table import COLUMNS, EXTRA, REQUIRED, csv_to_json, csv_to_records, json_to_csv, main
from roof_plants.plants import REQUIRED as USED
from roof_plants.plants import load_plants, opening_spec

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def read(name, encoding="utf-8"):
    with open(os.path.join(HERE, name), encoding=encoding, newline="") as f:
        return f.read()


def test_the_required_columns_are_the_ones_the_program_reads():
    assert REQUIRED == USED
    assert COLUMNS[:len(REQUIRED)] == REQUIRED and set(EXTRA).isdisjoint(REQUIRED)


def test_json_to_csv_and_back_is_lossless():
    data = json.loads(read("plants.json"))
    assert json.loads(csv_to_json(json_to_csv(data))) == data
    assert csv_to_json(json_to_csv(data)) == read("plants.json").replace("\r\n", "\n")     # to the byte


def test_plants_csv_and_plants_json_are_in_step():
    """Edit plants.csv, then run ``python -m roof_plants.plant_table csv2json plants.csv plants.json``.

    Run it in projects/roof-plants, where both files are.
    """
    assert read("plants.csv", "utf-8").startswith("\ufeff"), "plants.csv must keep its BOM, for Excel"
    assert csv_to_json(read("plants.csv", "utf-8-sig")) == read("plants.json").replace("\r\n", "\n")


def test_numbers_stay_numbers():
    (record,) = csv_to_records("id,name_zh,root_type,growth,offset,rim,depth,depth_datum,source,root_spread_mm\n"
                               "a,甲,x,x,-300,80,360.5,local_min,x,1e3\n")
    assert record["offset"] == -300 and isinstance(record["offset"], int)
    assert record["depth"] == 360.5 and isinstance(record["root_spread_mm"], float)


def test_empty_new_columns_are_left_out_and_the_record_still_works():
    header = ",".join(COLUMNS)
    row = "a,甲,x,x,0,220,350,nominal,x" + "," * len(EXTRA)
    (record,) = csv_to_records(header + "\n" + row + "\n")
    assert set(record) == set(REQUIRED)
    assert opening_spec(record)["top"] == 220.0


def test_a_new_column_is_carried_through():
    header = ",".join(COLUMNS)
    row = "a,甲,x,x,0,220,350,nominal,x,Sedum sp.,,,,,,,,,p. 12"
    (record,) = csv_to_records(header + "\n" + row + "\n")
    assert record["name_sci"] == "Sedum sp." and record["source_pages"] == "p. 12"


def test_a_required_cell_left_empty_names_its_row():
    with pytest.raises(ValueError, match="row 2"):
        csv_to_records("id,name_zh,root_type,growth,offset,rim,depth,depth_datum,source\na,甲,x,x,,80,360,nominal,x\n")


def test_a_word_in_a_number_column_names_it():
    with pytest.raises(ValueError, match="depth must be a number"):
        csv_to_records("id,name_zh,root_type,growth,offset,rim,depth,depth_datum,source\na,甲,x,x,0,80,deep,nominal,x\n")


def test_the_command_line_round_trip(tmp_path):
    csv_path, json_path = str(tmp_path / "p.csv"), str(tmp_path / "p.json")
    assert main(["json2csv", os.path.join(HERE, "plants.json"), csv_path]) == 0
    assert main(["csv2json", csv_path, json_path]) == 0
    assert load_plants(json_path) == load_plants(os.path.join(HERE, "plants.json"))
    assert main(["nonsense"]) == 2
