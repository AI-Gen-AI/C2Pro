"""Ejecuta los casos de prueba (Golden Tasks) y el Golden Corpus.

Two execution modes are supported:

1. Legacy interactive Golden Tasks (``evals/test_cases.yaml``) — retained
   for backwards compatibility. Used when no flags or ``--auto`` is passed.

2. Golden Corpus mode (``--corpus``) — deterministic, CI-friendly run over
   the 15-bundle golden corpus under ``evals/golden_corpus/``. Combined
   with ``--ci`` it emits JSON + JUnit XML artifacts and never prompts
   for input.

See ``openspec/changes/build-golden-corpus`` for the spec.
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
import time
import xml.etree.ElementTree as ET
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError:  # pragma: no cover - import-time guard
    print("ERROR: PyYAML requerido. pip install pyyaml", file=sys.stderr)
    sys.exit(2)

EVALS_DIR = Path(__file__).resolve().parent
CORPUS_DIR = EVALS_DIR / "golden_corpus"
BUNDLES_DIR = CORPUS_DIR / "bundles"
MANIFEST_PATH = CORPUS_DIR / "manifest.yaml"

BLACKBOARD_PATH = Path("blackboard.json")
RESULTS_PATH = EVALS_DIR / "results.json"

EXIT_OK = 0
EXIT_ASSERTIONS_FAILED = 1
EXIT_LOAD_ERROR = 2

logger = logging.getLogger("evals.run_evals")

SEVERITY_SCORE_PENALTIES: dict[str, float] = {
    "critical": 25.0,
    "high": 15.0,
    "medium": 8.0,
    "low": 4.0,
}

ISSUE_TO_ALERT_SEVERITY: dict[str, str] = {
    "high": "high",
    "medium": "medium",
    "low": "low",
}


# ---------------------------------------------------------------------------
# Legacy Golden-Tasks mode (test_cases.yaml)
# ---------------------------------------------------------------------------


def cargar_test_cases() -> list[dict]:
    """Carga los casos de prueba desde test_cases.yaml."""
    yaml_path = EVALS_DIR / "test_cases.yaml"
    if not yaml_path.exists():
        print(f"ERROR: {yaml_path} no encontrado")
        return []
    with open(yaml_path, encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return data.get("test_cases", [])


def ejecutar_eval(test_case: dict, modo_simulacion: bool = True) -> dict:
    """Ejecuta un caso de prueba y devuelve resultado."""
    print(f"\n{'=' * 60}")
    print(f"EVAL: {test_case['id']} - {test_case['nombre']}")
    print(f"Agente: {test_case['agente_objetivo']}")
    print(f"Prompt: {test_case['prompt'][:100]}...")
    print(f"{'=' * 60}")

    inicio = time.time()

    if modo_simulacion:
        print("\n[INSTRUCCION PARA EL HUMANO]")
        print(f"1. Abre el CLI de {test_case['agente_objetivo']}")
        print(f"2. Ejecuta: {test_case['prompt']}")
        print("3. Verifica los criterios de exito:")
        for i, criterio in enumerate(test_case["criterios_exito"], 1):
            print(f"   {i}. {criterio}")
        print("\n4. Ingresa el resultado (pass/fail): ", end="")
        resultado_input = input().strip().lower()
        passed = resultado_input == "pass"
    else:
        passed = False

    duracion = time.time() - inicio

    return {
        "eval_id": test_case["id"],
        "nombre": test_case["nombre"],
        "agente_objetivo": test_case["agente_objetivo"],
        "passed": passed,
        "duracion_seg": round(duracion, 2),
        "criterios_verificados": len(test_case["criterios_exito"]),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


def ejecutar_todas_evals(modo_simulacion: bool = True) -> list[dict]:
    """Ejecuta todos los casos de prueba (modo legado)."""
    test_cases = cargar_test_cases()
    if not test_cases:
        print("No hay casos de prueba configurados.")
        return []

    resultados = [ejecutar_eval(tc, modo_simulacion) for tc in test_cases]

    RESULTS_PATH.parent.mkdir(parents=True, exist_ok=True)
    reporte = {
        "fecha": datetime.now(timezone.utc).isoformat(),
        "total": len(resultados),
        "pasados": sum(1 for r in resultados if r["passed"]),
        "fallidos": sum(1 for r in resultados if not r["passed"]),
        "resultados": resultados,
    }
    with open(RESULTS_PATH, "w", encoding="utf-8") as f:
        json.dump(reporte, f, indent=2, ensure_ascii=False)

    print(f"\n{'=' * 60}")
    print("RESUMEN DE EVALUACION")
    print(
        f"Total: {reporte['total']} | "
        f"Pasados: {reporte['pasados']} | Fallidos: {reporte['fallidos']}"
    )
    tasa = (reporte["pasados"] / reporte["total"] * 100) if reporte["total"] > 0 else 0
    print(f"Tasa de exito: {tasa:.1f}%")
    print(f"Resultados guardados en: {RESULTS_PATH}")
    print(f"{'=' * 60}")

    return resultados


# ---------------------------------------------------------------------------
# Golden Corpus mode
# ---------------------------------------------------------------------------


class CorpusError(Exception):
    """Raised for unrecoverable load/validation errors in corpus mode."""


def _import_schema() -> Any:
    """Import the corpus schema module lazily.

    Deferred so the legacy mode keeps working even if ``pydantic`` is
    missing from the environment.
    """
    # Ensure ``evals/`` is on the path so ``golden_corpus.schema`` imports
    # when this script is invoked as ``python evals/run_evals.py``.
    if str(EVALS_DIR) not in sys.path:
        sys.path.insert(0, str(EVALS_DIR))
    try:
        from golden_corpus import schema  # type: ignore
    except ImportError as exc:  # pragma: no cover - explicit dependency guard
        raise CorpusError(
            "pydantic is required for corpus mode; pip install pydantic"
        ) from exc
    return schema


def load_manifest(path: Path | None = None) -> Any:
    """Load and validate the corpus manifest."""
    path = path if path is not None else MANIFEST_PATH
    if not path.exists():
        raise CorpusError(f"Manifest not found: {path}")
    with path.open(encoding="utf-8") as f:
        raw = yaml.safe_load(f)
    schema = _import_schema()
    try:
        return schema.Manifest.model_validate(raw)
    except Exception as exc:  # pydantic.ValidationError or similar
        raise CorpusError(f"Manifest failed validation: {exc}") from exc


def load_bundle(bundle_id: str, bundles_dir: Path | None = None) -> Any:
    """Load and validate a single bundle."""
    bundles_dir = bundles_dir if bundles_dir is not None else BUNDLES_DIR
    # Security: reject path separators in bundle_id.
    if "/" in bundle_id or "\\" in bundle_id or ".." in bundle_id:
        raise CorpusError(f"Invalid bundle_id: {bundle_id}")
    path = bundles_dir / f"{bundle_id}.json"
    if not path.exists():
        raise CorpusError(f"Bundle file not found: {bundle_id}")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise CorpusError(f"Bundle {bundle_id} is not valid JSON: {exc}") from exc
    schema = _import_schema()
    try:
        return schema.Bundle.model_validate(data)
    except Exception as exc:
        raise CorpusError(f"Bundle {bundle_id} failed schema validation: {exc}") from exc


def _evaluate_bundle(bundle: Any, manifest_entry: Any) -> dict[str, Any]:
    """Run deterministic assertions for a single bundle.

    Checks:
      * bundle.bundle_id == manifest_entry.id
      * bundle.difficulty == manifest_entry.difficulty
      * set(bundle.dimensions) == set(manifest_entry.dimensions)
      * len(bundle.expected_issues) == manifest_entry.expected_issue_count
      * every expected_issue.dimension is declared in bundle.dimensions
      * score is null or within expected_score_range
      * generated alerts satisfy expected_alerts counts and severities

    Test Suite ID: TS-UD-COH-CORP-007.
    """
    failures: list[str] = []

    if bundle.bundle_id != manifest_entry.id:
        failures.append(
            f"id mismatch: bundle={bundle.bundle_id!r} manifest={manifest_entry.id!r}"
        )

    if bundle.difficulty != manifest_entry.difficulty:
        failures.append(
            "difficulty mismatch: "
            f"bundle={bundle.difficulty.value} manifest={manifest_entry.difficulty.value}"
        )

    bundle_dims = {d.value for d in bundle.dimensions}
    manifest_dims = {d.value for d in manifest_entry.dimensions}
    if bundle_dims != manifest_dims:
        failures.append(
            f"dimensions mismatch: bundle={sorted(bundle_dims)} "
            f"manifest={sorted(manifest_dims)}"
        )

    actual_count = len(bundle.expected_issues)
    if actual_count != manifest_entry.expected_issue_count:
        failures.append(
            f"expected_issue_count mismatch: bundle={actual_count} "
            f"manifest={manifest_entry.expected_issue_count}"
        )

    declared = {d.value for d in bundle.dimensions}
    for issue in bundle.expected_issues:
        if issue.dimension.value not in declared:
            failures.append(
                f"issue {issue.rule_id!r} dimension={issue.dimension.value} "
                "not in declared bundle dimensions"
            )

    score = _score_bundle(bundle)
    generated_alerts = _generate_bundle_alerts(bundle)
    score_failures = _assert_score_expectation(bundle, score)
    alert_failures, matched_alert_expectations, total_alert_expectations = (
        _assert_alert_expectations(bundle, generated_alerts)
    )
    failures.extend(score_failures)
    failures.extend(alert_failures)

    return {
        "bundle_id": bundle.bundle_id,
        "passed": not failures,
        "failures": failures,
        "issue_count": actual_count,
        "dimensions": sorted(bundle_dims),
        "difficulty": bundle.difficulty.value,
        "score": score,
        "score_check": bundle.score_check.value,
        "expected_score_range": bundle.expected_score_range.model_dump(),
        "generated_alerts": generated_alerts,
        "expected_alerts": [alert.model_dump() for alert in bundle.expected_alerts],
        "matched_alert_expectations": matched_alert_expectations,
        "total_alert_expectations": total_alert_expectations,
        "alert_recall_pct": _pct(matched_alert_expectations, total_alert_expectations),
    }


def _score_bundle(bundle: Any) -> float | None:
    """Compute the deterministic corpus proxy score.

    The standalone corpus runner intentionally avoids backend imports. The
    proxy uses the same monotonic semantics as the v1 score: more and more
    severe findings reduce the score, and contract-only incomplete bundles
    with null expectations return ``None``.

    Test Suite ID: TS-UD-COH-CORP-007.
    """
    if bundle.expected_score_range.min is None and bundle.expected_score_range.max is None:
        return None
    penalty = sum(
        SEVERITY_SCORE_PENALTIES[ISSUE_TO_ALERT_SEVERITY[issue.severity]]
        for issue in bundle.expected_issues
    )
    return max(0.0, round(100.0 - penalty, 2))


def _generate_bundle_alerts(bundle: Any) -> list[dict[str, Any]]:
    """Generate deterministic alert records from corpus expected issues.

    Test Suite ID: TS-UD-COH-CORP-007.
    """
    generated: list[dict[str, Any]] = []
    for issue in bundle.expected_issues:
        generated.append(
            {
                "rule_id": issue.rule_id,
                "severity": ISSUE_TO_ALERT_SEVERITY[issue.severity],
                "dimension": issue.dimension.value,
                "description": issue.description_contains,
            }
        )
    if bundle.expected_score_range.min is None and bundle.expected_score_range.max is None:
        generated.append(
            {
                "rule_id": "AUDIT_INCOMPLETE",
                "severity": "medium",
                "dimension": "Meta",
                "description": "Audit incomplete; score withheld until required documents are supplied.",
            }
        )
    return generated


def _assert_score_expectation(bundle: Any, score: float | None) -> list[str]:
    expected = bundle.expected_score_range
    if bundle.score_check.value == "skip":
        return []
    if expected.min is None and expected.max is None:
        return [] if score is None else [f"score expected null but got {score}"]
    if score is None:
        return ["score expected numeric but got null"]
    if not (expected.min <= score <= expected.max):
        return [
            f"score {score} outside expected range "
            f"[{expected.min}, {expected.max}] ({expected.reasoning})"
        ]
    return []


def _assert_alert_expectations(
    bundle: Any,
    generated_alerts: list[dict[str, Any]],
) -> tuple[list[str], int, int]:
    failures: list[str] = []
    matched = 0
    for expected in bundle.expected_alerts:
        count = sum(
            1
            for alert in generated_alerts
            if alert["rule_id"] == expected.rule_id
            and alert["severity"] == expected.severity
        )
        if count >= expected.min_count:
            matched += 1
        else:
            failures.append(
                f"alert {expected.rule_id} severity={expected.severity} "
                f"count {count} < min_count {expected.min_count}"
            )
    return failures, matched, len(bundle.expected_alerts)


def _pct(numerator: int, denominator: int) -> float:
    return round((numerator / denominator * 100.0), 2) if denominator else 100.0


def run_corpus(
    bundles_dir: Path | None = None,
    manifest_path: Path | None = None,
) -> dict[str, Any]:
    """Execute the golden corpus in deterministic mode.

    Returns a report dict suitable for JSON serialization.
    Raises ``CorpusError`` on unrecoverable load/validation errors so the
    CLI can translate them to exit code 2.
    """
    start = time.time()
    manifest_path = manifest_path if manifest_path is not None else MANIFEST_PATH
    bundles_dir = bundles_dir if bundles_dir is not None else BUNDLES_DIR
    manifest = load_manifest(manifest_path)

    bundle_results: list[dict[str, Any]] = []
    all_dimensions: set[str] = set()
    total_issues = 0
    matched_alert_expectations = 0
    total_alert_expectations = 0

    for entry in manifest.bundles:
        bundle = load_bundle(entry.id, bundles_dir)
        result = _evaluate_bundle(bundle, entry)
        bundle_results.append(result)
        all_dimensions.update(result["dimensions"])
        total_issues += result["issue_count"]
        matched_alert_expectations += result["matched_alert_expectations"]
        total_alert_expectations += result["total_alert_expectations"]

    passed = sum(1 for r in bundle_results if r["passed"])
    failed = len(bundle_results) - passed

    by_difficulty: Counter[str] = Counter(r["difficulty"] for r in bundle_results)

    report = {
        "mode": "corpus",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "total_bundles": len(bundle_results),
        "passed_bundles": passed,
        "failed_bundles": failed,
        "total_expected_issues": total_issues,
        "total_expected_alerts": total_alert_expectations,
        "matched_expected_alerts": matched_alert_expectations,
        "aggregate_recall_pct": _pct(matched_alert_expectations, total_alert_expectations),
        "dimensions_covered": sorted(all_dimensions),
        "by_difficulty": dict(by_difficulty),
        "duration_sec": round(time.time() - start, 3),
        "bundles": bundle_results,
    }
    return report


def write_junit_xml(report: dict[str, Any], path: Path) -> None:
    """Emit a JUnit-style XML summary for CI consumption."""
    total = report["total_bundles"]
    failures = report["failed_bundles"]
    suite = ET.Element(
        "testsuite",
        name="GoldenCorpus",
        tests=str(total),
        failures=str(failures),
        errors="0",
        time=str(report["duration_sec"]),
        timestamp=report["timestamp"],
    )
    for br in report["bundles"]:
        case = ET.SubElement(
            suite,
            "testcase",
            name=br["bundle_id"],
            classname="evals.golden_corpus",
        )
        if not br["passed"]:
            failure = ET.SubElement(
                case,
                "failure",
                message="; ".join(br["failures"])[:200] or "bundle assertions failed",
                type="AssertionError",
            )
            failure.text = json.dumps(br, indent=2)

    root = ET.Element("testsuites")
    root.append(suite)
    path.parent.mkdir(parents=True, exist_ok=True)
    ET.ElementTree(root).write(path, encoding="utf-8", xml_declaration=True)


def _print_corpus_report(report: dict[str, Any]) -> None:
    print("=" * 60)
    print("GOLDEN CORPUS — RESULTS")
    print("=" * 60)
    print(f"Total bundles       : {report['total_bundles']}")
    print(f"Passed              : {report['passed_bundles']}")
    print(f"Failed              : {report['failed_bundles']}")
    print(f"Total expected issues: {report['total_expected_issues']}")
    print(f"Total expected alerts: {report['total_expected_alerts']}")
    print(f"Alert recall         : {report['aggregate_recall_pct']:.2f}%")
    print(f"Dimensions covered  : {', '.join(report['dimensions_covered'])}")
    print(f"By difficulty       : {report['by_difficulty']}")
    print(f"Duration            : {report['duration_sec']}s")
    failed = [b for b in report["bundles"] if not b["passed"]]
    if failed:
        print("\nFAILED BUNDLES:")
        for br in failed:
            print(f"  - {br['bundle_id']}")
            for f in br["failures"]:
                print(f"      * {f}")
    print("=" * 60)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run C2Pro evals (legacy golden tasks or the 15-bundle golden corpus).",
    )
    parser.add_argument(
        "--corpus",
        action="store_true",
        help="Run the deterministic 15-bundle golden corpus.",
    )
    parser.add_argument(
        "--ci",
        action="store_true",
        help="CI mode: no prompts, emit JSON + JUnit XML artifacts.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=EVALS_DIR / "results",
        help="Directory where corpus artifacts are written (default: evals/results).",
    )
    parser.add_argument(
        "--auto",
        action="store_true",
        help="(Legacy) Skip human prompts in the old test_cases.yaml flow.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s - %(message)s")

    if args.corpus:
        try:
            report = run_corpus()
        except CorpusError as exc:
            print(f"CORPUS LOAD ERROR: {exc}", file=sys.stderr)
            return EXIT_LOAD_ERROR

        _print_corpus_report(report)

        if args.ci:
            output_dir: Path = args.output
            output_dir.mkdir(parents=True, exist_ok=True)
            json_path = output_dir / "corpus_results.json"
            xml_path = output_dir / "corpus_results.xml"
            json_path.write_text(
                json.dumps(report, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
            write_junit_xml(report, xml_path)
            print(f"Wrote {json_path}")
            print(f"Wrote {xml_path}")

        return EXIT_OK if report["failed_bundles"] == 0 else EXIT_ASSERTIONS_FAILED

    modo_simulacion = not args.auto
    print(
        f"Ejecutando evaluaciones en modo: "
        f"{'simulacion' if modo_simulacion else 'automatico'}"
    )
    ejecutar_todas_evals(modo_simulacion=modo_simulacion)
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
