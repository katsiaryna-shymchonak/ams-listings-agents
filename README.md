# Amsterdam listings multi-agent chatbot

The app reads `listings.csv` and answers through a **blackboard pipeline**:

`planner → specialists → fallback? → critique → judge → synthesize`

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
| `critique` | critique | Heuristic quality review |
| `judge` | critique | Weighted rubric score for the turn |
| `synthesize` | synthesize | Final briefing |

## Judge rubric

Online (and offline against gold labels) the judge scores:

- **routing** — plan covers expected intents
- **filters** — extracted constraints match the query / gold
- **coverage** — specialists returned usable output (or fallback recovered)
- **usefulness** — tables / maps / charts / shortlist / briefing
- **efficiency** — plan width and fallback pressure

## Offline evaluation

```bash
python scripts/eval_suite.py
```

Uses `eval/golden_queries.json` and writes:
- `eval/latest_results.json` — machine-readable scores
- `eval/REPORT.md` — human-readable summary (`python scripts/render_eval_report.py`)

## Run the chat app

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
