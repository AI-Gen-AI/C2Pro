"""PC-2b.3 (#922) -- the deterministic WBS import parser (acceptance C, F, H and resource safety).

The parser turns untrusted ``.xlsx``/``.csv``/``wbs-import/v1`` bytes into one deterministic
``wbs-import-snapshot/v1``: hierarchy from every method present (they must agree), never repaired
silently, codes never identity, schedule/cost data never WBS authority, nothing executed.
"""

from __future__ import annotations

import io
import json
import zipfile
from typing import Any

import pytest
from openpyxl import Workbook

from src.wbs.imports.config import ImportConfigError
from src.wbs.imports.contracts import (
    MAX_ROWS,
    PARSERS,
    SNAPSHOT_SCHEMA_VERSION,
    ImportFormat,
    ImportStatus,
    ParseResult,
    Severity,
)
from src.wbs.imports.parser import parse_source

F = ImportFormat


def _codes(result: ParseResult, severity: Severity | None = None) -> set[str]:
    return {d.code for d in result.diagnostics if severity is None or d.severity is severity}


def _blocking(result: ParseResult) -> set[str]:
    return _codes(result, Severity.BLOCKING_ERROR)


def _parents(result: ParseResult) -> dict[str, str | None]:
    return {row.source_ref: row.parent_source_ref for row in result.rows}


def _xlsx(sheets: dict[str, list[list[Any]]]) -> bytes:
    workbook = Workbook()
    workbook.remove(workbook.active)
    for title, rows in sheets.items():
        sheet = workbook.create_sheet(title)
        for row in rows:
            sheet.append(row)
    buffer = io.BytesIO()
    workbook.save(buffer)
    return buffer.getvalue()


def _json(nodes: list[dict[str, Any]], **extra: Any) -> bytes:
    return json.dumps({"format": "wbs-import/v1", "nodes": nodes, **extra}).encode()


# ---------------------------------------------------------------------------------------- C. parser
def test_17_xlsx_parent_code_hierarchy() -> None:
    data = _xlsx({"WBS": [["Code", "Name", "Parent Code"], ["1", "Plant", None], ["1.1", "Civil", "1"],
                          ["1.2", "Electrical", "1"], ["1.2.1", "Cabling", "1.2"]]})
    result = parse_source(F.XLSX, data)
    assert result.status is ImportStatus.READY and result.sheet == "WBS"
    assert _parents(result) == {"sheet:WBS/row:2": None, "sheet:WBS/row:3": "sheet:WBS/row:2",
                                "sheet:WBS/row:4": "sheet:WBS/row:2", "sheet:WBS/row:5": "sheet:WBS/row:4"}
    assert (result.parser_id, result.parser_version) == PARSERS[F.XLSX] == ("wbs-xlsx", "v1")


def test_18_xlsx_outline_level_hierarchy() -> None:
    data = _xlsx({"WBS": [["WBS", "Title", "Outline Level"], ["1", "Plant", 1], ["1.1", "Civil", 2],
                          ["1.1.1", "Piling", 3], ["1.2", "Electrical", 2]]})
    result = parse_source(F.XLSX, data)
    assert result.status is ImportStatus.READY
    assert [r.outline_level for r in result.rows] == [1, 2, 3, 2]
    assert _parents(result)["sheet:WBS/row:5"] == "sheet:WBS/row:2"


def test_19_csv_parent_code_hierarchy_and_children_before_parents() -> None:
    result = parse_source(F.CSV, b"code,name,parent_code\n1.1,Civil,1\n1,Plant,\n")
    assert result.status is ImportStatus.READY
    assert _parents(result) == {"row:2": "row:3", "row:3": None}


def test_20_csv_level_hierarchy_with_semicolon_detected() -> None:
    result = parse_source(F.CSV, "código;name;level\n1;Plant;1\n1.1;Civil;2\n".replace("código", "code").encode())
    assert result.status is ImportStatus.READY and result.parse_config == {"delimiter": None}
    assert _parents(result) == {"row:2": None, "row:3": "row:2"}


def test_21_json_wbs_import_v1() -> None:
    result = parse_source(F.JSON, _json([
        {"id": "A", "code": "1", "name": "Platform", "level": 1},
        {"id": "B", "parent_id": "A", "code": "1.1", "name": "Billing", "level": 2,
         "dictionary": {"scope_statement": "Invoices", "deliverables": ["API"]}},
    ]))
    assert result.status is ImportStatus.READY
    assert _parents(result) == {"/nodes/0": None, "/nodes/1": "/nodes/0"}
    assert result.rows[1].dictionary and result.rows[1].dictionary["deliverables"] == ["API"]
    assert result.rows[1].external_id == "B"  # a SOURCE identifier only


