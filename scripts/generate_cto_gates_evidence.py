#!/usr/bin/env python3
"""
CTO Gates Evidence Generator

Runs all gate verification tests and generates comprehensive evidence
package for CTO review.

Usage:
    python scripts/generate_cto_gates_evidence.py
    python scripts/generate_cto_gates_evidence.py --output=evidence/
    python scripts/generate_cto_gates_evidence.py --gates=1,2,3,4
"""

import argparse
import json
import subprocess
import sys
from datetime import datetime, UTC
from pathlib import Path
from typing import Any


class Colors:
    """ANSI color codes for terminal output."""
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKCYAN = '\033[96m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'


def print_header(message: str):
    """Print formatted header."""
    print(f"\n{Colors.HEADER}{Colors.BOLD}{'=' * 80}{Colors.ENDC}")
    print(f"{Colors.HEADER}{Colors.BOLD}{message.center(80)}{Colors.ENDC}")
    print(f"{Colors.HEADER}{Colors.BOLD}{'=' * 80}{Colors.ENDC}\n")


def print_success(message: str):
    """Print success message."""
    print(f"{Colors.OKGREEN}✅ {message}{Colors.ENDC}")


def print_failure(message: str):
    """Print failure message."""
    print(f"{Colors.FAIL}❌ {message}{Colors.ENDC}")


def print_info(message: str):
    """Print info message."""
    print(f"{Colors.OKCYAN}ℹ️  {message}{Colors.ENDC}")


def run_gate_tests(gate_number: int, output_dir: Path) -> dict[str, Any]:
    """
    Run tests for a specific gate and collect results.

    Args:
        gate_number: Gate number (1-4)
        output_dir: Directory to save evidence

    Returns:
        Dictionary with test results and evidence
    """
    gate_names = {
        1: "Row Level Security (RLS)",
        2: "Identity & Authentication",
        3: "MCP Security",
        4: "Traceability & Audit Logging"
    }

    gate_markers = {
        1: "gate1_rls",
        2: "gate2_identity",
        3: "gate3_mcp",
        4: "gate4_traceability"
    }

    print_header(f"Gate {gate_number}: {gate_names[gate_number]}")

    # Prepare pytest command
    marker = gate_markers[gate_number]
    json_report = output_dir / f"gate{gate_number}_pytest_report.json"
    log_file = output_dir / f"gate{gate_number}_execution.log"

    cmd = [
        "pytest",
        f"apps/api/tests/verification/test_gate{gate_number}_*.py",
        "-v",
        "-m", f"gate{gate_number}_{marker.split('_')[1]}",
        "--tb=short",
        f"--json-report",
        f"--json-report-file={json_report}",
        "--json-report-indent=2"
    ]

    print_info(f"Running tests: {' '.join(cmd)}")

    # Run tests
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=300  # 5 minute timeout
        )

        # Save execution log
        with open(log_file, 'w') as f:
            f.write(f"Command: {' '.join(cmd)}\n")
            f.write(f"Exit Code: {result.returncode}\n")
            f.write(f"\n{'=' * 80}\n")
            f.write("STDOUT:\n")
            f.write(result.stdout)
            f.write(f"\n{'=' * 80}\n")
            f.write("STDERR:\n")
            f.write(result.stderr)

        # Load JSON report if available
        test_results = {}
        if json_report.exists():
            with open(json_report) as f:
                test_results = json.load(f)

        # Parse results
        status = "PASSED" if result.returncode == 0 else "FAILED"

        if status == "PASSED":
            print_success(f"Gate {gate_number} verification PASSED")
        else:
            print_failure(f"Gate {gate_number} verification FAILED")

        # Extract test counts
        tests_passed = test_results.get("summary", {}).get("passed", 0)
        tests_failed = test_results.get("summary", {}).get("failed", 0)
        tests_total = test_results.get("summary", {}).get("total", 0)

        # Generate evidence
        evidence = {
            "gate": f"Gate {gate_number} - {gate_names[gate_number]}",
            "status": status,
            "timestamp": datetime.now(UTC).isoformat(),
            "evidence": {
                "tests": {
                    "total": tests_total,
                    "passed": tests_passed,
                    "failed": tests_failed,
                    "coverage_percentage": (tests_passed / tests_total * 100) if tests_total > 0 else 0
                }
            },
            "test_results": {},
            "logs": [],
            "recommendations": []
        }

        # Extract individual test results
        for test in test_results.get("tests", []):
            test_name = test.get("nodeid", "").split("::")[-1]
            test_outcome = test.get("outcome", "unknown").upper()
            evidence["test_results"][test_name] = test_outcome

        # Extract log messages from stdout
        for line in result.stdout.split('\n'):
            if line.strip():
                evidence["logs"].append(line.strip())

        # Add recommendations if failed
        if status == "FAILED":
            evidence["recommendations"].append(
                f"Review failed tests in {log_file}"
            )
            evidence["recommendations"].append(
                "Fix failing tests before proceeding to production"
            )

        # Save evidence JSON
        evidence_file = output_dir / f"gate{gate_number}_evidence.json"
        with open(evidence_file, 'w') as f:
            json.dump(evidence, f, indent=2)

        print_info(f"Evidence saved to: {evidence_file}")

        return evidence

    except subprocess.TimeoutExpired:
        print_failure(f"Gate {gate_number} tests timed out")
        return {
            "gate": f"Gate {gate_number} - {gate_names[gate_number]}",
            "status": "TIMEOUT",
            "timestamp": datetime.now(UTC).isoformat(),
            "error": "Test execution exceeded 5 minute timeout"
        }
    except Exception as e:
        print_failure(f"Gate {gate_number} execution error: {e}")
        return {
            "gate": f"Gate {gate_number} - {gate_names[gate_number]}",
            "status": "ERROR",
            "timestamp": datetime.now(UTC).isoformat(),
            "error": str(e)
        }


