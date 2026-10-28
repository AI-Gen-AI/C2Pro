# Precision gate for the deterministic contract penalty reader (#1136)

The corpus is a JSONL file **kept outside the repository** (the repo is public; clauses come from real,
anonymised contracts). One JSON object per line:

| field | type | meaning |
|---|---|---|
| `id` | string | stable id, e.g. `es-lcsp-017` (never a contract name) |
| `text` | string | the clause exactly as extracted (may span several sentences/lines) |
| `lang` | `"es"` \| `"en"` \| `"mixed"` | language of the clause |
| `daily` | number \| null | expected **daily rate as a fraction** (0,1 % -> 0.001), `null` if the clause states none or it is not a plain per-day rate |
| `cap` | number \| null | expected **cumulative cap as a fraction**, `null` if none or not a total cap |
| `source` | string | anonymised provenance: `"<doc-type>/<jurisdiction>/<year-range>"`, e.g. `"PCAP/ES/2020-2024"`, `"FIDIC-red/INT/2017"` |
| `family` | string | wording family for the coverage matrix (see below) |
| `split` | `"holdout"` \| `"proposal"`, written by `prelabel.py` | `holdout` = labelled blind (a stable third of the ids by hash); `proposal` = the proposal of the reader was shown |
| `confirmed_proposal` | bool, only on `proposal` lines | the human accepted the proposal unchanged (a high rate means anchoring: trust the holdout) |
| `notes` | string, optional | why the label is what it is when it is not obvious (e.g. "tier: day 1-30 only") |

Labelling rules (so that "wrong number" is decidable):

* `daily` is the rate of the penalty **for delay** of the works/milestone, per calendar/working day, over the
  contract price (or the price base the clause states: still a rate, the measurement only checks the number).
  A rate for another breach (absence of staff, late reports) is `null` unless the clause is about delay.
* Tiered rates: label the first tier's number only when the clause says it applies to the whole period;
  otherwise `null` and `notes: "tiered"` (the reader must return `null`, not a tier).
* `cap` is the cumulative maximum of the delay penalties. A per-month, per-milestone, per-payment or
  liability cap is `null`.
* The label is the human reading; if two readers could disagree, put `null` (the gate asks for no wrong
  number, so an unlabelled doubt only costs recall).

## Workflow

1. Put the public pliegos (PDF/DOCX/TXT) in a folder **outside the repository**. First source: public pliegos from the
   Plataforma de Contratación del Sector Público.
2. Extract candidate clauses (penalty word + a figure), anonymised provenance only:

       python apps/api/scripts/clause_reader_gate/extract_clauses.py FILES... --out cands.jsonl --source "PCAP/ES/2020-2024" --prefix es-pcsp

3. Label them. `prelabel.py` proposes a daily rate and a cap for each clause; the human confirms (Enter) or corrects
   (`d=0.1% c=10%`, `-` for none). A third of the clauses (hash of the id) is the **holdout** and is shown **without**
   a proposal, so the measurement is not anchored on the reader being measured. The session is resumable.

       python apps/api/scripts/clause_reader_gate/prelabel.py cands.jsonl --out corpus.jsonl --reader-tree <checkout>

4. Measure the reader of a branch against `main` (two checkouts; the reader is imported from each, no network, no key):

       python apps/api/scripts/clause_reader_gate/measure_gate.py corpus.jsonl --main-tree <main> --branch-tree <branch> [--only holdout]

Output per reader: `exact_number`, `exact_null`, `wrong` (a number different from the label, including a number where
the label is `null`), `missed` (label has a number, reader returned `null`); precision = (exact_number + exact_null) /
(exact_number + exact_null + wrong), recall = exact_number / (exact_number + missed + wrong); per `lang` and per
`family`; and the wrong clauses by `id` (never the text, so logs can be shared). Entry criterion for #1136:
`wrong == 0` on the whole corpus **and on the holdout alone** for the branch reader, and no loss of `exact_number`
against `main`. Exit code 1 when the gate fails.

The corpus, the candidates and the downloaded files never enter the repository (`.gitignore` in this folder blocks
`*.jsonl`, `*.pdf`, `*.docx`, `*.txt`); the tests use synthetic clauses written inline.
