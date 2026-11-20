#!/usr/bin/env python3
"""LF-01: install two explicitly labelled *snapshot display* flows into isolated Langflow.

No C2Pro runtime calls, no model calls, no external telemetry, no production credentials.
Executable part: Chat Input -> Chat Output. Other tiles are notes, NOT executed nodes.
"""
from __future__ import annotations
import copy
import json
import os
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen

BASE = os.environ.get("LF01_URL", "http://127.0.0.1:17860") + "/api/v1"
ENV_PATH = Path(os.environ.get("LF01_ENV_PATH", "/home/lf01lab/lf01-config/.env"))
EVIDENCE_DIR = Path(os.environ.get("LF01_EVIDENCE_DIR", "/home/lf01lab/lf01-evidence"))

def request(path, *, token=None, payload=None, form=None, method=None):
    if form is not None:
        body = urlencode(form).encode()
        headers = {"Content-Type": "application/x-www-form-urlencoded"}
    elif payload is not None:
        body = json.dumps(payload).encode()
        headers = {"Content-Type": "application/json"}
    else:
        body = None
        headers = {}
    if token:
        headers["Authorization"] = "Bearer " + token
    with urlopen(Request(BASE + path, data=body, headers=headers, method=method), timeout=60) as result:
        return json.load(result)

