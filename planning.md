# FitFindr — planning.md

> Complete this document before writing any implementation code.
> Your spec and agent diagram are what you'll use to direct AI tools (Claude, Copilot, etc.) to generate your implementation — the more specific they are, the more useful the generated code will be.
> Your planning.md will be reviewed as part of your submission.
> Update it before starting any stretch features.

---

## Tools

List every tool your agent will use. For each tool, fill in all four fields.
You must have at least 3 tools. The three required tools are listed — add any additional tools below them.

### Tool 1: search_listings

**What it does:**
Scans the mock listings dataset and returns items that match the user's 
description, size, and price ceiling. Matching is fuzzy — it checks if 
search terms appear in the title, description, or style_tags. All three 
filters are applied together; a listing must pass all of them to be returned.


**Input parameters:**
- description (str): free-text query e.g. "vintage graphic tee". Split into 
  keywords and match against title, description, style_tags fields.
- size (str): e.g. "M", "S", "XL". Match if the listing's size field 
  *contains* this string (handles "S/M", "XL (oversized)" cases).
- max_price (float): upper price ceiling. Match if listing price <= max_price.
**What it returns:**
A list of listing dicts, each containing: id, title, price, platform, 
condition, size, style_tags, colors, brand. Sorted by price ascending.
Maximum 5 results returned. Empty list [] if nothing matches.

**What happens if it fails or returns nothing:**
If results == []: do NOT proceed to suggest_outfit. Return a message to the 
user: "No listings found for [description] in size [size] under $[max_price]. 
Try broadening your description or raising your budget." Stop the loop.



---

### Tool 2: suggest_outfit

**What it does:**
Given a new item and the user's wardrobe, suggests one complete outfit by 
finding wardrobe pieces that complement the new item's style_tags and colors.
Sends both to Claude with a prompt asking for a specific, styled recommendation.

**Input parameters:**
- new_item (dict): a single listing dict returned from search_listings. 
  Must have: title, style_tags, colors, category, price, platform.
- wardrobe (dict): wardrobe object with an "items" key containing a list 
  of wardrobe item dicts. Each has: name, category, colors, style_tags, notes.

**What it returns:**
A string — a specific outfit recommendation that names actual wardrobe pieces 
by name, suggests how to style them together, and references the new item 
by title. Example: "Pair the Y2K butterfly tee with your baggy dark-wash 
jeans and chunky white sneakers. Layer your vintage denim jacket on top 
for a complete 90s-inspired look."

**What happens if it fails or returns nothing:**
If wardrobe["items"] == []: don't crash. Instead pass a note to Claude that 
the wardrobe is empty and ask for generic styling advice for the item alone.
Return: "Your wardrobe is empty, but this piece works well with wide-leg 
denim, chunky sneakers, or straight-leg trousers."
---

### Tool 3: create_fit_card

**What it does:**
Generates a short, Instagram-caption-style description of the complete outfit.
Sounds like something a real person would post — casual, specific, uses the 
item's price and platform. Must feel different for different inputs.


**Input parameters:**
- outfit (str): the outfit suggestion string returned by suggest_outfit.
- new_item (dict): the listing dict from search_listings. Used to pull 
  price, platform, title for the caption.

**What it returns:**
A string of 1–3 sentences max. Lowercase. Conversational tone. References 
the actual item, price, and platform. Ends with 1 emoji max.
Example: "thrifted this y2k butterfly tee off depop for $18 and my 
wide-legs were literally waiting for it 🦋"

**What happens if it fails or returns nothing:**
If outfit or new_item is missing/malformed: return a safe fallback caption:
"found something worth adding to the rotation 🛍️"

---

### Additional Tools (if any)

<!-- Copy the block above for any tools beyond the required three -->

---

## Planning Loop

**How does your agent decide which tool to call next?**
The loop is a sequential decision tree — it checks what was returned at each 
step before deciding whether to continue.
Receive user input (description, size, max_price, wardrobe)
Call search_listings(description, size, max_price)

→ If results == []:

Set error = "No listings found for '{description}' in size {size}

under ${max_price}. Try broadening your search."

Return error to user. STOP.

→ If results != []:

Set session["selected_item"] = results[0]

Continue to step 3.
Call suggest_outfit(session["selected_item"], wardrobe)

→ If wardrobe["items"] == []:

Pass empty wardrobe flag to Claude — get generic advice

→ Store result in session["outfit_suggestion"]

Continue to step 4.
Call create_fit_card(session["outfit_suggestion"], session["selected_item"])

→ Store result in session["fit_card"]

Continue to step 5.
Return to user:

Top listing match (title, price, platform, condition)
outfit_suggestion
fit_card


**Key principle:** The agent never calls suggest_outfit if search_listings 
returned empty. State flows forward — each tool receives output from the 
previous step via the session dict, not from the user re-entering it.

---

## State Management

A session dictionary is created at the start of each run_agent() call and 
passed through the planning loop. Each tool writes its output into the session 
before the next tool reads from it:

- After search_listings: session["selected_item"] = results[0]
- After suggest_outfit:  session["outfit_suggestion"] = <returned string>
- After create_fit_card: session["fit_card"] = <returned string>

