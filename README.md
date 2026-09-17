# Amsterdam listings multi-agent chatbot

The app reads `listings.csv` in the project root and answers questions through an orchestrator and specialist agents.

| Agent | Role |
| --- | --- |
| `search` | Find listings by neighbourhood, price, room type, nights, reviews, keywords |
| `insights` | Market stats, neighbourhood comparison, price charts |
| `recommend` | Top listings by reviews, price, value, or distance to center |
| `host` | Host profile, top hosts, license coverage |
| `help` | Usage guide |

## Features

- English NLU for filters (`under 250`, `between 150 and 250`, `near the center`, `canal`, `terrace`)
- Multi-agent routing in one turn
- Short follow-ups inherit previous filters (`same filters`, or brief refinements)
- `reset` / sidebar button clears memory
- Tables, maps, and bar charts in the Streamlit UI

## Run

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
streamlit run app.py
```

Open the URL Streamlit prints (usually http://localhost:8501).

## Example questions

- Find a canal apartment in De Pijp under 300 euros
- Compare neighbourhoods by price
- Recommend top 5 cheap private rooms near the center
- Average price in Westerpark
- What does host Edwin list?
- Find listings between 150 and 250 euros with terrace
- help

Not every row has a price (~6.5k of 10.5k). The agents account for that.
