# Amsterdam listings multi-agent chatbot

The app reads `listings.csv` and answers through a **blackboard pipeline**:

`planner → specialists → fallback? → critique → synthesize`

| Agent | Stage | Role |
| --- | --- | --- |
| `planner` | planner | Builds the execution order |
| `search` | specialist | Filter listings |
| `recommend` | specialist | Ranked picks (price / value / score / center) |
| `insights` | specialist | Market stats + nearby areas |
| `compare` | specialist | Side-by-side neighbourhoods |
| `budget` | specialist | Trip cost for N nights / total budget |
| `deal` | specialist | Below-neighbourhood-median bargains |
| `guide` | specialist | Neighbourhood primer + local snapshot |
| `explain` | specialist | Why a listing ranks the way it does |
| `watchlist` | specialist | Save / show / clear pinned listing ids |
| `host` | specialist | Host profile and licenses |
| `similar` | specialist | Alternatives to the last shortlist |
| `clarify` | specialist | Asks for missing constraints |
| `fallback` | recovery | Progressively relaxes filters |
| `critique` | critique | Quality review of the turn |
| `synthesize` | synthesize | Final briefing |

## Extra capabilities

- Keyword search (`canal`, `terrace`, …)
- Composite listing score + deal discount vs area median
- Nearby neighbourhood suggestions
- Stay-cost estimates (`for 3 nights`, `total budget 900`)
- Cross-turn filter, shortlist, and watchlist memory
- Downloadable markdown briefing from the chat UI

## Run

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
streamlit run app.py
```

Open http://localhost:8501

## Example questions

- Find deals in De Pijp under 280 euros
- Guide to Westerpark
- Compare De Pijp and Westerpark
- Plan a 4-night trip with total budget 900
- save top
- show watchlist
- explain 28871
- similar
- help