def test_22_unsupported_json_version_and_arbitrary_json_are_rejected() -> None:
    assert "UNSUPPORTED_CONTRACT_VERSION" in _blocking(parse_source(F.JSON, b'{"format":"wbs-import/v2","nodes":[]}'))
    assert parse_source(F.JSON, b'[{"name":"x"}]').status is ImportStatus.INVALID
    assert parse_source(F.JSON, b'{"name":"not a wbs"}').status is ImportStatus.INVALID
    unknown = parse_source(F.JSON, _json([{"name": "x", "level": 1}], owner="me"))
    assert "JSON_UNKNOWN_FIELD" in _blocking(unknown)


def test_23_cycle_is_blocking() -> None:
    result = parse_source(F.CSV, b"code,name,parent_code\n1,A,3\n2,B,1\n3,C,2\n")
    assert result.status is ImportStatus.INVALID and "PARENT_CYCLE" in _blocking(result)
    assert all(row.parent_source_ref is None for row in result.rows)  # never moved to root as a "repair"


def test_23b_self_parent_is_blocking() -> None:
    assert "SELF_PARENT" in _blocking(parse_source(F.CSV, b"code,name,parent_code\n1,A,1\n"))


def test_24_orphan_is_blocking() -> None:
    result = parse_source(F.CSV, b"code,name,parent_code\n1,A,\n1.1,B,9\n")
    assert "PARENT_UNRESOLVED" in _blocking(result)
    assert _parents(result)["row:3"] is None and result.status is ImportStatus.INVALID


def test_25_ambiguous_parent_is_blocking() -> None:
    result = parse_source(F.JSON, _json([{"id": "a", "name": "A", "parent_id": None}, {"id": "a", "name": "A2"},
                                         {"id": "c", "name": "C", "parent_id": "a"}]))
    assert {"DUPLICATE_SOURCE_IDENTITY", "PARENT_AMBIGUOUS"} <= _blocking(result)


def test_26_parent_code_and_level_that_disagree_are_blocking() -> None:
    result = parse_source(F.CSV, b"code,name,parent_code,level\n1,A,,1\n1.1,B,1,2\n1.2,C,1.1,2\n")
    assert "HIERARCHY_CONFLICT" in _blocking(result)
    agree = parse_source(F.CSV, b"code,name,parent_code,level\n1,A,,1\n1.1,B,1,2\n1.1.1,C,1.1,3\n")
    assert agree.status is ImportStatus.READY  # both methods describe the same tree: PASS


def test_27_level_jump_is_blocking() -> None:
    assert "LEVEL_JUMP" in _blocking(parse_source(F.CSV, b"code,name,level\n1,A,1\n1.1.1,B,3\n"))
    assert "LEVEL_JUMP" in _blocking(parse_source(F.CSV, b"code,name,level\n1,A,2\n"))  # impossible root depth
    assert "LEVEL_INVALID" in _blocking(parse_source(F.CSV, b"code,name,level\n1,A,one\n"))


def test_28_duplicate_code_is_a_warning_when_hierarchy_is_unambiguous() -> None:
    result = parse_source(F.CSV, b"code,name,level\n1,Root,1\n1.1,A,2\n1.1,B,2\n")
    assert result.status is ImportStatus.READY_WITH_WARNINGS and _codes(result) == {"CODE_DUPLICATE"}
    duplicated = [r for r in result.rows if r.raw_code == "1.1"]
    assert [r.normalized_code for r in duplicated] == [None, None]  # never guess which one keeps it
    assert all(r.parent_source_ref == "row:2" for r in duplicated)


def test_29_duplicate_parent_code_is_blocking() -> None:
    result = parse_source(F.CSV, b"code,name,parent_code\n1,Root,\n2,A,1\n2,B,1\n2.1,Child,2\n")
    assert "PARENT_AMBIGUOUS" in _blocking(result)


def test_30_formulas_are_never_evaluated() -> None:
    data = _xlsx({"WBS": [["code", "name", "level"], ["1", "Root", 1], ["=1+0.1", "Calculated", 2],
                          ["1.2", '=CONCAT("a","b")', 2]]})
    result = parse_source(F.XLSX, data)
    assert result.status is ImportStatus.INVALID and "FORMULA_NOT_ALLOWED" in _blocking(result)
    assert {d.field for d in result.diagnostics if d.code == "FORMULA_NOT_ALLOWED"} == {"code", "name"}
    # In CSV a leading '=' is DATA, never a formula.
    csv_result = parse_source(F.CSV, b"code,name,level\n1,=SUM(A1:A2),1\n")
    assert csv_result.status is ImportStatus.READY and csv_result.rows[0].name == "=SUM(A1:A2)"


