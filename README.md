# FitFindr 🛍️

An AI-powered thrift shopping agent that searches secondhand listings,
suggests outfits based on your wardrobe, and generates a shareable fit card —
all from a single natural language query.

---

## Setup

```bash
git clone <your-repo-url>

cd ai201-project2-fitfindr-starter

python3 -m venv .venv

source .venv/bin/activate

pip install -r requirements.txt

- Set your Groq API key in a `.env` file (get a free key at [console.groq.com](https://console.groq.com)):
GROQ_API_KEY=your_key_here

Run the app:
```bash
python app.py
```

Open `http://localhost:7860` in your browser.

---

## What's Included
ai201-project2-fitfindr-starter/

├── data/

│   ├── listings.json          # 40 mock secondhand listings

│   └── wardrobe_schema.json   # Wardrobe format + example wardrobe

├── utils/

│   └── data_loader.py         # Helper functions for loading the data

├── tools.py                   # The three agent tools

├── agent.py                   # Planning loop and session state

├── app.py                     # Gradio UI

├── tests/

│   └── test_tools.py          # pytest tests for all three tools

├── planning.md                # Design spec — filled out before any code

└── requirements.txt           # Python dependencies

---

## Tool Inventory

### `search_listings(description, size, max_price)`
- **Inputs:** `description` (str) — free-text item query; `size` (str | None) —
  clothing size, substring matched so "M" matches "S/M"; `max_price` (float | None) — price ceiling
- **Output:** List of up to 5 listing dicts sorted by keyword relevance score.
  Empty list `[]` if nothing matches — never raises an exception.
- **Purpose:** Scans the mock listings dataset using keyword overlap scoring
  across title, description, and style_tags. All filters are applied together —
  a listing must pass price, size, and keyword checks to be returned.

### `suggest_outfit(new_item, wardrobe)`
- **Inputs:** `new_item` (dict) — a listing dict from search_listings;
  `wardrobe` (dict) — wardrobe object with an `items` key
- **Output:** String with 1-2 complete outfit suggestions naming specific
  wardrobe pieces by name, or general styling advice if wardrobe is empty.
- **Purpose:** Calls the Groq LLM (llama-3.3-70b-versatile) with the new
  item's details and the user's wardrobe formatted as readable text.

### `create_fit_card(outfit, new_item)`
- **Inputs:** `outfit` (str) — suggestion string from suggest_outfit;
  `new_item` (dict) — listing dict for price/platform details
- **Output:** 1-3 sentence Instagram-style caption, lowercase, one emoji,
  references item name, price, and platform naturally.
- **Purpose:** Calls the Groq LLM at temperature 0.9 to generate varied,
  authentic-sounding captions. Higher temperature ensures different outputs
  for different inputs.

---

## How the Planning Loop Works

The agent runs a sequential decision tree — it checks what each tool returned
before deciding whether to continue. It does not call all tools unconditionally.
Parse the user's query using the LLM → extract description, size, max_price
Call search_listings() with parsed parameters

→ results == []: set error message, return early. STOP.

→ results != []: store results[0] as selected_item, continue.
Call suggest_outfit(selected_item, wardrobe)

→ wardrobe empty: get general styling advice instead of crashing

→ store result as outfit_suggestion, continue.
Call create_fit_card(outfit_suggestion, selected_item)

→ outfit empty: return fallback caption instead of crashing

→ store result as fit_card, continue.
Return completed session with all three outputs populated.

The key branch is at step 2: if `search_listings` returns an empty list,
the agent returns immediately with an error message. `suggest_outfit` is
never called with empty input. This is what makes it a planning loop rather
than three unconditional function calls.

---

## State Management

A `session` dict is initialized at the start of each `run_agent()` call
and passed through the entire loop. Each tool writes its output into the
session before the next tool reads from it:

```python
session["selected_item"]     # set after search_listings
session["outfit_suggestion"] # set after suggest_outfit
session["fit_card"]          # set after create_fit_card
session["error"]             # set if any step fails early
```

Tools never receive raw user input after step 1 — they only receive what
previous tools stored in the session. At the end of a run, the full session
is returned so the caller can inspect every intermediate result.

**Verified example:** In testing, `session["selected_item"]["price"]` was
`18.0` after `search_listings`. That exact value appeared in the fit card
as `"$18"` — the LLM read it from the session, not from anything the user typed.

