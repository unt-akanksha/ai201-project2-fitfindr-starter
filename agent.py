"""
agent.py
"""

import json
import os
import re

from dotenv import load_dotenv
from groq import Groq

from tools import search_listings, suggest_outfit, create_fit_card

load_dotenv()


def _get_groq_client():
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        raise ValueError("GROQ_API_KEY not set.")
    return Groq(api_key=api_key)


def _new_session(query: str, wardrobe: dict) -> dict:
    return {
        "query": query,
        "parsed": {},
        "search_results": [],
        "selected_item": None,
        "wardrobe": wardrobe,
        "outfit_suggestion": None,
        "fit_card": None,
        "error": None,
    }


def _parse_query(query: str) -> dict:
    """
    Use the LLM to extract description, size, and max_price from a natural
    language query. Returns a dict with those three keys.

    Why LLM parsing? Regex breaks on natural language variations.
    "under thirty bucks size medium" would fool a regex but not an LLM.

    We ask the model to return ONLY JSON — no explanation, no markdown.
    Then we parse that JSON. If it fails, we fall back to safe defaults.
    """
    client = _get_groq_client()

    prompt = f"""Extract search parameters from this fashion query.
Return ONLY a JSON object with exactly these three keys:
- "description": the item being searched for (string)
- "size": clothing size like S, M, L, XL, or null if not mentioned
- "max_price": maximum price as a number, or null if not mentioned

Query: "{query}"

Return only the JSON. No explanation. No markdown. No backticks."""

    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.0,  # deterministic — we want consistent extraction
    )

    raw = response.choices[0].message.content.strip()

    # Try to parse the JSON the LLM returned
    # We wrap in try/except because LLMs occasionally ignore instructions
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        # Fallback: treat the whole query as the description
        # This is graceful degradation — we don't crash, we do our best
        parsed = {
            "description": query,
            "size": None,
            "max_price": None,
        }

    return parsed


def run_agent(query: str, wardrobe: dict) -> dict:
    """
    Main planning loop. Runs all tools in sequence, branching on results.
    Returns the completed session dict.
    """

    # Step 1: Initialize session — all state lives here
    session = _new_session(query, wardrobe)

    # Step 2: Parse the query into structured parameters
    # This lets search_listings receive clean inputs instead of raw text
    try:
        parsed = _parse_query(query)
    except Exception as e:
        session["error"] = f"Couldn't understand your query. Try being more specific. ({e})"
        return session

    session["parsed"] = parsed  # store so we can inspect it later

    description = parsed.get("description", query)
    size = parsed.get("size")          # None if not mentioned
    max_price = parsed.get("max_price") # None if not mentioned

    # Step 3: Search for listings
    # ── THIS IS THE PLANNING LOOP BRANCH ──
    # We check the result BEFORE deciding whether to continue
    try:
        results = search_listings(description, size, max_price)
    except Exception as e:
        session["error"] = f"Search failed: {e}"
        return session

    session["search_results"] = results

    # ← The key branch: if empty, stop here. Do NOT call suggest_outfit.
    if not results:
        # Build a helpful message using what we know about their search
        size_str = f" in size {size}" if size else ""
        price_str = f" under ${max_price:.0f}" if max_price else ""
        session["error"] = (
            f"No listings found for '{description}'{size_str}{price_str}. "
            f"Try a broader description or raise your budget."
        )
        return session  # early return — fit_card and outfit stay None

    # Step 4: Pick the top result
    # results is sorted by relevance score, so index 0 is best match
    session["selected_item"] = results[0]

    # Step 5: Suggest an outfit
    # Only reaches here if we have a real selected_item
    try:
        outfit = suggest_outfit(session["selected_item"], wardrobe)
    except Exception as e:
        session["error"] = f"Outfit suggestion failed: {e}"
        return session

    session["outfit_suggestion"] = outfit

    # Step 6: Generate the fit card
    try:
        fit_card = create_fit_card(session["outfit_suggestion"], session["selected_item"])
    except Exception as e:
        # Fit card failure is non-fatal — we still have the outfit suggestion
        # So we use the fallback instead of stopping completely
        fit_card = "found something worth adding to the rotation 🛍️"

    session["fit_card"] = fit_card

    # Step 7: Return the complete session
    return session


if __name__ == "__main__":
    from utils.data_loader import get_example_wardrobe

    print("=== Happy path: graphic tee ===\n")
    session = run_agent(
        query="looking for a vintage graphic tee under $30",
        wardrobe=get_example_wardrobe(),
    )
    if session["error"]:
        print(f"Error: {session['error']}")
    else:
        print(f"Parsed: {session['parsed']}")
        print(f"Found: {session['selected_item']['title']}")
        print(f"\nOutfit: {session['outfit_suggestion']}")
        print(f"\nFit card: {session['fit_card']}")

    print("\n\n=== No-results path ===\n")
    session2 = run_agent(
        query="designer ballgown size XXS under $5",
        wardrobe=get_example_wardrobe(),
    )
    print(f"Error message: {session2['error']}")
    print(f"fit_card is None: {session2['fit_card'] is None}")  # must be True