def generate_database_evidence(output_dir: Path) -> dict[str, Any]:
    """
    Generate database-level evidence for RLS policies.

    Returns:
        Dictionary with database security evidence
    """
    print_header("Database Security Analysis")

    try:
        # Check if database is available
        result = subprocess.run(
            [
                "docker", "exec", "c2pro-test-db",
                "psql", "-U", "test", "-d", "c2pro_test",
                "-c", "SELECT COUNT(*) FROM pg_tables WHERE schemaname = 'public';"
            ],
            capture_output=True,
            text=True,
            timeout=10
        )

        if result.returncode != 0:
            print_failure("Database not accessible")
            return {"status": "UNAVAILABLE", "error": "Database not running"}

        # Get RLS policy information
        rls_query = """
        SELECT
            schemaname,
            tablename,
            rowsecurity as rls_enabled
        FROM pg_tables
        WHERE schemaname = 'public'
        ORDER BY tablename;
        """

        result = subprocess.run(
            [
                "docker", "exec", "c2pro-test-db",
                "psql", "-U", "test", "-d", "c2pro_test",
                "-c", rls_query
            ],
            capture_output=True,
            text=True,
            timeout=10
        )

        rls_output_file = output_dir / "database_rls_policies.txt"
        with open(rls_output_file, 'w') as f:
            f.write(result.stdout)

        print_success("Database RLS policies exported")

        # Get policy details
        policy_query = """
        SELECT
            tablename,
            policyname,
            permissive,
            cmd
        FROM pg_policies
        WHERE schemaname = 'public'
        ORDER BY tablename, policyname;
        """

        result = subprocess.run(
            [
                "docker", "exec", "c2pro-test-db",
                "psql", "-U", "test", "-d", "c2pro_test",
                "-c", policy_query
            ],
            capture_output=True,
            text=True,
            timeout=10
        )

        policy_output_file = output_dir / "database_policy_details.txt"
        with open(policy_output_file, 'w') as f:
            f.write(result.stdout)

        print_success("Database policy details exported")

        return {
            "status": "ANALYZED",
            "rls_policies_file": str(rls_output_file),
            "policy_details_file": str(policy_output_file)
        }

    except Exception as e:
        print_failure(f"Database analysis error: {e}")
        return {"status": "ERROR", "error": str(e)}


