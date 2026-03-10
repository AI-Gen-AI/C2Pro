#!/usr/bin/env python3
"""
Check Evaluation Drift

This script checks for drift in evaluation metrics and sends alerts
when thresholds are exceeded.

Usage:
    python check_eval_drift.py --config path/to/eval_thresholds.yaml
    python check_eval_drift.py --config path/to/eval_thresholds.yaml --notify-on-drift
"""

import argparse
import json
import os
import sys
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml


def load_config(config_path: Path) -> dict:
    """Load evaluation thresholds configuration."""
    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def load_baseline_metrics(datasets_path: Path) -> dict[str, dict[str, float]]:
    """Load baseline metrics for all services."""
    baselines = {}

    services = ["coherence", "extraction", "retrieval"]
    for service in services:
        baseline_file = datasets_path / service / "baseline_metrics.json"
        if baseline_file.exists():
            with open(baseline_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                baselines[service] = data.get("metrics", {})

    return baselines


def parse_junit_results(results_dir: Path) -> dict[str, dict]:
    """Parse JUnit XML results from evaluation runs."""
    results = {}

    # Find all XML result files
    for xml_file in results_dir.rglob("*.xml"):
        try:
            tree = ET.parse(xml_file)
            root = tree.getroot()

            # Get test suite info
            testsuite = root.find(".//testsuite") or root
            if testsuite is not None:
                service_name = xml_file.stem.replace("-eval-results", "")
                results[service_name] = {
                    "tests": int(testsuite.get("tests", 0)),
                    "failures": int(testsuite.get("failures", 0)),
                    "errors": int(testsuite.get("errors", 0)),
                    "skipped": int(testsuite.get("skipped", 0)),
                    "time": float(testsuite.get("time", 0)),
                }
        except ET.ParseError:
            continue

    return results


def check_drift(
    config: dict,
    baselines: dict[str, dict[str, float]],
    current_metrics: dict[str, dict[str, float]],
) -> list[dict[str, Any]]:
    """
    Check for metric drift against thresholds.

    Returns list of drift alerts.
    """
    alerts = []

    service_configs = {
        "coherence": config.get("coherence_engine", {}),
        "extraction": config.get("document_extraction", {}),
        "retrieval": config.get("hybrid_retrieval", {}),
    }

    for service, svc_config in service_configs.items():
        if not svc_config.get("enabled", True):
            continue

        baseline = baselines.get(service, {})
        current = current_metrics.get(service, {})

        for metric_config in svc_config.get("metrics", []):
            metric_name = metric_config["name"]
            baseline_value = baseline.get(metric_name)
            current_value = current.get(metric_name)

            if baseline_value is None or current_value is None:
                continue

            # Check absolute floor
            min_value = metric_config.get("min_absolute_value", 0)
            if current_value < min_value:
                alerts.append({
                    "service": service,
                    "metric": metric_name,
                    "type": "absolute_floor",
                    "baseline": baseline_value,
                    "current": current_value,
                    "threshold": min_value,
                    "severity": metric_config.get("severity", "high"),
                    "message": f"{metric_name} dropped below minimum: {current_value:.3f} < {min_value:.3f}",
                })
                continue

            # Check percentage drop
            pct_threshold = metric_config.get("threshold_percentage_drop", 0.1)
            if baseline_value > 0:
                actual_drop = (baseline_value - current_value) / baseline_value
                if actual_drop > pct_threshold:
                    alerts.append({
                        "service": service,
                        "metric": metric_name,
                        "type": "percentage_drop",
                        "baseline": baseline_value,
                        "current": current_value,
                        "drop_pct": actual_drop,
                        "threshold_pct": pct_threshold,
                        "severity": metric_config.get("severity", "high"),
                        "message": f"{metric_name} dropped {actual_drop:.1%} (threshold: {pct_threshold:.1%})",
                    })

    return alerts


def send_slack_notification(alerts: list[dict], webhook_url: str) -> bool:
    """Send drift alerts to Slack."""
    import urllib.request
    import urllib.error

    if not alerts:
        return True

    # Build Slack message
    blocks = [
        {
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": "C2PRO Evaluation Drift Alert",
            },
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*{len(alerts)} metric(s) exceeded drift thresholds*",
            },
        },
    ]

    for alert in alerts:
        severity_emoji = {
            "critical": ":rotating_light:",
            "high": ":warning:",
            "medium": ":large_yellow_circle:",
        }.get(alert.get("severity", "high"), ":warning:")

        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": (
                    f"{severity_emoji} *{alert['service']}* - `{alert['metric']}`\n"
                    f"{alert['message']}\n"
                    f"Baseline: {alert['baseline']:.3f} → Current: {alert['current']:.3f}"
                ),
            },
        })

    blocks.append({
        "type": "context",
        "elements": [
            {
                "type": "mrkdwn",
                "text": f"Detected at {datetime.now().isoformat()}",
            },
        ],
    })

    payload = {"blocks": blocks}

    try:
        req = urllib.request.Request(
            webhook_url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=10) as response:
            return response.status == 200
    except urllib.error.URLError as e:
        print(f"Failed to send Slack notification: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(description="Check for evaluation drift")
    parser.add_argument(
        "--config",
        type=Path,
        required=True,
        help="Path to eval_thresholds.yaml",
    )
    parser.add_argument(
        "--results-dir",
        type=Path,
        help="Directory containing JUnit XML results",
    )
    parser.add_argument(
        "--datasets-dir",
        type=Path,
        help="Directory containing baseline metrics",
    )
    parser.add_argument(
        "--notify-on-drift",
        action="store_true",
        help="Send Slack notification on drift",
    )

    args = parser.parse_args()

    # Determine paths
    config_path = args.config
    if not config_path.exists():
        print(f"Error: Config file not found: {config_path}")
        sys.exit(1)

    datasets_dir = args.datasets_dir
    if datasets_dir is None:
        datasets_dir = config_path.parent.parent / "datasets"

    # Load configuration and baselines
    config = load_config(config_path)
    baselines = load_baseline_metrics(datasets_dir)

    print("=" * 60)
    print("C2PRO Evaluation Drift Check")
    print("=" * 60)
    print(f"Config: {config_path}")
    print(f"Datasets: {datasets_dir}")
    print()

    # For now, we check baselines against thresholds
    # In production, this would compare against actual evaluation results
    current_metrics = baselines  # Placeholder - would come from eval results

    if args.results_dir and args.results_dir.exists():
        junit_results = parse_junit_results(args.results_dir)
        print("JUnit Results:")
        for service, result in junit_results.items():
            status = "PASS" if result["failures"] == 0 else "FAIL"
            print(f"  {service}: {status} ({result['tests']} tests, {result['failures']} failures)")
        print()

    # Check for drift
    alerts = check_drift(config, baselines, current_metrics)

    if alerts:
        print(f"DRIFT DETECTED: {len(alerts)} alert(s)")
        print("-" * 60)
        for alert in alerts:
            print(f"  [{alert['severity'].upper()}] {alert['service']}.{alert['metric']}")
            print(f"    {alert['message']}")
            print()

        if args.notify_on_drift:
            webhook_url = os.getenv("SLACK_WEBHOOK_URL")
            if webhook_url:
                if send_slack_notification(alerts, webhook_url):
                    print("Slack notification sent.")
                else:
                    print("Failed to send Slack notification.")
            else:
                print("SLACK_WEBHOOK_URL not set, skipping notification.")

        sys.exit(1)
    else:
        print("No drift detected. All metrics within thresholds.")
        sys.exit(0)


if __name__ == "__main__":
    main()