def make_graph(template, snapshot, tag):
    graph = template["data"]
    original_input = next(n for n in graph["nodes"] if n["data"].get("type") == "ChatInput")
    original_output = next(n for n in graph["nodes"] if n["data"].get("type") == "ChatOutput")
    note_example = next(n for n in graph["nodes"] if n["type"] == "noteNode")
    input_id, output_id = "LF01-ChatInput-" + tag, "LF01-ChatOutput-" + tag
    source_to_model = next(e for e in graph["edges"] if e["source"] == original_input["id"])
    model_to_output = next(e for e in graph["edges"] if e["target"] == original_output["id"])

    input_node, output_node = copy.deepcopy(original_input), copy.deepcopy(original_output)
    for node, new_id, x, name in [
        (input_node, input_id, 30, "Read-only snapshot input"),
        (output_node, output_id, 600, "Diagnostic snapshot output"),
    ]:
        node["id"] = new_id
        node["data"]["id"] = new_id
        node["position"] = {"x": x, "y": 60}
        node["positionAbsolute"] = {"x": x, "y": 60}
        node["data"]["display_name"] = name
        node["data"]["node"]["display_name"] = name

    summary = json.dumps(snapshot, ensure_ascii=False, indent=2)
    input_node["data"]["node"]["template"]["input_value"]["value"] = summary
    for node in (input_node, output_node):
        slot = node["data"]["node"]["template"].get("should_store_message")
        if slot is not None:
            slot["value"] = False

    edge = copy.deepcopy(model_to_output)
    edge["id"] = "lf01-edge-" + tag
    edge["source"] = input_id
    edge["target"] = output_id
    edge["sourceHandle"] = source_to_model["sourceHandle"].replace(original_input["id"], input_id)
    edge["targetHandle"] = model_to_output["targetHandle"].replace(original_output["id"], output_id)
    edge["data"]["sourceHandle"] = copy.deepcopy(source_to_model["data"]["sourceHandle"])
    edge["data"]["sourceHandle"]["id"] = input_id
    edge["data"]["targetHandle"] = copy.deepcopy(model_to_output["data"]["targetHandle"])
    edge["data"]["targetHandle"]["id"] = output_id

    n4 = snapshot["N4"]
    stages = [
        ("DOCUMENT", "Evidence source: " + snapshot["data_class"] + ". NOT a fresh model execution."),
        ("N1 / N2", "Historical windows: " + str(snapshot["N1_N2"]["processing_windows_historical"]) + ". " + ("50 literal N2 verified / 92 unverified" if tag == "REAL" else "Partial by design; 3 of 6 processed")),
        ("N3", "Status: " + snapshot["N3"]["status"] + ". No claims about real N3 processing."),
        ("N4", "Status: " + n4["status"] + ". Proposed candidates: " + str(n4["candidate_count"]) + ". Never accepted risks."),
        ("N12", "Status: " + snapshot["N12"]["status"] + ". No reviewer completion evidenced."),
        ("HITL", "Status: " + snapshot["HITL"]["status"] + ". Zero approvals, no write operations."),
        ("PROJECTGRAPH", "Status: " + snapshot["ProjectGraph"]["status"] + ". No promoted candidates."),
        ("N8 / SCORE", "Status: " + snapshot["N8_Coherence"]["status"] + ". No score recomputation."),
        ("USER UI", "Status: " + snapshot["UI"]["status"] + ". Do not assume results reached UI."),
        ("RELATED DOCUMENTS", "Budget, schedule, specs & annexes: " + snapshot["Budget_Schedule_Tech_Annexes"]["status"]),
    ]
    notes = []
    for index, (title, body) in enumerate(stages):
        node = copy.deepcopy(note_example)
        new_id = "LF01-note-" + tag + "-" + str(index)
        x, y = 30 + (index % 5) * 365, 500 + (index // 5) * 300
        node["id"] = new_id
        node["data"]["id"] = new_id
        node["data"]["node"]["description"] = "### " + title + "\n" + body + "\n\n**Evidence class:** " + snapshot["data_class"] + "\n**Execution:** NOT EXECUTED IN LANGFLOW"
        node["data"]["node"]["i18n_key"] = ""
        node["position"] = {"x": x, "y": y}
        node["positionAbsolute"] = {"x": x, "y": y}
        node["height"] = 240
        node["width"] = 330
        node["style"] = {"height": 240, "width": 330}
        notes.append(node)
    return {"nodes": [input_node, output_node, *notes],
            "edges": [edge], "viewport": {"x": 0, "y": 0, "zoom": 0.6}}

def main():
    settings = dict(line.split("=", 1) for line in ENV_PATH.read_text().splitlines()
                    if "=" in line)
    access = request("/login", form={"username": settings["LANGFLOW_SUPERUSER"],
                                     "password": settings["LANGFLOW_SUPERUSER_PASSWORD"]})["access_token"]
    examples = request("/flows/basic_examples/", token=access)
    basic = next(f for f in examples if f["name"] == "Basic Prompting")
    existing = request("/flows/?get_all=true&remove_example_flows=false&page=1&size=100", token=access)
    for tag, fname in [("REAL", "real_offline_aggregate.json"),
                       ("SYNTHETIC", "synthetic_partial_scenario.json")]:
        snapshot = json.loads((EVIDENCE_DIR / fname).read_text())
        assert snapshot["data_class"].startswith("REAL" if tag == "REAL" else "SYNTHETIC")
        name = "LF01 " + tag + " | " + ("N4 142 offline" if tag == "REAL" else "partial failure fixture")
        graph = make_graph(basic, snapshot, tag)
        flow = {"name": name,
                "description": "LF-01 DIAGNOSTIC SNAPSHOT. Executable echo only; stage notes are NOT run. " +
                               snapshot["data_class"] + ". No paid inference. No writes to C2Pro.",
                "data": graph, "webhook": False, "mcp_enabled": False,
                "tags": ["LF01", snapshot["data_class"]]}
        (EVIDENCE_DIR / ("lf01_" + tag.lower() + "_flow_definition.json")).write_text(
            json.dumps(flow, indent=2, ensure_ascii=False) + "\n")
        duplicate = next((x for x in existing if x.get("name") == name), None)
        if duplicate:
            updated = request("/flows/" + duplicate["id"], token=access,
                              payload={"data": graph}, method="PATCH")
            print(tag, "updated", duplicate["id"], "nodes", len(graph["nodes"]))
            (EVIDENCE_DIR / ("lf01_" + tag.lower() + "_flow_id.txt")).write_text(duplicate["id"] + "\n")
            continue
        created = request("/flows/", token=access, payload=flow)
        print(tag, "created", created["id"], "nodes", len(graph["nodes"]),
              "edges", len(graph["edges"]))
        (EVIDENCE_DIR / ("lf01_" + tag.lower() + "_flow_id.txt")).write_text(created["id"] + "\n")

if __name__ == "__main__":
    main()
