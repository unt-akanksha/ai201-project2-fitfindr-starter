"""
tools.py
"""

import os
from dotenv import load_dotenv
from groq import Groq
from utils.data_loader import load_listings

load_dotenv()


def _get_groq_client():
    """Initialize and return a Groq client using GROQ_API_KEY from .env."""
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        raise ValueError(
            "GROQ_API_KEY not set. Add it to a .env file in the project root."
        )
    return Groq(api_key=api_key)


# ── Tool 1: search_listings ───────────────────────────────────────────────────

def search_listings(
    description: str,
    size: str | None = None,
    max_price: float | None = None,
) -> list[dict]:
    """Search listings by description keywords, size, and price ceiling."""

    # Step 1: Load all listings from the JSON file
    # We use the provided helper — no need to open files ourselves
    listings = load_listings()

    # Step 2: Apply hard filters first (price and size)
    # These are binary: either the listing qualifies or it doesn't
    filtered = []
    for item in listings:

        # Price filter: skip if listing costs more than max_price
        # We check max_price is not None first — None means "no price limit"
        if max_price is not None and item["price"] > max_price:
            continue

        # Size filter: check if the query size appears INSIDE the listing size
        # e.g. "M" is in "S/M", "XL" is in "XL (oversized)"
        # .lower() on both sides makes it case-insensitive
        if size is not None:
            if size.lower() not in item["size"].lower():
                continue

        filtered.append(item)

    # Step 3: Score remaining listings by keyword overlap
    # Split description into individual words to search for each one
    keywords = description.lower().split()

    scored = []
    for item in filtered:
        # Build one big searchable string from all text fields in this listing
        # style_tags is a list, so we join it into a string first
        searchable = " ".join([
            item["title"].lower(),
            item["description"].lower(),
            " ".join(item["style_tags"]).lower(),
            item["category"].lower(),
        ])

        # Count how many keywords appear in the searchable text
        # This is the "relevance score" — more keyword matches = better result
        score = sum(1 for kw in keywords if kw in searchable)
        
        # Step 4: Only keep listings that matched at least one keyword
        if score > 0:
            scored.append((score, item))

    # Step 5: Sort by score highest first, return just the listing dicts
    # The '-' before score reverses the sort (highest score first)
    scored.sort(key=lambda x: -x[0])

    # Return max 5 results — no need to overwhelm the user
    return [item for _, item in scored[:5]]


# ── Tool 2: suggest_outfit ────────────────────────────────────────────────────

def suggest_outfit(new_item: dict, wardrobe: dict) -> str:
    """Suggest outfit combinations using the new item and the user's wardrobe."""

    client = _get_groq_client()

    # Step 1: Check if wardrobe is empty
    # wardrobe is a dict with an "items" key — we check if that list is empty
    wardrobe_items = wardrobe.get("items", [])
    is_empty = len(wardrobe_items) == 0

    # Step 2a: Empty wardrobe — ask for general styling advice
    if is_empty:
        prompt = f"""A user just found this secondhand item:
- Name: {new_item['title']}
- Category: {new_item['category']}
- Style tags: {', '.join(new_item['style_tags'])}
- Colors: {', '.join(new_item['colors'])}

They haven't told us what's in their wardrobe yet.
Suggest 1-2 general outfit ideas — what kinds of pieces pair well with this item?
Be specific about garment types, silhouettes, and colors. Keep it to 3-4 sentences."""

    # Step 2b: Wardrobe has items — suggest specific combinations
    else:
        # Format wardrobe items into readable text for the prompt
        # We describe each item so the LLM knows exactly what the user owns
        wardrobe_text = "\n".join([
            f"- {w['name']} ({w['category']}, colors: {', '.join(w['colors'])})"
            + (f" — {w['notes']}" if w.get("notes") else "")
            for w in wardrobe_items
        ])

        prompt = f"""A user just found this secondhand item:
- Name: {new_item['title']}
- Category: {new_item['category']}
- Style tags: {', '.join(new_item['style_tags'])}
- Colors: {', '.join(new_item['colors'])}

Here is their current wardrobe:
{wardrobe_text}

Suggest 1-2 complete outfits using the new item combined with specific pieces 
from their wardrobe. Name each wardrobe piece by name. Describe the overall vibe.
Keep it to 4-5 sentences total."""

    # Step 3: Call the LLM and return its response
    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.7,  # some creativity, but stays coherent
    )

    return response.choices[0].message.content


# ── Tool 3: create_fit_card ───────────────────────────────────────────────────

def create_fit_card(outfit: str, new_item: dict) -> str:
    """Generate an Instagram-style caption for the outfit."""

    # Step 1: Guard against empty outfit input
    # .strip() removes whitespace — "   " would otherwise pass a truthiness check
    if not outfit or not outfit.strip():
        return "found something worth adding to the rotation 🛍️"

    # Also guard against missing new_item fields with .get() + fallbacks
    title = new_item.get("title", "this find")
    price = new_item.get("price", "")
    platform = new_item.get("platform", "a thrift app")

    # Format price nicely — only show if we have it
    price_str = f"${price:.0f}" if price else ""

    client = _get_groq_client()

    # Step 2: Build the caption prompt
    # We're very specific about tone, length, and style here
    # The more specific the instructions, the more consistent the output
    prompt = f"""Write an Instagram caption for this thrifted outfit.

Item: {title}
Price: {price_str} from {platform}
Outfit: {outfit}

Rules:
- Write in ALL lowercase
- 1-3 sentences max
- Sound like a real person posting their OOTD, not a product description
- Mention the item name, price, and platform naturally (once each)
- End with exactly one emoji that fits the vibe
- No hashtags
- Be specific about the look, not generic

Just write the caption. No intro, no explanation."""

    # Step 3: Higher temperature = more variation between runs
    # This is what the milestone means by "outputs vary" — 
    # temperature 0.0 = deterministic, 1.0 = very random
    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.9,  # higher = more creative/varied each time
    )

    return response.choices[0].message.content