"""C2Pro OSS research — Docling digital PDF smoke, synthetic fixtures only."""
from __future__ import annotations
import hashlib, importlib.metadata, json, os, sys, time, traceback
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
FIX=ROOT/"fixtures"; OUT=ROOT/"results"; MODELS=ROOT/"models"
for p in (FIX,OUT,MODELS): p.mkdir(parents=True,exist_ok=True)
os.environ["HF_HOME"]=str(MODELS)
os.environ["TORCH_HOME"]=str(MODELS/"torch")
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.enums import TA_LEFT
from reportlab.platypus import SimpleDocTemplate, Paragraph, Table, TableStyle, Spacer, PageBreak
from reportlab.lib.pagesizes import A4

styles=getSampleStyleSheet()
def pdf(name, elements):
    path=FIX/name
    SimpleDocTemplate(str(path),pagesize=A4,topMargin=45,bottomMargin=45).build(elements)
    return path
def para(t): return Paragraph(t,styles["Normal"])
contract=pdf("synthetic_contract.pdf",[
    Paragraph("C2Pro synthetic EPC transformer agreement",styles["Title"]),
    para("TEST DATA ONLY. Not a contract. No real client or supplier information."),
    Spacer(1,10),
    para("Clause 9.6 - FAT acceptance milestone: the transformer must pass FAT no later than 30 May 2027."),
    para("Clause 13 - Liquidated damages: 0.5 percent per week of critical delivery delay."),
    para("Clause 4.3.1 - Equipment specifications: 132 kV transformer required."),
    para("Clause 2.5.5 - Approved cost ceiling: EUR 950000."),
    PageBreak(),
    Paragraph("General conditions and cross-references",styles["Heading2"]),
    para("Annex A defines the proposed delivery timeline. Annex B contains the cost and equipment list."),
    para("Changes to contractual milestones require written approval by the project manager.")
])
rows=[
 ["WBS","Item","Proposed FAT","Quote EUR"],
 ["WBS-130","132 kV transformer","20 June 2027","1030000"],
 ["WBS-135","Protection system","10 May 2027","120000"]
]
tbl=Table(rows,repeatRows=1,colWidths=[75,180,115,75])
tbl.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,0),colors.lightgrey),("GRID",(0,0),(-1,-1),0.6,colors.black),("FONTSIZE",(0,0),(-1,-1),8),("VALIGN",(0,0),(-1,-1),"TOP")]))
annex=pdf("synthetic_annex.pdf",[
    Paragraph("Annex A/B - Equipment and offer schedule",styles["Title"]),
    para("Supplementary proposal issued for synthetic demo only."),
    Spacer(1,15),tbl,Spacer(1,10),
    para("The proposed transformer FAT date is 20 June 2027, later than the contractual 30 May 2027."),
    para("The transformer quote is EUR 1030000, above the contractual EUR 950000 ceiling.")
])
manifest={"synthetic_only":True,"inputs":[{"file":p.name,"sha256":hashlib.sha256(p.read_bytes()).hexdigest(),"bytes":p.stat().st_size} for p in (contract,annex)]}
(OUT/"docling_corpus_manifest.json").write_text(json.dumps(manifest,indent=2),encoding="utf-8")
if "--generate-only" in sys.argv:
    print(json.dumps({"status":"GENERATED","files":manifest["inputs"]}))
    sys.exit(0)
report={"spike":"Docling","synthetic_only":True,"docling_version":importlib.metadata.version("docling"),"reportlab_version":importlib.metadata.version("reportlab"),"inputs":manifest["inputs"],"documents":{},"limitations":["Synthetic digital PDFs; not scanned contracts.","No comparison with current C2Pro parser or N4/N12.","Text presence and table detection do not prove legal interpretation."]}
try:
    from docling.document_converter import DocumentConverter, PdfFormatOption
    from docling.datamodel.base_models import InputFormat
    from docling.datamodel.pipeline_options import PdfPipelineOptions
    options=PdfPipelineOptions()
    options.do_ocr=False
    options.do_table_structure=True
    converter=DocumentConverter(format_options={InputFormat.PDF:PdfFormatOption(pipeline_options=options)})
    for path,terms in ((contract,["FAT","30 May 2027","0.5","132","950000"]), (annex,["FAT","20 June 2027","1030000","WBS-130"])):
        result={"status":"FAIL"}
        try:
            start=time.monotonic()
            conversion=converter.convert(str(path),raises_on_error=False)
            doc=conversion.document
            if doc is None: raise RuntimeError(f"No document: {conversion.status}")
            md=doc.export_to_markdown()
            (OUT/(path.stem+".md")).write_text(md,encoding="utf-8")
            normalized=" ".join(md.lower().split())
            present={t:(t.lower() in normalized) for t in terms}
            result={"status":"PASS" if all(present.values()) else "PASS_LIMITED",
                    "conversion_status":str(conversion.status),"seconds":round(time.monotonic()-start,3),
                    "pages":len(doc.pages),"tables":len(doc.tables),
                    "expected_terms":present,"markdown_chars":len(md),
                    "markdown_sha256":hashlib.sha256(md.encode()).hexdigest()}
        except Exception as ex:
            result={"status":"FAIL","error":f"{type(ex).__name__}: {ex}"[:1000]}
        report["documents"][path.name]=result
    statuses=[x["status"] for x in report["documents"].values()]
    report["status"]="PASS" if all(x=="PASS" for x in statuses) else "PASS_LIMITED" if all(x!="FAIL" for x in statuses) else "FAIL"
except Exception as exc:
    report["status"]="FAIL"
    report["fatal"]=f"{type(exc).__name__}: {exc}"[:1000]
    report["traceback"]=traceback.format_exc()[-1500:]
finally:
    (OUT/"docling_smoke_result.json").write_text(json.dumps(report,indent=2,ensure_ascii=False),encoding="utf-8")
    print(json.dumps({"status":report["status"],"version":report["docling_version"],"documents":report["documents"],"fatal":report.get("fatal")},ensure_ascii=False))
sys.exit(0 if report["status"] in ("PASS","PASS_LIMITED") else 2)