def test_31_several_matching_sheets_require_explicit_selection() -> None:
    data = _xlsx({"WBS A": [["code", "name", "level"], ["1", "A", 1]],
                  "WBS B": [["code", "name", "parent_code"], ["1", "B", None]],
                  "Notes": [["anything"], ["x"]]})
    assert "SHEET_SELECTION_REQUIRED" in _blocking(parse_source(F.XLSX, data))
    chosen = parse_source(F.XLSX, data, {"sheet": "WBS B"})
    assert chosen.status is ImportStatus.READY and chosen.sheet == "WBS B" and chosen.rows[0].name == "B"
    assert "SHEET_NOT_FOUND" in _blocking(parse_source(F.XLSX, data, {"sheet": "Sheet1"}))


def test_name_is_required_and_never_invented() -> None:
    assert "NAME_REQUIRED" in _blocking(parse_source(F.CSV, b"code,name,level\n1,,1\n"))
    assert "MISSING_NAME_COLUMN" in _blocking(parse_source(F.CSV, b"code,label,level\n1,x,1\n", {"delimiter": ","}))
    assert "MISSING_HIERARCHY_COLUMNS" in _blocking(parse_source(F.CSV, b"code,name\n1,x\n", {"delimiter": ","}))


def test_invalid_code_becomes_null_with_a_warning() -> None:
    result = parse_source(F.CSV, ("code,name,level\n" + "X" * 60 + ",Too long,1\n").encode())
    assert result.status is ImportStatus.READY_WITH_WARNINGS and _codes(result) == {"CODE_INVALID"}
    assert result.rows[0].normalized_code is None and result.rows[0].raw_code == "X" * 60


# ---------------------------------------------------------------------------------------- F. digest
def test_49_same_normalized_snapshot_same_digest() -> None:
    data = b"code,name,parent_code\n1,Plant,\n1.1,Civil,1\n"
    first, again = parse_source(F.CSV, data), parse_source(F.CSV, data)
    assert first.snapshot_digest == again.snapshot_digest and first.snapshot["schema"] == SNAPSHOT_SCHEMA_VERSION
    assert parse_source(F.CSV, data, {}).parse_config_digest == parse_source(F.CSV, data, {"delimiter": None}
                                                                            ).parse_config_digest
    assert parse_source(F.CSV, b"code,name,parent_code\n1,Plant,\n1.1,Civils,1\n").snapshot_digest != first.snapshot_digest


def test_diagnostic_wording_is_not_digest_bound_but_codes_are() -> None:
    result = parse_source(F.CSV, b"code,name,level\n1,Root,1\n1.1,A,2\n1.1,B,2\n")
    identities = result.snapshot["diagnostics"]
    assert identities and all(set(d) == {"severity", "code", "source_ref", "field"} for d in identities)


def test_51_parse_config_changes_identity_and_is_strict() -> None:
    data = b"code,name,level\n1,Root,1\n"
    assert parse_source(F.CSV, data, {"delimiter": ","}).parse_config_digest != parse_source(F.CSV, data
                                                                                            ).parse_config_digest
    with pytest.raises(ImportConfigError):
        parse_source(F.CSV, data, {"delimiter": "|"})
    with pytest.raises(ImportConfigError):
        parse_source(F.JSON, _json([]), {"sheet": "x"})


# ---------------------------------------------------------------------------------------- H. honesty
def test_58_59_schedule_columns_never_become_wbs_dates_or_structure() -> None:
    result = parse_source(F.CSV, b"code,name,level,planned_start,planned_finish,duration,predecessors\n"
                                 b"1,Project,1,2026-01-01,2026-12-31,365d,\n1.1,Design,2,2026-01-01,2026-02-01,30d,9\n")
    assert result.status is ImportStatus.READY_WITH_WARNINGS
    ignored = {d.field for d in result.diagnostics if d.code == "SCHEDULE_FIELD_IGNORED"}
    assert ignored == {"planned_start", "planned_finish", "duration", "predecessors"}
    assert _parents(result) == {"row:2": None, "row:3": "row:2"}  # predecessors never become structure
    serialized = json.dumps(result.snapshot)
    assert "2026-01-01" not in serialized and "365d" not in serialized
    rejected = parse_source(F.JSON, _json([{"name": "A", "level": 1, "planned_start": "2026-01-01"}]))
    assert "SCHEDULE_FIELD_REJECTED" in _blocking(rejected)


def test_60_cost_columns_never_become_wbs_cost_authority() -> None:
    result = parse_source(F.CSV, b"code,name,level,budget,unit_cost,quantity\n1,Plant,1,1000000,5,3\n")
    assert {d.field for d in result.diagnostics if d.code == "COST_FIELD_IGNORED"} == {"budget", "unit_cost",
                                                                                      "quantity"}
    assert "1000000" not in json.dumps(result.snapshot)
    assert "COST_FIELD_REJECTED" in _blocking(parse_source(F.JSON, _json([{"name": "A", "level": 1, "cost": 5}])))


