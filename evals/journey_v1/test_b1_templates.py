"""B1 red/green contract: immutable public EPC taxonomy and blank oracle.

No real contracts or per-contract values may appear in these templates.
"""
from __future__ import annotations

import csv
from pathlib import Path

import yaml

HERE = Path(__file__).resolve().parent
FIELDS = [
    "id", "tipo", "critico", "presente", "clausula",
    "pagina", "cita_ancla", "cifras_esperadas", "dimension",
]
# Independently transcribed control catalog from JV1 plan §6.2.
EXPECTED = [
    ("EPC-01", "Precio y moneda", "BUDGET", True),
    ("EPC-02", "Hitos/calendario de pagos y condiciones", "BUDGET", True),
    ("EPC-03", "Retenciones, avales y garantías financieras", "BUDGET", True),
    ("EPC-04", "Plazo / fechas de terminación garantizadas", "TIME", True),
    ("EPC-05", "Penalizaciones por retraso: tasa y tope", "TIME", True),
    ("EPC-06", "Garantías y penalizaciones de rendimiento", "TECHNICAL", True),
    (
        "EPC-07",
        "Limitación de responsabilidad, daño consecuencial y excepciones",
        "LEGAL", True,
    ),
    ("EPC-08", "Indemnidades", "LEGAL", True),
    ("EPC-09", "Resolución (causas, consecuencias, plazos)", "LEGAL", True),
    ("EPC-10", "Suspensión", "LEGAL", False),
    ("EPC-11", "Fuerza mayor", "LEGAL", True),
    ("EPC-12", "Variaciones / órdenes de cambio y su valoración", "SCOPE", True),
    ("EPC-13", "Alcance, exclusiones e interfaces", "SCOPE", True),
    ("EPC-14", "Pruebas y recepción (provisional/definitiva)", "QUALITY", True),
    ("EPC-15", "Garantía y periodo de defectos", "QUALITY", True),
    ("EPC-16", "Seguros y límites", "LEGAL", False),
    ("EPC-17", "Confidencialidad y propiedad intelectual", "LEGAL", False),
    ("EPC-18", "Ley aplicable y disputas", "LEGAL", False),
    ("EPC-19", "Impuestos, aranceles, permisos y cambio de ley", "BUDGET", False),
    ("EPC-20", "Remisiones a anexos y orden de prelación", "SCOPE", True),
]
BLANK_FIELDS = ("presente", "clausula", "pagina", "cita_ancla", "cifras_esperadas")


def test_yaml_taxonomy_matches_epc_plan_and_is_unassessed():
    path = HERE / "epc_control_taxonomy.yaml"
    assert path.is_file(), "B1 taxonomy has not been implemented"
    with path.open(encoding="utf-8") as f:
        data = yaml.safe_load(f)
    assert data["schema_version"] == 1
    assert data["campos_oraculo"] == FIELDS
    controls = data["controles"]
    assert len(controls) == 20
    for control, expected in zip(controls, EXPECTED, strict=True):
        assert list(control) == FIELDS
        assert expected == (
            control["id"], control["tipo"], control["dimension"], control["critico"]
        )
        assert all(control[field] is None for field in BLANK_FIELDS)
    assert sum(control["critico"] for control in controls) == 15
    assert {control["dimension"] for control in controls} == {
        "BUDGET", "TIME", "TECHNICAL", "LEGAL", "SCOPE", "QUALITY",
    }


def test_csv_oracle_has_exactly_20_unassessed_rows():
    path = HERE / "oracle_template.csv"
    assert path.is_file(), "B1 oracle has not been implemented"
    with path.open(encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        assert reader.fieldnames == FIELDS
        rows = list(reader)
    assert len(rows) == len(EXPECTED)
    for row, expected in zip(rows, EXPECTED, strict=True):
        id_, label, dimension, critical = expected
        assert (row["id"], row["tipo"], row["dimension"]) == (
            id_, label, dimension,
        )
        assert row["critico"] == ("si" if critical else "no")
        assert all(row[field] == "" for field in BLANK_FIELDS)
    assert len({row["id"] for row in rows}) == 20
