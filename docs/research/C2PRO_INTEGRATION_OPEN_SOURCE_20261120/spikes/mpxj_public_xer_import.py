"""F1: MPXJ import of public XER samples, independent raw table census.

Source data are publicly downloadable illustrative schedules; NOT real as-built
projects or SolarMax schedule. No writes to C2Pro, no model calls.
"""
import hashlib, json, sys, time
from pathlib import Path

BASE=Path(__file__).resolve().parents[1]
FILES=[
 ("Meridian_EPC_Level3_public_illustrative.xer","https://sketchdule.com/blog/img/xer-onepager/Meridian_EPC_Level3.xer"),
 ("stratum4d_sample.xer","https://github.com/xunaidlnt-sudo/stratum-4d/blob/main/samples/demo.xer"),
 ("project_toolkit_sample.xer","https://github.com/indrapandu/project-toolkit/blob/main/tools/p6-xer-viewer/sample.xer"),
 ("P6_schedule_AI_sample.xer","https://github.com/akhilkarthik/P6-Schedule-AI-Automation/blob/main/sample_schedule.xer")
]

def raw_census(p):
    counts={}
    table=None
    for line in p.read_text(encoding="utf-8-sig",errors="replace").splitlines():
        f=line.split("\t")
        if len(f)>1 and f[0]=="%T":
            table=f[1];counts.setdefault(table,0)
        elif f and f[0]=="%R" and table:
            counts[table]+=1
    return counts

import jpype,mpxj
jpype.startJVM()
from org.mpxj.reader import UniversalProjectReader
output={"study":"MPXJ public XER import","mpxj_version":"16.10.0",
"synthetic_or_illustrative_inputs":True,"files":[],"status":"PASS_LIMITED",
"limitations":["Examples are public project simulations, not accepted actual as-built programmes.",
"Raw XER TASK count can differ from MPXJ task count when summary/WBS records are materialized.",
"Parser import PASS does not prove calendar/baseline/float/constraint fidelity."]}
for filename,source in FILES:
    p=BASE/"fixtures"/filename
    if not p.exists():
        output["files"].append({"file":filename,"source":source,"status":"NOT_FOUND"});continue
    x={"file":filename,"source":source,"bytes":p.stat().st_size,"sha256":hashlib.sha256(p.read_bytes()).hexdigest(),"raw_table_rows":raw_census(p)}
    try:
        tic=time.perf_counter()
        project=UniversalProjectReader().read(str(p))
        ts=[t for t in project.getTasks() if t.getName()]
        x.update({"status":"PASS" if len(ts)>=2 else "PASS_LIMITED",
          "seconds":round(time.perf_counter()-tic,3),
          "mpxj_task_count":len(ts),
          "mpxj_predecessor_relationship_count":sum(len(list(t.getPredecessors())) for t in ts if t.getPredecessors() is not None),
          "mpxj_calendars":len(project.getCalendars()),
          "mpxj_resources":len(project.getResources()),
          "sample_ids":[{"id":str(t.getID()),"uid":str(t.getUniqueID())} for t in ts[:3]],
        })
    except Exception as e:
        x.update({"status":"FAIL","error":str(e)[:400],"exception_class":type(e).__name__})
    output["files"].append(x)

( BASE/"results"/"mpxj_public_xer_import.json").write_text(json.dumps(output,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
print(json.dumps({"totals":{"pass":sum(f["status"]=="PASS" for f in output["files"]),"fail":sum(f["status"]=="FAIL" for f in output["files"])},"files":[{"name":f["file"],"status":f["status"],"tasks":f.get("mpxj_task_count"),"raw_tasks":f.get("raw_table_rows",{}).get("TASK"),"relationships":f.get("mpxj_predecessor_relationship_count"),"error":f.get("error")} for f in output["files"]]},ensure_ascii=False))
