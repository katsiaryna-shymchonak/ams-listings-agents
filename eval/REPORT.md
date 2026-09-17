# Agent evaluation report

Generated: 2026-09-17 18:23 UTC
Pass rate: **15/15 (100%)**
Threshold: 70%

| ID | Result | Score | Plan | Query |
| --- | --- | ---: | --- | --- |
| `search_canal_pijp` | PASS | 97% | `insights -> search` | Find a canal apartment in De Pijp under 300 euros for 3 nights |
| `deal_pijp` | PASS | 97% | `insights -> deal` | Find deals in De Pijp under 280 euros |
| `compare_areas` | PASS | 84% | `compare` | Compare De Pijp and Westerpark |
| `budget_trip` | PASS | 94% | `budget` | Plan a 4-night trip with total budget 900 |
| `recommend_scored` | PASS | 94% | `recommend` | Recommend top 5 scored private rooms near the center |
| `guide_westerpark` | PASS | 92% | `guide` | Guide to Westerpark |
| `insights_average` | PASS | 92% | `insights` | Average price in Westerpark |
| `host_edwin` | PASS | 94% | `host` | What does host Edwin list? |
| `explain_id` | PASS | 87% | `explain` | explain 28871 |
| `help` | PASS | 76% | `help` | help |
| `clarify_short` | PASS | 87% | `clarify` | xyz |
| `licensed_centrum` | PASS | 97% | `insights -> search` | Show licensed apartments in Centrum-West |
| `terrace_range` | PASS | 94% | `search` | Find listings between 150 and 250 euros with terrace |
| `watchlist_show` | PASS | 76% | `watchlist` | show watchlist |
| `city_compare_prices` | PASS | 84% | `insights` | Compare neighbourhoods by price |

## Dimension averages

| Dimension | Average |
| --- | ---: |
| routing | 100% |
| filters | 88% |
| coverage | 95% |
| usefulness | 58% |
| efficiency | 100% |

## Per-case notes

### search_canal_pijp (97%)
- [routing] Plan covered expected intents ['search'].
- [filters] All 5 expected filters matched.
- [coverage] Specialists produced substantive markdown.

### deal_pijp (97%)
- [routing] Plan covered expected intents ['deal'].
- [filters] All 2 expected filters matched.
- [coverage] Specialists produced substantive markdown.

### compare_areas (84%)
- [routing] Plan covered expected intents ['compare'].
- [filters] No filter expectations; query stayed open-ended.
- [coverage] Specialists produced substantive markdown.

### budget_trip (94%)
- [routing] Plan covered expected intents ['budget'].
- [filters] All 2 expected filters matched.
- [coverage] Specialists produced substantive markdown.

### recommend_scored (94%)
- [routing] Plan covered expected intents ['recommend'].
- [filters] All 4 expected filters matched.
- [coverage] Specialists produced substantive markdown.

### guide_westerpark (92%)
- [routing] Plan covered expected intents ['guide'].
- [filters] All 1 expected filters matched.
- [coverage] Specialists produced substantive markdown.

### insights_average (92%)
- [routing] Plan covered expected intents ['insights'].
- [filters] All 1 expected filters matched.
- [coverage] Specialists produced substantive markdown.

### host_edwin (94%)
- [routing] Plan covered expected intents ['host'].
- [filters] All 1 expected filters matched.
- [coverage] Specialists produced substantive markdown.

### explain_id (87%)
- [routing] Plan covered expected intents ['explain'].
- [filters] No filter expectations; query stayed open-ended.
- [coverage] Specialists produced substantive markdown.

### help (76%)
- [routing] Plan covered expected intents ['help'].
- [filters] No filter expectations; query stayed open-ended.
- [coverage] Specialists produced substantive markdown.

### clarify_short (87%)
- [routing] Plan covered expected intents ['clarify'].
- [filters] No filter expectations; query stayed open-ended.
- [coverage] Specialists produced substantive markdown.

### licensed_centrum (97%)
- [routing] Plan covered expected intents ['search'].
- [filters] All 3 expected filters matched.
- [coverage] Specialists produced substantive markdown.

### terrace_range (94%)
- [routing] Plan covered expected intents ['search'].
- [filters] All 3 expected filters matched.
- [coverage] Specialists produced substantive markdown.

### watchlist_show (76%)
- [routing] Plan covered expected intents ['watchlist'].
- [filters] No filter expectations; query stayed open-ended.
- [coverage] Specialists produced substantive markdown.

### city_compare_prices (84%)
- [routing] Plan covered expected intents ['insights'].
- [filters] No filter expectations; query stayed open-ended.
- [coverage] Specialists produced substantive markdown.