---

## Error Handling

| Tool | Failure Condition | What the agent does |
|---|---|---|
| `search_listings` | No listings match filters | Returns: "No listings found for '{description}' in size {size} under ${max}. Try a broader description or raise your budget." Loop stops. |
| `search_listings` | File load error | Returns: "Search failed: {error}". Loop stops. |
| `suggest_outfit` | Wardrobe is empty | Calls LLM with empty-wardrobe prompt for general styling advice. Continues to fit card. |
| `suggest_outfit` | LLM API error | Sets error message, returns session early. |
| `create_fit_card` | Empty outfit string | Returns fallback: "found something worth adding to the rotation 🛍️". Never crashes. |
| `create_fit_card` | LLM API error | Returns same fallback caption. Non-fatal. |

**Tested — empty search:**
suggest_outfit(results[0], get_empty_wardrobe())

→ "The Y2K Baby Tee can be paired with high-waisted straight-leg jeans

in a light wash to create a casual, nostalgic look..."

(general advice, no crash)
**Tested — empty outfit string:**

create_fit_card("", results[0])

→ "found something worth adding to the rotation 🛍️"

(fallback returned, no crash)

---

## Spec Reflection

**What matched the spec:**
The planning loop behaved exactly as designed in `planning.md` — the branch
on empty search results worked correctly, state flowed between tools without
re-entry, and all three failure modes produced the exact messages specified
in the error handling table.

**What I'd change:**
Query parsing via LLM adds latency before the actual search. A regex fallback
for simple patterns like "under $30" or "size M" would speed up the happy path
while keeping LLM parsing for complex queries. The fit card prompt could also
enforce a stricter length limit — some outputs ran longer than 3 sentences
despite the instruction.

**Biggest design decision:**
Using a `session` dict instead of threading return values through function
arguments kept the planning loop clean and debuggable. Printing the full
session at the end of any run made it immediately clear what happened at
every step — especially useful when tracking down the state-passing bug
during testing.

**Where implementation diverged from spec:**
The spec described size matching as exact equality. During testing I discovered 
"M" wouldn't match "S/M" in the data, so I changed it to substring matching 
(`size.lower() in item["size"].lower()`). The spec was wrong about the data 
— implementation taught me that.

---

## AI Tool Usage

**Instance 1 — Implementing `search_listings`:**
Input to Claude: Tool 1 spec block from `planning.md` + `load_listings()`
signature from `data_loader.py`. The generated code used exact string matching
on size — I changed it to substring matching (`size.lower() in item["size"].lower()`)
after realizing "M" wouldn't match "S/M". Verified with `test_search_size_filter`.

**Instance 2 — Planning loop in agent.py:**
Input to Claude: the planning loop pseudocode and architecture diagram 
from planning.md. I reviewed the generated code against my spec before 
running it — specifically checking that the branch on empty search results 
returned early and didn't call suggest_outfit. The code matched the spec 
so I used it as written. Verified by running the no-results test case and 
confirming fit_card was None.

**Instance 3 — suggest_outfit and create_fit_card:**
Input to Claude: Tool 2 and Tool 3 spec blocks plus the wardrobe schema. 
I ran both tools in isolation before connecting them to the agent, which 
is how I confirmed the empty wardrobe case returned general advice rather 
than crashing. Used the generated code as written after verifying the 
test cases passed.

---

## The Mock Listings Dataset

`data/listings.json` contains 40 mock secondhand listings across categories
(tops, bottoms, outerwear, shoes, accessories) and styles (vintage, y2k, grunge,
cottagecore, streetwear, and more).

Each listing has: `id`, `title`, `description`, `category`, `style_tags`,
`size`, `condition`, `price`, `colors`, `brand`, and `platform`.

Load it with:
```python
from utils.data_loader import load_listings
listings = load_listings()
```

## The Wardrobe Schema

`data/wardrobe_schema.json` defines the format your agent uses to represent
a user's existing wardrobe. It includes:

- `schema`: field definitions for a wardrobe item
- `example_wardrobe`: a sample wardrobe with 10 items for testing
- `empty_wardrobe`: a starting template for a new user

Load an example wardrobe with:
```python
from utils.data_loader import get_example_wardrobe
wardrobe = get_example_wardrobe()
```