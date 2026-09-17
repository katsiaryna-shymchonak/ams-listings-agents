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
| `host` | specialist | Host profile and licenses |
| `similar` | specialist | Alternatives to the last shortlist |
| `clarify` | specialist | Asks for missing constraints |
| `fallback` | recovery | Progressively relaxes filters |
| `critique` | critique | Quality review of the turn |
| `synthesize` | synthesize | Final briefing |

## Extra capabilities

- Keyword search (`canal`, `terrace`, …)
- Composite listing score
- Nearby neighbourhood suggestions
- Stay-cost estimates (`for 3 nights`, `total budget 900`)
- Cross-turn filter + shortlist memory (`similar`, `same filters`, `reset`)

## Run

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
streamlit run app.py
```

Open http://localhost:8501

## Example questions

- Find a canal apartment in De Pijp under 300 euros for 3 nights
- Compare De Pijp and Westerpark
- Plan a 4-night trip with total budget 900
- Recommend top 5 scored private rooms near the center
- similar
- help
