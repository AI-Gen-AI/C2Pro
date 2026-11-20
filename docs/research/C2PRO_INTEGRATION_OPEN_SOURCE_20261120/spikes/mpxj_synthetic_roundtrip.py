"""C2Pro OSS research — MPXJ synthetic round-trip smoke, no real project data."""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
import sys
import traceback

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "results"
FIX = ROOT / "fixtures"
OUT.mkdir(parents=True, exist_ok=True)
FIX.mkdir(parents=True, exist_ok=True)
report = {"spike": "MPXJ", "synthetic_only": True, "read_only_sources": True,
          "source": "MPXJ Python README / UniversalProjectWriter",
          "checks": [], "formats": {}, "limitations": [
              "Synthetic self-generated schedule: validates API round-trip only.",
              "Does NOT establish fidelity against native Primavera P6/Asta/MPP exports.",
              "Dates, calendars, baselines and float need independent oracle review."
          ]}
try:
    import jpype
    import mpxj
    import importlib.metadata
    report["mpxj_version"] = importlib.metadata.version("mpxj")
    report["jpype_version"] = importlib.metadata.version("JPype1")
    jpype.startJVM(convertStrings=True)
    from java.time import LocalDateTime
    from org.mpxj import ProjectFile, Duration, TimeUnit, Relation
    from org.mpxj.reader import UniversalProjectReader
    from org.mpxj.writer import UniversalProjectWriter, FileFormat

    project = ProjectFile()
    project.addDefaultBaseCalendar()
    props = project.getProjectProperties()
    props.setProjectTitle("C2PRO-SYNTHETIC-TRANSFORMER-2026")
    props.setStartDate(LocalDateTime.of(2026, 11, 23, 8, 0))

    summary = project.addTask()
    summary.setName("WBS-100 Subestacion / paquete transformador")
    spec = summary.addTask()
    spec.setName("WBS-110 Aprobar especificaciones de transformador")
    spec.setStart(LocalDateTime.of(2026, 11, 23, 8, 0))
    spec.setDuration(Duration.getInstance(5, TimeUnit.DAYS))
    procurement = summary.addTask()
    procurement.setName("WBS-120 Adjudicacion y fabricacion")
    procurement.setStart(LocalDateTime.of(2026, 11, 30, 8, 0))
    procurement.setDuration(Duration.getInstance(10, TimeUnit.DAYS))
    procurement.addPredecessor(Relation.Builder().predecessorTask(spec).successorTask(procurement))
    deadline = summary.addTask()
    deadline.setName("WBS-130 Hito contractual entrega FAT")
    deadline.setStart(LocalDateTime.of(2026, 12, 14, 8, 0))
    deadline.setDuration(Duration.getInstance(0, TimeUnit.DAYS))
    deadline.addPredecessor(Relation.Builder().predecessorTask(procurement).successorTask(deadline))
    expected_names = [str(t.getName()) for t in project.getTasks() if t.getName()]
    report["input_task_names"] = expected_names
    report["input_task_count"] = len(expected_names)
    report["input_predecessor_count"] = sum(len(list(t.getPredecessors())) for t in project.getTasks() if t.getPredecessors() is not None)

    for key, kind, extension in [
        ("mspdi", FileFormat.MSPDI, ".xml"),
        ("xer", FileFormat.XER, ".xer"),
    ]:
        target = FIX / ("synthetic_schedule" + extension)
        record = {"output": target.name}
        try:
            UniversalProjectWriter(kind).write(project, str(target))
            reloaded = UniversalProjectReader().read(str(target))
            if reloaded is None:
                raise RuntimeError("Reader returned no ProjectFile")
            tasks = [t for t in reloaded.getTasks() if t.getName()]
            names = [str(t.getName()) for t in tasks]
            missing = [n for n in expected_names if n not in names]
            links = sum(len(list(t.getPredecessors())) for t in tasks if t.getPredecessors() is not None)
            record.update({
                "status": "PASS" if not missing and links >= 2 else "PASS_LIMITED",
                "input_names": len(expected_names), "reloaded_names": len(names),
                "unmatched_names": missing, "reloaded_predecessor_count": links,
                "sha256": hashlib.sha256(target.read_bytes()).hexdigest(),
                "bytes": target.stat().st_size,
                "tasks": [{"name": str(t.getName()), "id": str(t.getID()),
                          "uid": str(t.getUniqueID()), "start": str(t.getStart()),
                          "finish": str(t.getFinish()),
                          "predecessors": len(list(t.getPredecessors())) if t.getPredecessors() is not None else 0}
                          for t in tasks]
            })
        except Exception as exc:
            record.update({"status": "FAIL", "error": f"{type(exc).__name__}: {exc}"[:1000]})
        report["formats"][key] = record
    report["status"] = "PASS" if all(x.get("status") == "PASS" for x in report["formats"].values()) else "PASS_LIMITED" if any(x.get("status") in ("PASS", "PASS_LIMITED") for x in report["formats"].values()) else "FAIL"
except Exception as exc:
    report["status"] = "FAIL"
    report["fatal"] = f"{type(exc).__name__}: {exc}"[:1200]
    report["traceback"] = traceback.format_exc()[-3000:]
finally:
    (OUT / "mpxj_smoke_result.json").write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({"status": report["status"], "mpxj_version": report.get("mpxj_version"),
                      "formats": {k: {p: q for p, q in v.items() if p in ("status","error","reloaded_names","reloaded_predecessor_count","bytes")}
                                  for k, v in report.get("formats", {}).items()},
                      "fatal": report.get("fatal")}, ensure_ascii=False))
sys.exit(0 if report["status"] in ("PASS", "PASS_LIMITED") else 2)
