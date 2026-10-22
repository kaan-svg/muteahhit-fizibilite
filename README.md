# Müteahhit Fizibilite Asistanı

A feasibility calculator for small residential projects in Turkey, focused on **Alanya / Antalya**.
Given a plot and its zoning parameters, it estimates the buildable area, the apartment mix,
construction cost, sales revenue and the contractor's profit, and compares scenarios side by side.

All numbers are computed in plain, tested Python. In week 2 a local LLM (Ollama) will be added
on top as an agent that calls these functions as tools and explains the results. **The LLM will
never do the math.**

>  **For information only.** This is a learning project, not investment, legal or engineering advice.
> Prices and costs below are rough public averages and assumptions. Always check the official
> zoning status (imar durumu) of a specific parcel and real local prices before making any decision.

**Status:** Week 1 done (calculation core). Week 2 (LLM agent, RAG, UI) in progress.

## Example

```bash
python -m src.senaryo
```

1000 m² plot, TAKS 0.30, emsal 1.50, 45% of units to the landowner (kat karşılığı), +25% extra costs:

```
Senaryo                Kat  Alan m2              Daireler  Gelir M  Gider M   Kar M   Marj
------------------------------------------------------------------------------------------
Kestel 50/50             5     1500          10x1+1 6x2+1     83.9     39.5     6.7    17%
Kestel max 4 kat         4     1200           8x1+1 5x2+1     68.5     31.6     6.1    19%
Oba 50/50                5     1500          10x1+1 6x2+1     78.5     39.5     3.7     9%
Mahmutlar pay %40        5     1500          10x1+1 6x2+1     69.0     39.5     1.9     5%
Mahmutlar hep 1+1        5     1500                21x1+1     74.3     39.5     1.4     4%
Mahmutlar 50/50          5     1500          10x1+1 6x2+1     69.0     39.5    -1.5    -4%
```

The same plot goes from a loss to a profit when the landowner's share drops from 45% to 40%.
That sensitivity is the main reason this tool exists.

## How it works

```
imar.py      zoning  -> footprint, total floor area, number of floors
daire.py     units   -> net usable area, apartment mix (1+1, 2+1, 3+1)
maliyet.py   cost    -> building class + official unit cost (TL/m²)
gelir.py     revenue -> sales revenue, profit (land purchase or kat karşılığı)
senaryo.py   chains all of the above and compares scenarios
```

```python
from src.senaryo import fizibilite

sonuc = fizibilite(
    arsa_alani=1000, taks=0.30, emsal=1.50, mahalle="Oba",
    oranlar={"1+1": 0.5, "2+1": 0.5},
    arsa_sahibi_payi=0.45, ek_gider_orani=0.25,
)
print(sonuc["kar"], sonuc["daireler"])
```

## Glossary

| Term | Meaning |
|------|---------|
| TAKS | Footprint / plot area |
| Emsal (KAKS) | Total floor area / plot area |
| Kat karşılığı | Landowner gives the plot and receives a share of the finished units instead of cash |
| Yapı sınıfı (III-A … IV-B) | Building class used for the official construction unit cost |

## Data and assumptions

| Input | Source | Reliability |
|-------|--------|-------------|
| Unit construction cost | Ministry of Environment 2026 table (Resmî Gazete, 3 Feb 2026, No. 33157) | Official, but not market cost: excludes VAT, includes 15% overhead + 10% contractor profit |
| m² sale prices (`data/pazar.csv`) | Emlakjet listing averages, Sep 2026 | Asking prices, include older buildings. Not new-project sale prices |
| Apartment sizes (60 / 95 / 130 m²) | Assumption | To be replaced with local data |
| Common area ratio 15% | Assumption | To be replaced with local data |
| Extra costs, landowner share | Passed as parameters | No default, the user must decide |

Not modelled yet: areas excluded from emsal (balconies, parking, shelters), basements, setbacks,
financing cost, time to sell.

## Setup

```bash
git clone https://github.com/kaan-svg/muteahhit-fizibilite.git
cd muteahhit-fizibilite
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pytest
```

## Roadmap

- [x] Zoning, apartment mix, cost, revenue/profit, scenario comparison (with tests)
- [ ] Local LLM with Ollama
- [ ] Calculation functions exposed as tools + agent loop
- [ ] RAG over the zoning regulation (Planlı Alanlar İmar Yönetmeliği)
- [ ] Gradio web interface
- [ ] Evaluation on 5 real plot scenarios
- [ ] Real Alanya price and cost data from local sources