def generate_summary_report(all_gates: list[dict], output_dir: Path) -> str:
    """
    Generate executive summary for CTO.

    Args:
        all_gates: List of gate evidence dictionaries
        output_dir: Directory to save report

    Returns:
        Path to generated report
    """
    print_header("Generating Executive Summary")

    # Calculate overall status
    all_passed = all(gate.get("status") == "PASSED" for gate in all_gates)
    overall_status = "✅ ALL GATES PASSED" if all_passed else "❌ SOME GATES FAILED"

    # Count totals
    total_tests = sum(gate.get("evidence", {}).get("tests", {}).get("total", 0) for gate in all_gates)
    total_passed = sum(gate.get("evidence", {}).get("tests", {}).get("passed", 0) for gate in all_gates)
    total_failed = sum(gate.get("evidence", {}).get("tests", {}).get("failed", 0) for gate in all_gates)

    # Generate markdown report
    report = f"""# CTO Security Gates Verification Report
**Date**: {datetime.now(UTC).strftime('%Y-%m-%d %H:%M:%S UTC')}
**Version**: v2.4.0
**Prepared by**: Engineering Team
**Generated by**: Automated CTO Gates Evidence Generator

---

## Overall Status: {overall_status}

### Summary
{'All four critical security gates have been verified with comprehensive testing and evidence generation. The system is ready for CTO approval and production deployment.' if all_passed else 'Some security gates require attention before production deployment. See details below.'}

### Test Summary
- **Total Tests**: {total_tests}
- **Passed**: {total_passed}
- **Failed**: {total_failed}
- **Success Rate**: {(total_passed / total_tests * 100):.1f}%

---

### Gate Results

| Gate | Status | Tests Passed | Coverage | Risk Level |
|------|--------|--------------|----------|------------|
"""

    for i, gate in enumerate(all_gates, 1):
        status_icon = "✅" if gate.get("status") == "PASSED" else "❌"
        tests = gate.get("evidence", {}).get("tests", {})
        passed = tests.get("passed", 0)
        total = tests.get("total", 0)
        coverage = tests.get("coverage_percentage", 0)
        risk = "LOW" if gate.get("status") == "PASSED" else "HIGH"

        report += f"| Gate {i}: {gate.get('gate', '').split(' - ')[1] if ' - ' in gate.get('gate', '') else ''} | {status_icon} {gate.get('status', 'UNKNOWN')} | {passed}/{total} | {coverage:.0f}% | {risk} |\n"

    report += "\n---\n\n### Detailed Results\n\n"

    # Add detailed results for each gate
    for i, gate in enumerate(all_gates, 1):
        report += f"#### Gate {i}: {gate.get('gate', '')}\n\n"
        report += f"**Status**: {gate.get('status', 'UNKNOWN')}\n\n"

        if gate.get("status") == "PASSED":
            report += "✅ All security requirements verified\n\n"
        else:
            report += "❌ Security issues detected - review required\n\n"

        # Add test results
        test_results = gate.get("test_results", {})
        if test_results:
            report += "**Test Results**:\n"
            for test_name, result in test_results.items():
                icon = "✅" if result == "PASSED" else "❌"
                report += f"- {icon} `{test_name}`: {result}\n"
            report += "\n"

        # Add recommendations
        recommendations = gate.get("recommendations", [])
        if recommendations:
            report += "**Recommendations**:\n"
            for rec in recommendations:
                report += f"- {rec}\n"
            report += "\n"

        report += "---\n\n"

    # Add evidence package reference
    report += f"""### Evidence Package

All detailed evidence has been saved to: `{output_dir}/`

**Files included**:
- `gate1_evidence.json` - Gate 1 (RLS) detailed evidence
- `gate2_evidence.json` - Gate 2 (Identity) detailed evidence
- `gate3_evidence.json` - Gate 3 (MCP Security) detailed evidence
- `gate4_evidence.json` - Gate 4 (Traceability) detailed evidence
- `database_rls_policies.txt` - Database RLS configuration
- `database_policy_details.txt` - RLS policy details
- Test execution logs for each gate

---

### Recommendations for Production Deployment

"""

    if all_passed:
        report += """1. ✅ **Proceed with deployment** - All security gates passed
2. Enable continuous security monitoring in production
3. Schedule regular security audits (quarterly)
4. Implement automated security regression testing in CI/CD
5. Set up alerting for security-related events

"""
    else:
        report += """1. ❌ **DO NOT DEPLOY** - Fix failing security tests first
2. Review failed test logs in evidence package
3. Address all security issues before retesting
4. Re-run verification after fixes
5. Obtain CTO approval before proceeding

"""

    report += """---

### Sign-off Checklist

- [ ] CTO Approval
- [ ] Security Team Review
- [ ] Compliance Team Review
- [ ] Production Deployment Authorized

---

**Report Generated**: {timestamp}
**Command**: `python scripts/generate_cto_gates_evidence.py`
""".format(timestamp=datetime.now(UTC).isoformat())

    # Save report
    report_file = output_dir / "CTO_GATES_VERIFICATION_REPORT.md"
    with open(report_file, 'w', encoding='utf-8') as f:
        f.write(report)

    print_success(f"Executive summary saved to: {report_file}")

    return str(report_file)


