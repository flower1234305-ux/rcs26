"""The plant database as a table: ``plants.csv`` for people, ``plants.json`` for the program.

    cd projects/roof-plants
    uv run python -m roof_plants.plant_table csv2json plants.csv plants.json
    uv run python -m roof_plants.plant_table json2csv plants.json plants.csv

``plants.csv`` is the copy people edit (in Excel or any spreadsheet); it is
written as UTF-8 with a byte order mark, so Excel opens the Chinese names
correctly. ``plants.json`` is generated from it and is what
:func:`roof_plants.plants.load_plants` reads.

The program uses only the geometry columns (:data:`roof_plants.plants.REQUIRED`).
The other columns (:data:`EXTRA`) hold what the plants are known to need, for
the research and for later conversions; any of them may be left empty, and an
empty cell is simply not written to the JSON. Numbers stay numbers: a column
in :data:`NUMBERS` becomes an ``int`` when it is a whole number and a ``float``
otherwise, so JSON -> CSV -> JSON gives back the same records.

Standard library only.
"""

import csv
import io
import json
import sys

__all__ = ["REQUIRED", "EXTRA", "COLUMNS", "NUMBERS", "records_to_csv", "csv_to_records", "json_to_csv", "csv_to_json",
           "write_csv", "write_json"]

#: The fields the program uses, in the order of ``roof_plants.plants.REQUIRED``.
REQUIRED = ("id", "name_zh", "root_type", "growth", "offset", "rim", "depth", "depth_datum", "source")

#: Fields for what the plant needs; empty until a sourced value is known.
EXTRA = ("name_sci", "name_common", "soil_depth_min_mm", "soil_depth_rec_mm", "root_spread_mm",
         "mature_weight_kg_m2", "water_need", "drought_tolerance", "sun_need", "source_pages")

#: Every column of ``plants.csv``, in order.
COLUMNS = REQUIRED + EXTRA

#: Columns read as numbers.
NUMBERS = ("offset", "rim", "depth", "soil_depth_min_mm", "soil_depth_rec_mm", "root_spread_mm",
           "mature_weight_kg_m2")

BOM = "﻿"


def _number(text, column, row):
    try:
        value = float(text)
    except ValueError:
        raise ValueError("row {} ({}): {} must be a number, got {!r}".format(row, column, column, text)) from None
    return int(value) if value.is_integer() and "." not in text and "e" not in text.lower() else value


def records_to_csv(records):
    """Plant records (dicts) as CSV text, with :data:`COLUMNS` first and any other keys after them."""
    extra = []
    for record in records:
        extra += [k for k in record if k not in COLUMNS and k not in extra]
    out = io.StringIO()
    writer = csv.DictWriter(out, fieldnames=list(COLUMNS) + extra, lineterminator="\r\n")
    writer.writeheader()
    for record in records:
        writer.writerow({k: ("" if v is None else v) for k, v in record.items()})
    return out.getvalue()


def csv_to_records(text):
    """CSV text (with or without a byte order mark) as plant records.

    Empty cells are left out of the record. A missing required column, or a
    required cell left empty, raises ``ValueError`` naming the row.
    """
    reader = csv.DictReader(io.StringIO(text[len(BOM):] if text.startswith(BOM) else text))
    missing = [c for c in REQUIRED if c not in (reader.fieldnames or [])]
    if missing:
        raise ValueError("plants.csv is missing column(s): {}".format(", ".join(missing)))
    records = []
    for n, row in enumerate(reader, start=2):        # row 1 is the header
        if not any((v or "").strip() for v in row.values()):
            continue
        record = {}
        for column, text in row.items():
            text = (text or "").strip()
            if not text:
                continue
            record[column] = _number(text, column, n) if column in NUMBERS else text
        empty = [c for c in REQUIRED if c not in record]
        if empty:
            raise ValueError("row {} ({}): required cell(s) empty: {}".format(n, record.get("id", "?"),
                                                                                ", ".join(empty)))
        records.append(record)
    return records


def json_to_csv(data):
    """The parsed ``plants.json`` (``{"plants": [...]}``) as CSV text."""
    return records_to_csv(data["plants"])


def csv_to_json(text):
    """CSV text as the ``plants.json`` text, formatted as the file in the repository is."""
    return json.dumps({"plants": csv_to_records(text)}, indent=1, ensure_ascii=False) + "\n"


def write_csv(json_path, csv_path):
    """``plants.json`` -> ``plants.csv``, UTF-8 with a byte order mark."""
    with open(json_path, encoding="utf-8") as f:
        text = json_to_csv(json.load(f))
    with open(csv_path, "w", encoding="utf-8-sig", newline="") as f:
        f.write(text)
    return csv_path


def write_json(csv_path, json_path):
    """``plants.csv`` -> ``plants.json``."""
    with open(csv_path, encoding="utf-8-sig", newline="") as f:
        text = csv_to_json(f.read())
    with open(json_path, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)
    return json_path


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    commands = {"csv2json": write_json, "json2csv": write_csv}
    if len(argv) != 3 or argv[0] not in commands:
        print(__doc__.split("\n\n")[1])
        return 2
    print("wrote", commands[argv[0]](argv[1], argv[2]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
