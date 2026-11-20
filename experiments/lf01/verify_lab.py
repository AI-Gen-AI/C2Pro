#!/usr/bin/env python3
"""LF-01 bounded no-inference flow smoke tests; reports evidence without credentials."""
import json
import os
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.parse import urlencode
from urllib.error import HTTPError

BASE = os.environ.get("LF01_URL", "http://127.0.0.1:17860") + "/api/v1"
DIR = Path(os.environ.get("LF01_EVIDENCE_DIR", "/home/lf01lab/lf01-evidence"))
ENV = Path(os.environ.get("LF01_ENV_PATH", "/home/lf01lab/lf01-config/.env"))

def req(url, *, data=None, headers=None):
    r = Request(BASE + url, data=data, headers=headers or {})
    try:
        with urlopen(r, timeout=60) as x:
            return x.status, json.load(x)
    except HTTPError as x:
        return x.code, {"error": x.read().decode(errors="replace")[:600]}

def main():
    settings = dict(line.split("=",1) for line in ENV.read_text().splitlines() if "=" in line)
    status, login = req("/login", data=urlencode({
        "username":settings["LANGFLOW_SUPERUSER"],
        "password":settings["LANGFLOW_SUPERUSER_PASSWORD"]}).encode(),
        headers={"Content-Type":"application/x-www-form-urlencoded"})
    assert status == 200, ("login", status)
    head = {"Content-Type":"application/json", "Authorization":"Bearer "+login["access_token"]}
    for tag,fname in [("real","real_offline_aggregate.json"),
                      ("synthetic","synthetic_partial_scenario.json")]:
        definition = json.loads((DIR/("lf01_"+tag+"_flow_definition.json")).read_text())
        types = [n["data"].get("type") for n in definition["data"]["nodes"]
                 if n["type"] == "genericNode"]
        assert set(types) == {"ChatInput", "ChatOutput"}, types
        id_ = (DIR/("lf01_"+tag+"_flow_id.txt")).read_text().strip()
        snapshot = json.loads((DIR/fname).read_text())
        marker = snapshot["data_class"]
        request = {
            "input_value":json.dumps(snapshot,ensure_ascii=False),
            "input_type":"chat","output_type":"chat",
            "session_id":"lf01-"+tag+"-readonly"
        }
        code,output=req("/run/"+id_+"?stream=false",
                        data=json.dumps(request).encode(), headers=head)
        output_text=json.dumps(output,ensure_ascii=False)
        verified = code==200 and marker in output_text
        print("RUN",tag,"http",code,"output_contains_evidence_class",marker in output_text,
              "passed",verified,"output_bytes",len(output_text))
        if not verified:
            print("DIAGNOSTIC",output_text[:480])
        result={"fixture":tag,"flow_id":id_,"http_code":code,
                "marker_returned":marker in output_text,
                "inference_calls":0,"C2Pro_writes":0,
                "test_passed":verified,
                "boundary":"local snapshot echo; stage note nodes NOT executed"}
        (DIR/("lf01_"+tag+"_run_result.json")).write_text(json.dumps(result,indent=2)+"\n")
    print("test files saved; no contract content exported")

if __name__=="__main__":
    main()