def main():
    """Main execution function."""
    parser = argparse.ArgumentParser(
        description="Generate CTO Gates verification evidence"
    )
    parser.add_argument(
        "--output",
        type=str,
        default="evidence",
        help="Output directory for evidence (default: evidence/)"
    )
    parser.add_argument(
        "--gates",
        type=str,
        default="1,2,3,4",
        help="Comma-separated list of gates to verify (default: 1,2,3,4)"
    )
    parser.add_argument(
        "--skip-db-analysis",
        action="store_true",
        help="Skip database security analysis"
    )

    args = parser.parse_args()

    # Create output directory
    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

    print_header("CTO Security Gates Verification")
    print_info(f"Output directory: {output_dir.absolute()}")
    print_info(f"Timestamp: {datetime.now(UTC).isoformat()}")

    # Parse gates to verify
    gates_to_verify = [int(g.strip()) for g in args.gates.split(',')]
    print_info(f"Verifying gates: {gates_to_verify}")

    # Run database analysis (if not skipped)
    if not args.skip_db_analysis:
        db_evidence = generate_database_evidence(output_dir)
    else:
        print_info("Skipping database analysis (--skip-db-analysis)")

    # Run gate tests
    all_gates = []
    for gate_num in gates_to_verify:
        if 1 <= gate_num <= 4:
            evidence = run_gate_tests(gate_num, output_dir)
            all_gates.append(evidence)
        else:
            print_failure(f"Invalid gate number: {gate_num} (must be 1-4)")

    # Generate summary report
    if all_gates:
        report_file = generate_summary_report(all_gates, output_dir)

        print_header("Verification Complete")
        print_info(f"Evidence package: {output_dir.absolute()}")
        print_info(f"Executive summary: {report_file}")

        # Final status
        all_passed = all(gate.get("status") == "PASSED" for gate in all_gates)
        if all_passed:
            print_success("\n🎉 ALL GATES PASSED - Ready for CTO approval\n")
            return 0
        else:
            print_failure("\n⚠️  SOME GATES FAILED - Review evidence before deployment\n")
            return 1
    else:
        print_failure("No gates were verified")
        return 1


if __name__ == "__main__":
    sys.exit(main())