def test_json_cannot_carry_authority_or_canonical_ids() -> None:
    for key in ("approved", "baseline_id", "submitted_by", "approver", "node_id", "status"):
        result = parse_source(F.JSON, _json([{"name": "A", "level": 1, key: "x"}]))
        assert "AUTHORITY_FIELD_REJECTED" in _blocking(result), key


# ---------------------------------------------------------------------------------------- resource safety
def test_42_bounds_on_untrusted_input() -> None:
    rows = "".join(f"{i},n{i},1\n" for i in range(MAX_ROWS + 1))
    assert "TOO_MANY_ROWS" in _blocking(parse_source(F.CSV, ("code,name,level\n" + rows).encode()))
    wide = ",".join(f"c{i}" for i in range(80))
    assert "TOO_MANY_COLUMNS" in _blocking(parse_source(F.CSV, f"name,level,{wide}\nx,1\n".encode(), {"delimiter": ","}))
    assert "CELL_TOO_LONG" in _blocking(parse_source(F.CSV, ("code,name,level\n1," + "x" * 5000 + ",1\n").encode()))
    assert "JSON_TOO_DEEP" in _blocking(parse_source(F.JSON, b'{"format":"wbs-import/v1","nodes":[' + b"[" * 50
                                                     + b"]" * 50 + b"]}"))
    assert "JSON_DUPLICATE_KEY" in _blocking(parse_source(F.JSON, b'{"format":"wbs-import/v1","format":"x","nodes":[]}'))
    assert "CSV_ENCODING" in _blocking(parse_source(F.CSV, b"code,name,level\n1,\xff\xfe,1\n"))
    assert "CSV_INVALID" in _blocking(parse_source(F.CSV, b"code,name,level\n1,\"unterminated,1\n", {"delimiter": ","}))
    assert "XLSX_UNREADABLE" in _blocking(parse_source(F.XLSX, b"PK\x03\x04 not really a zip"))


def test_42b_macro_workbooks_and_zip_bombs_are_refused_before_parsing() -> None:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("xl/vbaProject.bin", b"\x00" * 10)
    assert "XLSX_MACROS_NOT_SUPPORTED" in _blocking(parse_source(F.XLSX, buffer.getvalue()))
    bomb = io.BytesIO()
    with zipfile.ZipFile(bomb, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("xl/worksheets/sheet1.xml", b"0" * (65 * 1024 * 1024))
    assert "XLSX_TOO_LARGE" in _blocking(parse_source(F.XLSX, bomb.getvalue()))


# ---------------------------------------------------------------------------------------- 46. generality
SOLAR_EPC = b"""code,name,parent_code
1,Solar PV Plant 50MW,
1.1,Civil Works,1
1.1.1,Site Preparation,1.1
1.2,PV Array,1
1.2.1,Mounting Structures,1.2
1.2.2,PV Modules,1.2
1.3,Electrical Collection,1
"""

CIVIL_LINEAR = [["code", "name", "level"], ["H", "Highway A-12 km 0-24", 1], ["H.S1", "Section 1 km 0-8", 2],
                ["H.S1.E", "Earthworks", 3], ["H.S1.P", "Pavement", 3], ["H.S2", "Section 2 km 8-24", 2],
                ["H.S2.B", "Bridge over river", 3]]

SOFTWARE_SAAS = [
    {"id": "p", "code": "SaaS", "name": "Billing platform", "level": 1, "decomposition_kind": "core:capability"},
    {"id": "a", "parent_id": "p", "code": "SaaS.1", "name": "Identity", "level": 2},
    {"id": "b", "parent_id": "p", "code": "SaaS.2", "name": "Invoicing API", "level": 2,
     "dictionary": {"acceptance_criteria": ["p95 < 200ms"]}},
    {"id": "c", "parent_id": "b", "code": "SaaS.2.1", "name": "Tax engine integration", "level": 3},
]


def test_46_generic_wbs_shapes_import_without_epc_assumptions() -> None:
    solar = parse_source(F.CSV, SOLAR_EPC)
    civil = parse_source(F.XLSX, _xlsx({"Road WBS": CIVIL_LINEAR}))
    saas = parse_source(F.JSON, _json(SOFTWARE_SAAS))
    for result, size in ((solar, 7), (civil, 6), (saas, 4)):
        assert result.status is ImportStatus.READY, result.diagnostics
        assert len(result.rows) == size and sum(r.parent_source_ref is None for r in result.rows) == 1
    names = {r.name for r in saas.rows}
    assert not names & {"Engineering", "Procurement", "Construction", "Commissioning"}
    assert saas.rows[0].decomposition_kind == "core:capability"
