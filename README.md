# Müteahhit Fizibilite Asistanı

[![tests](https://github.com/kaan-svg/muteahhit-fizibilite/actions/workflows/tests.yml/badge.svg)](https://github.com/kaan-svg/muteahhit-fizibilite/actions/workflows/tests.yml)

A local AI assistant for small residential construction projects in **Alanya / Antalya, Turkey**.
Given a plot and its zoning parameters, it estimates buildable area, apartment mix, construction cost,
sales revenue and the contractor's profit, and answers questions about the zoning regulation.

Everything runs locally: a tested Python calculation core, an agent on top of a local LLM
(Ollama, `qwen3:8b`) that calls the calculations as tools, and RAG over the
*Planlı Alanlar İmar Yönetmeliği* (Turkish zoning regulation).

**The LLM never does the math.** Every number comes from the calculation code; the model only
decides which tool to call and explains the result.

>  **For information only.** A learning project, not investment, legal or engineering advice.
> Prices and costs are rough public averages and assumptions. Always check the official zoning
> status (imar durumu) of a parcel and real local prices before making any decision.

![Demo](docs/demo.gif)

## Features

- **Feasibility calculator:** zoning (TAKS, emsal, floor limit) → apartment mix → cost → revenue → profit,
  for both land purchase and *kat karşılığı* (landowner receives a share of the units).
  Areas excluded from emsal (balconies, stairs, parking; up to 30%) can be added to the cost.
- **Sensitivity analysis:** how profit changes with the landowner's share, sale price, emsal, etc.
- **Agent:** ask in plain Turkish (*"Mahmutlar'da 1000 m² arsam var... kârlı mı?"*); the model calls the tools,
  asks for missing data instead of guessing, and recovers from tool errors.
- **Regulation search (RAG):** *"Balkonlar emsale dahil mi?"* → finds the relevant articles and cites them.
- **Web UI (Gradio):** an instant calculator form and a chat tab that shows which tools were called.
- **Evaluation script:** measures the agent on 10 cases, 3 runs each.

## Example: why the details matter

1000 m² plot in Mahmutlar, TAKS 0.30, emsal 1.50, 40% of the units to the landowner, +25% extra costs:

| Areas excluded from emsal (balcony, stairs, parking) | Profit |
|---|---|
| 0% | +1.93 M TL |
| 10% | −2.01 M TL |
| 20% | −5.96 M TL |
| 30% | −9.91 M TL |

The same plot also turns from loss to profit when the landowner's share drops from 45% to 40%.
Small changes in assumptions flip the result, which is why every input is explicit and adjustable.
(Excluded areas are costed at the full unit price, which overstates their effect; see *Known limitations*.)

## Architecture

```mermaid
flowchart LR
    U[User] --> UI[Gradio UI<br/>arayuz.py]
    UI -->|form| CALC
    UI -->|chat| AG[Agent loop<br/>agent.py]
    AG <-->|tool calls| LLM[(qwen3:8b<br/>Ollama)]
    AG --> T[Tools<br/>araclar.py]
    T --> CALC[Calculation core<br/>imar → daire → maliyet → gelir → senaryo]
    T --> RAG[Regulation search<br/>yonetmelik.py]
    RAG --> IDX[(Article embeddings<br/>bge-m3, JSON)]
    CALC --> CSV[(pazar.csv<br/>m² prices)]
```

| Module | Role |
|---|---|
| `imar.py` | Footprint, total floor area, number of floors |
| `daire.py` | Net usable area, apartment mix (1+1, 2+1, 3+1) |
| `maliyet.py` | Building class + official unit construction cost |
| `gelir.py` | Sales revenue, profit (land purchase or kat karşılığı) |
| `senaryo.py` | Chains the above, compares scenarios |
| `araclar.py` | Tool definitions (JSON Schema) + argument cleaning |
| `agent.py` | Tool-calling loop with step limit and conversation memory |
| `yonetmelik.py` | Downloads the regulation, splits it into articles, embeds and searches |
| `llm.py` | Single-shot explanation of a result |
| `arayuz.py` | Gradio web interface |
| `degerlendirme.py` | Agent evaluation |

## Evaluation

`python -m src.degerlendirme` runs 10 cases × 3 runs against the local model. Expected numbers come
from the calculation code, so this measures the **model's behaviour**, not the formulas
(those are covered by unit tests).

- **arac:** the right tool was called with the right arguments (the tool returned the expected profit)
- **rakam:** the number in the answer matches the tool output (±0.06 M TL)
- **yon:** profit/loss direction stated correctly
- **madde / yasak:** the regulation answer cites the right article and doesn't contain a known wrong claim
- **sormali:** with missing data, the agent asks instead of inventing values

### Results (`qwen3:8b`, thinking off, 3 runs per case)

| Case | What it tests | Passed | Failed checks |
|---|---|---|---|
| mahmutlar | Basic feasibility, loss expected | 2/3 | yon ×1 ¹ |
| kestel_1+1 | Only 1+1 units | 3/3 | |
| oba_kat_siniri | Floor limit from the plan | 3/3 | |
| tosmur_kendi_arsam | No landowner share | 3/3 | |
| avsallar_buyuk | 2+1 / 3+1 mix, loss expected | 3/3 | |
| duyarlilik | Two scenarios, two numbers | 3/3 | |
| mahalleler | Price list tool | 3/3 | |
| eksik_bilgi | TAKS / emsal missing, must ask | **0/3** | sormali ×3 |
| balkon | Regulation, Madde 22 | **0/3** | yasak ×2, madde ×1 |
| emsal_disi_sinir | Regulation, 30% cap (Madde 5) | 2/3 | madde ×1 |
| **Total** | | **22/30 (73%)** | |

¹ not yet verified by hand; may be a false negative of the keyword check.

Average response time: 3–5 s per question on an RTX 5060 (8 GB).

### What the numbers say

- **Calculations: 17/18.** Tool choice and arguments were correct in all 18 runs. The model reliably turns
  a Turkish description of a plot into the right tool call and reports the result.
- **Missing data: 0/3.** Asked about a plot with no TAKS/emsal, the model invents values and calls the
  calculation tool instead of asking. In this case the tool failed for another reason (no price data for
  the neighbourhood), which hid the invented values in the first version of the checker.
  The prompt rule ("don't guess, ask") is not enough; this needs a code-level guard.
- **Regulation: 2/6.** Retrieval returns the right articles, but the answer is unstable. For the balcony
  question the model repeatedly turns "*not* included in emsal under these conditions" into
  "*may be* included", the opposite of the rule. For the 30% cap the content was right in every run,
  only the article number was missing.
- **Variance is high on regulation questions.** An earlier run gave balkon 2/3 and emsal_disi_sinir 0/3,
  the reverse of this run. Three runs per case is too few for a stable rate on these questions.

### Fixing the evaluator first

The first run reported 23/30, but reading every failed answer showed the checker itself was wrong
in two places:
- a correct answer that stated the **margin** (−16.2%) and "*kâr elde edilememiştir*" was marked as wrong
  (only the TL amount and a few loss phrases were recognised);
- an answer that **invented TAKS/emsal** was not caught, because the tool call returned an error.

Both were fixed (and covered by tests) before the run above. The second fix made the score *worse*,
which is the point: the evaluation should measure the model, not flatter it.
Raw answers and tool arguments of every run are saved in `eval/sonuc-*.json`.

## Design decisions

- **Calculations in code, not in the LLM.** An 8B model reads numbers correctly but misreads their
  relationships (in early tests it compared costs with gross revenue instead of the contractor's share).
  The prompt now states the profit formula explicitly, and all arithmetic stays in tested code.
- **Argument cleaning instead of prompt rules.** Small models send `45`, `"%45"` or `0.45` for the same
  ratio, `TAKS` instead of `taks`, and fill unknown fields with `0`. These are normalised in code;
  invalid calls return `{"hata": ...}` so the model can retry instead of crashing the loop.
- **No vector database.** The regulation is ~230 chunks. A JSON file with normalised vectors and a
  plain cosine search is enough; Chroma would only add a dependency.
- **Hybrid search.** 80% embedding similarity + 20% keyword overlap, so exact terms like *bodrum* or
  *otopark* are not missed. `bge-m3` is used because it is multilingual.
- **Thinking mode off.** `qwen3` reasons before every tool call by default, which made each step
  5–10× slower without improving tool selection.

## Data and assumptions

| Input | Source | Reliability |
|---|---|---|
| Unit construction cost | Ministry of Environment 2026 table (Resmî Gazete, 3 Feb 2026, No. 33157) | Official, not market cost: excludes VAT, includes 15% overhead + 10% contractor profit |
| m² sale prices (`data/pazar.csv`) | Emlakjet listing averages, Sep 2026 | Asking prices, include older buildings |
| Apartment sizes (60 / 95 / 130 m²), common area 15% | Assumption | To be replaced with local data |
| Regulation text | mevzuat.gov.tr (downloaded at setup, current version) | Official |

## Known limitations

- **Areas excluded from emsal are costed at the full unit price.** Balconies, stairs and parking
  (`emsal_disi_orani`, 0–30% per Madde 5) are added to the cost at the same TL/m² as interior space.
  In reality open balconies and parking are cheaper to build, so this overstates their cost; a separate
  unit cost for these areas would be more accurate. They are not added to the sellable area.
- **Regulation answers are the weakest part** (2/6 in the evaluation). Retrieval finds the right articles,
  but the 8B model sometimes mixes articles or inverts a rule. Treat regulation answers as pointers to the
  article, not as legal answers. Parcel-specific plan notes always override the general regulation.
- **The agent invents missing zoning values** (0/3) instead of asking.
- **PDF extraction artefacts.** `pypdf` splits some words (*"k onut"*); search still works but text is imperfect.
- Financing cost, time to sell, basements and setbacks are not modelled.

## Setup

Requirements: Python 3.11+, [Ollama](https://ollama.com), ~8 GB VRAM recommended (tested on RTX 5060 8 GB, WSL2).

```bash
git clone https://github.com/kaan-svg/muteahhit-fizibilite.git
cd muteahhit-fizibilite
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
pytest

ollama pull qwen3:8b
ollama pull bge-m3
python -m src.yonetmelik kur      # download regulation + build search index (once)

python -m src.arayuz              # web UI at http://localhost:7860
python -m src.agent               # or chat in the terminal
```

If Ollama runs on Windows and the code in WSL, enable mirrored networking
(`[wsl2] networkingMode=mirrored` in `%UserProfile%\.wslconfig`) so `localhost:11434` is reachable.

## Glossary

| Term | Meaning |
|---|---|
| TAKS | Footprint / plot area |
| Emsal (KAKS) | Total floor area / plot area |
| Kat karşılığı | Landowner provides the plot and receives a share of the finished units instead of cash |
| Yapı sınıfı (III-A … IV-B) | Building class used for the official unit construction cost |

## Roadmap

- [x] Calculation core with tests
- [x] Local LLM, tools, agent loop
- [x] RAG over the zoning regulation
- [x] Gradio UI
- [x] Evaluation script
- [ ] Code-level guard: refuse calculation when TAKS/emsal were not given by the user
- [x] Areas excluded from emsal added to cost (balconies, stairs, parking)
- [ ] Separate, lower unit cost for excluded areas
- [X ] More runs per case (10+) for stable regulation scores; try a larger model
- [ ] Real Alanya prices, unit sizes and construction costs from local sources
- [ ] Compare with a real completed project