Tools never receive raw user input after step 1 — they only receive what 
previous tools stored in the session. This is what makes it an agent rather 
than three independent function calls.

---

## Error Handling

| Tool | Failure Condition | Agent Response |
|---|---|---|
| search_listings | results == [] | "No listings found for '{description}' in size {size} under ${max_price}. Try a broader description or higher budget." Stop loop. |
| search_listings | File load error | "Couldn't load listings data. Please try again." Stop loop. |
| suggest_outfit | wardrobe is empty | Return generic styling advice for the item alone. Continue to fit card. |
| suggest_outfit | Claude API error | "Couldn't generate an outfit suggestion right now." Skip to fit card with partial data. |
| create_fit_card | Missing outfit/item | Return fallback caption: "found something worth adding to the rotation 🛍️" |
| create_fit_card | Claude API error | Return same fallback caption. Never crash. |


---

## Architecture

User Input (description, size, max_price, wardrobe)

│

▼

┌─────────────────────────────────────────────────┐

│                  Planning Loop                   │

│                                                  │

│  session = {}  ← state lives here               │

└──────────────────────┬──────────────────────────┘

│

▼

search_listings(description, size, max_price)

│

┌────────────┴─────────────┐

│ results == []            │ results != []

▼                         ▼

❌ Return error msg    session["selected_item"] = results[0]

STOP                         │

▼

suggest_outfit(selected_item, wardrobe)

│

┌─────────┴──────────┐

│ wardrobe empty      │ wardrobe has items

▼                     ▼

generic advice        specific outfit

└─────────┬──────────┘

│

session["outfit_suggestion"]

│

▼

create_fit_card(outfit_suggestion, selected_item)

│

session["fit_card"]

│

▼

✅ Return full session to user

(selected_item + outfit + fit_card)

---

## AI Tool Plan

**Milestone 2 (this spec):**
Written manually. No AI used yet — spec must come from my own understanding 
of the data and requirements.

**Milestone 3 — Implementing search_listings:**
Input to Claude: Tool 1 spec block above + load_listings() signature from 
data_loader.py. Ask it to implement the function using keyword splitting on 
description, substring match on size, and float comparison on price.
Verify: Run 3 test queries — one that returns results, one that returns empty, 
one with a price right at the boundary.

**Milestone 4 — Implementing suggest_outfit + create_fit_card:**
Input to Claude: Tool 2 and Tool 3 spec blocks + the wardrobe schema.
Ask it to implement both using the Anthropic API with specific prompts.
Verify: Test with example_wardrobe, then with empty_wardrobe. Check that 
empty wardrobe doesn't crash and returns something useful.

**Milestone 5 — Planning loop:**
Input to Claude: The planning loop pseudocode above + the architecture diagram.
Ask it to implement run_agent(description, size, max_price, wardrobe) that 
follows the exact conditional logic described.
Verify: Trace through manually with the example query. Confirm state flows 
correctly between tools.



---



## A Complete Interaction (Step by Step)

FitFindr takes a user's description, size, and budget → searches listings → 
if results found, takes the best match and the user's wardrobe → suggests a 
complete outfit → generates a shareable fit card caption. If search returns 
nothing, it stops and tells the user what to adjust. If the wardrobe is empty, 
suggest_outfit handles it gracefully instead of crashing.

**Example user query:** "I'm looking for a vintage graphic tee under $30, size M. 
I mostly wear baggy jeans and chunky sneakers."

**Step 1:**
The agent calls search_listings(description="vintage graphic tee", size="M", max_price=30.0).
The tool scans listings.json filtering by price <= 30.0, size contains "M", and 
description/style_tags match "vintage" and "graphic tee".
Returns: 2–3 matching listings sorted by relevance. Agent picks the top result:
{ "title": "Y2K Baby Tee — Butterfly Print", "price": 18.0, "platform": "depop", "condition": "excellent" }

**Step 2:**
The agent now has a confirmed item. It calls suggest_outfit(new_item=<band tee>, wardrobe=get_example_wardrobe()).
The tool looks at the new item's style_tags (["y2k", "vintage", "graphic tee"]) and 
finds compatible wardrobe pieces by matching tags and categories.
Returns: "Pair this with your baggy dark-wash jeans (w_001) and chunky white 
sneakers (w_007). Add your vintage black denim jacket if it's cold."

**Step 3:**
The agent calls create_fit_card(outfit=<suggestion above>, new_item=<band tee>).
The tool generates a short, caption-style description of the full look.
Returns: "thrifted this y2k butterfly tee for $18 and my wide-legs were waiting 
for it 🦋 full fit incoming"

**Final output to user:**
- The matched listing (title, price, platform, condition)
- The outfit suggestion with specific wardrobe pieces called out
- The fit card caption, styled and ready to copy

**Error path:**
If Step 1 returns no matches → agent tells user "Nothing matched — try a broader 
description or raise your budget" and stops. Does NOT call suggest_outfit with empty input.
If wardrobe is empty → suggest_outfit returns generic styling advice instead of crashing.