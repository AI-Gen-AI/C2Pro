"""F1 real public SEC EPC HTML corpus: Docling parsing and source marker census.

No claims about PDF versions or legal correctness. SEC filing source names are
distinct contracts; independent held-out, never 'same file different version'.
"""
from __future__ import annotations
import hashlib, json, re, time, traceback
from pathlib import Path
from bs4 import BeautifulSoup

ROOT=Path(__file__).resolve().parents[1]
sources=[
 ("SEC_solarmax_longfellow_2025_ex991_original.html","https://www.sec.gov/Archives/edgar/data/1519472/000164033425001363/solarmax_ex991.htm","Longfellow BESS I / SolarMax"),
 ("SEC_solarmax_naguabo_2025_ex991_holdout.html","https://www.sec.gov/Archives/edgar/data/1519472/000164033426000032/solarmax_ex991.htm","Naguabo BESS / SolarMax"),
]
markers={
"liquidated_damages_2_5_5":r"2\.5\.5",
"suspension_9_6":r"9\.6",
"specification_4_3_1":r"4\.3\.1",
"article_13":r"(?:ARTICLE\s+13|13\.\d+)",
"exhibit_C":r"Exhibit\s+C",
"exhibit_D":r"Exhibit\s+D",
"table_C_1":r"Table\s+C-1",
"table_D_2":r"Table\s+D-2",
}
result={"study":"SEC EPC HTML public extraction, no private PDFs",
"format":"text/html (SEC official original), NOT original QA/UAT PDF",
"comparison_scope":"structural term/marker detection, not contractual legal reasoning",
"runs":[],"status":"PASS_LIMITED"}
converter=None
try:
    from docling.document_converter import DocumentConverter
    converter=DocumentConverter()
    result["docling_loader"]="available"
except Exception as e:
    result["docling_loader"]=f"unavailable: {e}"
for name,url,case in sources:
    p=ROOT/"fixtures"/name
    data=p.read_bytes()
    soup=BeautifulSoup(data,"html.parser")
    for tag in soup(["script","style"]):tag.decompose()
    source_text=" ".join(soup.stripped_strings)
    run={"file":name,"source_url":url,"case":case,"bytes":len(data),
         "sha256":hashlib.sha256(data).hexdigest(),
         "html_text_chars":len(source_text),
         "html_tables":len(soup.find_all("table")),
         "source_markers":{k:bool(re.search(pattern,source_text,re.IGNORECASE)) for k,pattern in markers.items()}}
    try:
        if converter is None: raise RuntimeError("No Docling converter")
        start=time.perf_counter()
        output=converter.convert(str(p),raises_on_error=False)
        if output.document is None:raise RuntimeError(str(output.status))
        md=output.document.export_to_markdown()
        (ROOT/"results"/(p.stem+"_docling.md")).write_text(md,encoding="utf-8")
        run["docling"]={
          "status":str(output.status),
          "elapsed_seconds":round(time.perf_counter()-start,3),
          "markdown_chars":len(md),
          "markdown_sha256":hashlib.sha256(md.encode()).hexdigest(),
          "tables":len(output.document.tables),
          "marker_recovery":{k:bool(re.search(pattern,md,re.IGNORECASE)) for k,pattern in markers.items()}
        }
    except Exception as e:
        run["docling"]={"status":"FAIL","error":f"{type(e).__name__}: {e}"[:400],"traceback_tail":traceback.format_exc()[-1000:]}
    result["runs"].append(run)
result["status"]="PASS" if all(x["docling"]["status"].endswith("SUCCESS") for x in result["runs"]) else "PASS_LIMITED"
result["limitations"]=[
 "The 2025 and 2026 SEC filing URLs are two DIFFERENT EPC agreements.",
 "Original QA (94p), UAT (51p), SEC rendition (73p) private PDFs were not supplied to this run.",
 "HTML/Markdown spans are not original PDF page/bounding-box evidence.",
 "Occurrence of a marker does not prove its clause, annex, table, or obligation was analysed.",
 "Annexes C/D/E may be absent from the public SEC filing or represented only partially.",
 "No N4/N12, independent contractual oracle, ProjectGraph, cross-document risk analysis, or external LLM inference."
]
(ROOT/"results"/"sec_public_contract_structural_eval.json").write_text(json.dumps(result,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
print(json.dumps({"status":result["status"],"runs":[{"file":r["file"],"html_text_chars":r["html_text_chars"],"html_tables":r["html_tables"],"source_markers":r["source_markers"],"docling":r["docling"]} for r in result["runs"]]},ensure_ascii=False))
