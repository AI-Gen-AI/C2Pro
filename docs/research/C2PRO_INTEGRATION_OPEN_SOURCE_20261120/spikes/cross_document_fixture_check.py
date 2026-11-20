"""F0 research: detect two seeded cross-document candidate discrepancies.

This is deliberately a simple deterministic fixture oracle, NOT N4/N12, an
EPC risk engine, legal analysis, or a production-ready cross-document parser.
"""
from __future__ import annotations
from datetime import datetime
from pathlib import Path
import hashlib, json, re, sys
ROOT=Path(__file__).resolve().parents[1]
res=ROOT/"results"
manifest=json.loads((res/"docling_corpus_manifest.json").read_text(encoding="utf-8"))
documents={}
for name in ("contract","annex"):
    documents[name]=(res/f"synthetic_{name}.md").read_text(encoding="utf-8")
hashes={x["file"]:x["sha256"] for x in manifest["inputs"]}
def span_match(document,pattern,label):
    m=re.search(pattern,documents[document],flags=re.IGNORECASE|re.MULTILINE)
    if m is None:raise AssertionError(f"Missing {label} in Docling Markdown: {document}")
    quote=m.group(0)
    return m.group(1),{"source":f"synthetic_{document}.pdf","source_sha256":hashes[f"synthetic_{document}.pdf"],"text_start":m.start(),"text_end":m.end(),"quote":quote,"reference_type":"markdown_char_span_not_pdf_coordinates"}
deadline,deadline_ref=span_match("contract",r"FAT no later than (\d{1,2} [A-Za-z]+ \d{4})","contract FAT")
proposal,proposal_ref=span_match("annex",r"FAT date is (\d{1,2} [A-Za-z]+ \d{4})","proposed FAT")
ceiling,ceiling_ref=span_match("contract",r"cost ceiling: EUR\s*(\d+)","contract budget")
offer,offer_ref=span_match("annex",r"transformer quote is EUR\s*(\d+)","annex offer")
a=datetime.strptime(deadline,"%d %B %Y").date()
b=datetime.strptime(proposal,"%d %B %Y").date()
late=(b-a).days
overrun=int(offer)-int(ceiling)
candidates=[]
if late>0:
    candidates.append({"type":"FAT_DATE_CONTRADICTION","status":"CANDIDATE_UNVALIDATED","delay_days":late,"contractual_date":a.isoformat(),"proposed_date":b.isoformat(),"evidence":[deadline_ref,proposal_ref]})
if overrun>0:
    candidates.append({"type":"BUDGET_OFFER_CONTRADICTION","status":"CANDIDATE_UNVALIDATED","overrun_eur":overrun,"approved_ceiling_eur":int(ceiling),"offered_price_eur":int(offer),"evidence":[ceiling_ref,offer_ref]})
result={"status":"PASS" if len(candidates)==2 and late==21 and overrun==80000 else "FAIL","synthetic_only":True,"input_type":"Docling markdown from two generated PDFs","method":"fixture-specific regex, NOT a general contract analysis algorithm","candidates":candidates,"trusted_promotions":0,"alerts_created":0,"score_modified":False,"limitations":["Markdown offsets are not original PDF coordinates.","Pattern-based extraction is valid only for this synthetic corpus.","No MPXJ schedule linkage or C2Pro ProjectGraph API has been exercised.","No N4/N12 analysis, human review, or accuracy benchmark has been executed."]}
(res/"cross_document_candidate_result.json").write_text(json.dumps(result,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
print(json.dumps({"status":result["status"],"candidate_count":len(candidates),"types":[x["type"] for x in candidates],"delta_days":late,"delta_eur":overrun,"trusted_promotions":0},ensure_ascii=False))
sys.exit(0 if result["status"]=="PASS" else 2)
