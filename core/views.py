from django.shortcuts import render, redirect
from django.conf import settings
from pathlib import Path
from django.core.files.storage import default_storage
from django.utils.crypto import get_random_string
import json
import requests
import random

_OUTFITS_CACHE = None
_PRODUCTS_CACHE = None

# ======= Onboarding ========
def onboarding_view(request):
    if request.method == "POST":
        first_name = request.POST.get("first_name", "").strip()
        gender = request.POST.get("gender", "male")
        selfie_file = request.FILES.get("selfie")

        # store basic user info in session
        request.session["user_first_name"] = first_name
        request.session["user_gender"] = gender

        if selfie_file:
            # Save selfie under media/selfies/
            filename = f"selfies/{get_random_string(12)}_{selfie_file.name}"
            path = default_storage.save(filename, selfie_file)

            # build URL: /media/selfies/...
            model_image_url = settings.MEDIA_URL + filename.split("/", 1)[1]
        else:
            # No selfie → use default static image
            if gender.lower() == "female":
                model_image_url = "/static/models/default_female_model.png"
            else:
                model_image_url = "/static/models/default_male_model.png"

        request.session["model_image_url"] = model_image_url
        request.session.modified = True

        # after onboarding, send them to Swipe or Outfits (up to you)
        return redirect("swipe")

    return render(request, "core/onboarding.html")

# ========= Outfit data loader =========
def load_outfits():
    global _OUTFITS_CACHE
    if _OUTFITS_CACHE is None:
        data_path = Path(settings.BASE_DIR) / "core" / "data" / "streetwear_1_to_30_flat_keywords.json"
        with data_path.open(encoding="utf-8") as f:
            outfits = json.load(f)

        # add static path for Django's {% static %} tag
        for o in outfits:
            o["static_path"] = f"outfits/{o['image']}"

        _OUTFITS_CACHE = outfits
    return _OUTFITS_CACHE

# ========= Preference helpers =========
def get_preferences(session):
    """Return preferences dict from session, with default structure."""
    prefs = session.get("preferences")
    if not prefs:
        prefs = {"keywords": {}}
    return prefs

def save_preferences(session, prefs):
    session["preferences"] = prefs
    session.modified = True

def update_preferences_with_outfit(prefs, outfit):
    """Increment keyword counts based on outfit keywords."""
    kw_counts = prefs.setdefault("keywords", {})
    for kw in outfit.get("keywords", []):
        kw_counts[kw] = kw_counts.get(kw, 0) + 1
    return prefs

# ========= Product data loader =========
def categorize_product(p):
    """
    Very lightweight category inference based on keywords/name.
    We only need 'top' vs 'bottom' for now.
    """
    text = (p.get("name", "") + " " + " ".join(p.get("keywords", []))).lower()

    bottom_tokens = ["pants", "jeans", "cargo", "chino", "trousers"]
    top_tokens = ["tshirt", "tee", "hoodie", "sweatshirt", "shirt", "jacket", "longsleeve"]

    for token in bottom_tokens:
        if token in text:
            return "bottom"
    for token in top_tokens:
        if token in text:
            return "top"
    return None

def load_products():
    """
    Load products from core/data/streetwear_products_combined.json
    and attach a static_path for each image.
    """
    global _PRODUCTS_CACHE
    if _PRODUCTS_CACHE is None:
        data_path = Path(settings.BASE_DIR) / "core" / "data" / "streetwear_products_combined.json"
        with data_path.open(encoding="utf-8") as f:
            products = json.load(f)

        for p in products:
            p["static_path"] = f"products/{p['id']}.png"
            p["category"] = categorize_product(p)

        _PRODUCTS_CACHE = products
    return _PRODUCTS_CACHE

# ======= Nosana outfit generation =======
def generate_outfit_with_nosana(tops, bottoms, prefs, last_top_id=None, last_bottom_id=None):
    """
    Ask the Nosana-hosted LLM to pick one top + one bottom.
    We then enforce a rule: do not repeat the same top or bottom
    consecutively if there is an alternative.
    Returns (top_id, bottom_id, outfit_name, style_notes, error_message).
    """
    # Fallback in case Nosana is unavailable or not enough items
    def simple_fallback():
        top = tops[0] if tops else None
        bottom = bottoms[0] if bottoms else None
        if not top or not bottom:
            return None, None, None, None, "Not enough items to build an outfit"
        return top["id"], bottom["id"], "Simple fallback fit", "Chosen without AI (fallback).", None

    if not tops or not bottoms:
        return simple_fallback()

    base = (getattr(settings, "NOSANA_BASE_URL", "") or "").rstrip("/")
    model_name = getattr(settings, "NOSANA_MODEL_NAME", "gpt-oss-20b")
    api_key = getattr(settings, "NOSANA_API_KEY", "dummy")

    if not base:
        return simple_fallback()

    # Build URL deterministically
    if base.endswith("/v1"):
        url = base + "/chat/completions"
    elif "/v1/" in base:
        url = base.rstrip("/") + "/chat/completions"
    else:
        url = base + "/v1/chat/completions"

    # Deterministic subset: first N candidates
    tops_small = tops[:4]
    bottoms_small = bottoms[:4]

    def simplify(p):
        return {
            "id": p["id"],
            "name": p["name"],
            "category": p.get("category"),
            "price": p.get("price"),
            "currency": p.get("currency"),
            "keywords": (p.get("keywords", []) or [])[:3],
        }

    catalog = [simplify(p) for p in tops_small + bottoms_small]

    kw_counts = prefs.get("keywords", {})
    sorted_kw = sorted(kw_counts.items(), key=lambda x: x[1], reverse=True)
    top_prefs = [kw for kw, c in sorted_kw[:5]]

    system_msg = (
        "You are a streetwear stylist AI for an e-commerce app. "
        "You must choose exactly one TOP and one BOTTOM item from the given catalog. "
        "Only use item IDs that exist in the catalog."
    )

    avoid_text_parts = []
    if last_top_id:
        avoid_text_parts.append(f"Do not reuse this top ID if possible: {last_top_id}.")
    if last_bottom_id:
        avoid_text_parts.append(f"Do not reuse this bottom ID if possible: {last_bottom_id}.")
    avoid_text = (" ".join(avoid_text_parts) + "\n") if avoid_text_parts else ""

    user_msg = (
        avoid_text +
        "User style keywords (most important first): "
        f"{top_prefs if top_prefs else 'none'}.\n\n"
        "Catalog items (JSON list):\n"
        f"{json.dumps(catalog, ensure_ascii=False)}\n\n"
        "Pick exactly one item with category 'top' and one item with category 'bottom' "
        "that best match the user's style. Return ONLY a JSON object with this format:\n"
        "{\n"
        '  \"top_id\": \"<id of chosen top>\",\n'
        '  \"bottom_id\": \"<id of chosen bottom>\",\n'
        '  \"outfit_name\": \"<short creative name for the outfit>\",\n'
        '  \"style_notes\": \"<one or two sentences describing why this works>\"\n'
        "}\n"
        "No extra text, no markdown."
    )

    payload = {
        "model": model_name,
        "messages": [
            {"role": "system", "content": system_msg},
            {"role": "user", "content": user_msg},
        ],
        "temperature": 0.7,
    }

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
    }

    try:
        resp = requests.post(url, headers=headers, json=payload, timeout=90)
        resp.raise_for_status()
        data = resp.json()
        content = data["choices"][0]["message"]["content"]
    except Exception as e:
        top_id, bottom_id, name, notes, _ = simple_fallback()
        return top_id, bottom_id, name, notes, f"Nosana call failed: {e}"

    # Parse JSON from LLM
    try:
        parsed = json.loads(content)
        top_id = parsed.get("top_id")
        bottom_id = parsed.get("bottom_id")
        outfit_name = parsed.get("outfit_name") or "AI-picked fit"
        style_notes = parsed.get("style_notes") or ""
    except Exception:
        top_id, bottom_id, name, notes, _ = simple_fallback()
        return top_id, bottom_id, name, notes, "Nosana returned invalid JSON."

    # Validate IDs
    valid_top_ids = {p["id"] for p in tops}
    valid_bottom_ids = {p["id"] for p in bottoms}
    if top_id not in valid_top_ids or bottom_id not in valid_bottom_ids:
        top_id, bottom_id, name, notes, _ = simple_fallback()
        return top_id, bottom_id, name, notes, "Nosana chose IDs not in catalog."

    # HARD RULE: do not repeat same top/bottom consecutively if any alternative exists
    if last_top_id and top_id == last_top_id and len(tops) > 1:
        # pick first different top in deterministic order
        alt_top = next((p for p in tops if p["id"] != last_top_id), None)
        if alt_top:
            top_id = alt_top["id"]
            if style_notes:
                style_notes += " We changed the top to avoid repetition."
            else:
                style_notes = "We changed the top to avoid repetition."

    if last_bottom_id and bottom_id == last_bottom_id and len(bottoms) > 1:
        # pick first different bottom in deterministic order
        alt_bottom = next((p for p in bottoms if p["id"] != last_bottom_id), None)
        if alt_bottom:
            bottom_id = alt_bottom["id"]
            if style_notes:
                style_notes += " We changed the pants to avoid repetition."
            else:
                style_notes = "We changed the pants to avoid repetition."

    return top_id, bottom_id, outfit_name, style_notes, None

# ======= Production Views (= Parsa Styling) ========
def mystore_view(request):
    products = load_products()
    prefs = get_preferences(request.session)
    kw_counts = prefs.get("keywords", {})

    if not kw_counts:
        # No preferences yet → empty shop
        top_products = []
    else:
        # score products by keyword overlap
        scored = []
        for p in products:
            score = sum(kw_counts.get(kw, 0) for kw in p.get("keywords", []))
            if score > 0:
                scored.append((score, p))

        scored.sort(key=lambda sp: (-sp[0], sp[1]["name"]))
        top_products = [p for score, p in scored[:24]]

    context = {
        "products": top_products,
        "has_preferences": bool(kw_counts),
    }
    return render(request, "core/mystore.html", context)

def swipe_view(request):
     # If the user has not completed onboarding → redirect
    if not request.session.get("model_image_url"):
        return redirect("onboarding")

    outfits = load_outfits()
    total = len(outfits)

    # current index from session, default 0
    idx = request.session.get("current_outfit_index", 0)

    # Handle POST like/dislike
    if request.method == "POST":
        action = request.POST.get("action")
        prefs = get_preferences(request.session)

        if action == "reset":
            request.session["current_outfit_index"] = 0
            save_preferences(request.session, {"keywords": {}})
            request.session.modified = True
            return redirect("swipe")

        # Apply preference update only if there is a current outfit
        if 0 <= idx < total:
            current_outfit = outfits[idx]
            if action == "like":
                prefs = update_preferences_with_outfit(prefs, current_outfit)
                save_preferences(request.session, prefs)

        # Move to next outfit
        idx += 1
        request.session["current_outfit_index"] = idx
        request.session.modified = True

        # Redirect to avoid form resubmission on refresh
        return redirect("swipe")

    # GET request: decide which outfit to show
    if 0 <= idx < total:
        outfit = outfits[idx]
        done = False
    else:
        outfit = None
        done = True

    prefs = get_preferences(request.session)
    top_keywords = sorted(
        prefs["keywords"].items(),
        key=lambda x: x[1],
        reverse=True
    )[:10]

    context = {
        "outfit": outfit,
        "done": done,
        "index": idx,
        "total": total,
        "top_keywords": top_keywords,
    }
    return render(request, 'core/swipe.html', context)

def outfits_view(request):
    # Require onboarding/model
    model_image_url = request.session.get("model_image_url")
    first_name = request.session.get("user_first_name", "")
    if not model_image_url:
        return redirect("onboarding")

    products = load_products()
    prefs = get_preferences(request.session)
    kw_counts = prefs.get("keywords", {})

    # Need preferences to generate meaningful outfit
    if not kw_counts:
        context = {
            "model_image_url": model_image_url,
            "first_name": first_name,
            "has_preferences": False,
            "outfit": None,
            "error": None,
        }
        return render(request, "sandbox/outfits_logic.html", context)

    # Score all products (no filtering on score > 0)
    scored = []
    for p in products:
        score = sum(kw_counts.get(kw, 0) for kw in p.get("keywords", []))
        scored.append((score, p))

    # Deterministic order: score desc, then name
    scored.sort(key=lambda sp: (-sp[0], sp[1]["name"]))
    relevant_products = [p for score, p in scored]

    # Split into tops/bottoms based on category
    tops = [p for p in relevant_products if p.get("category") == "top"]
    bottoms = [p for p in relevant_products if p.get("category") == "bottom"]

    # Last chosen IDs from previous outfit (for diversity)
    last_ids = request.session.get("last_outfit_ids") or {}
    last_top_id = last_ids.get("top_id")
    last_bottom_id = last_ids.get("bottom_id")

    top_id, bottom_id, outfit_name, style_notes, error = generate_outfit_with_nosana(
        tops, bottoms, prefs, last_top_id=last_top_id, last_bottom_id=last_bottom_id
    )

    outfit_products = []
    total_price = 0
    currency = None

    prod_by_id = {p["id"]: p for p in products}

    if top_id and top_id in prod_by_id:
        p = prod_by_id[top_id]
        outfit_products.append(p)
        total_price += p.get("price") or 0
        currency = currency or p.get("currency")

    if bottom_id and bottom_id in prod_by_id:
        p = prod_by_id[bottom_id]
        outfit_products.append(p)
        total_price += p.get("price") or 0
        currency = currency or p.get("currency")

    outfit = {
        "name": outfit_name,
        "style_notes": style_notes,
        "items": outfit_products,
        "total_price": total_price,
        "currency": currency or "EUR",
    }

    # Save current choice so next time we can forbid repeats
    request.session["last_outfit_ids"] = {
        "top_id": top_id,
        "bottom_id": bottom_id,
    }
    request.session.modified = True

    context = {
        "model_image_url": model_image_url,
        "first_name": first_name,
        "has_preferences": True,
        "outfit": outfit,
        "error": error,
    }
    return render(request, 'core/outfits.html', context)

# ======= Sandbox Views (= Mehmet Logic) ========
def mystore_view_dev(request):
    products = load_products()
    prefs = get_preferences(request.session)
    kw_counts = prefs.get("keywords", {})

    if not kw_counts:
        # No preferences yet → empty shop
        top_products = []
    else:
        # score products by keyword overlap
        scored = []
        for p in products:
            score = sum(kw_counts.get(kw, 0) for kw in p.get("keywords", []))
            if score > 0:
                scored.append((score, p))

        scored.sort(key=lambda sp: (-sp[0], sp[1]["name"]))
        top_products = [p for score, p in scored[:24]]

    context = {
        "products": top_products,
        "has_preferences": bool(kw_counts),
    }
    return render(request, "sandbox/mystore_logic.html", context)

def swipe_view_dev(request):
    # If the user has not completed onboarding → redirect
    if not request.session.get("model_image_url"):
        return redirect("onboarding")
    
    outfits = load_outfits()
    total = len(outfits)

    # current index from session, default 0
    idx = request.session.get("current_outfit_index", 0)

    # Handle POST like/dislike
    if request.method == "POST":
        action = request.POST.get("action")
        prefs = get_preferences(request.session)

        if action == "reset":
            request.session["current_outfit_index"] = 0
            save_preferences(request.session, {"keywords": {}})
            request.session.modified = True
            return redirect("swipe_dev")

        # Apply preference update only if there is a current outfit
        if 0 <= idx < total:
            current_outfit = outfits[idx]
            if action == "like":
                prefs = update_preferences_with_outfit(prefs, current_outfit)
                save_preferences(request.session, prefs)

        # Move to next outfit
        idx += 1
        request.session["current_outfit_index"] = idx
        request.session.modified = True

        # Redirect to avoid form resubmission on refresh
        return redirect("swipe_dev")

    # GET request: decide which outfit to show
    if 0 <= idx < total:
        outfit = outfits[idx]
        done = False
    else:
        outfit = None
        done = True

    prefs = get_preferences(request.session)
    top_keywords = sorted(
        prefs["keywords"].items(),
        key=lambda x: x[1],
        reverse=True
    )[:10]

    context = {
        "outfit": outfit,
        "done": done,
        "index": idx,
        "total": total,
        "top_keywords": top_keywords,
    }
    return render(request, 'sandbox/swipe_logic.html', context)

def outfits_view_dev(request):
    # Require onboarding/model
    model_image_url = request.session.get("model_image_url")
    first_name = request.session.get("user_first_name", "")
    if not model_image_url:
        return redirect("onboarding")

    products = load_products()
    prefs = get_preferences(request.session)
    kw_counts = prefs.get("keywords", {})

    # Need preferences to generate meaningful outfit
    if not kw_counts:
        context = {
            "model_image_url": model_image_url,
            "first_name": first_name,
            "has_preferences": False,
            "outfit": None,
            "error": None,
        }
        return render(request, "sandbox/outfits_logic.html", context)

    # Score all products (no filtering on score > 0)
    scored = []
    for p in products:
        score = sum(kw_counts.get(kw, 0) for kw in p.get("keywords", []))
        scored.append((score, p))

    # Deterministic order: score desc, then name
    scored.sort(key=lambda sp: (-sp[0], sp[1]["name"]))
    relevant_products = [p for score, p in scored]

    # Split into tops/bottoms based on category
    tops = [p for p in relevant_products if p.get("category") == "top"]
    bottoms = [p for p in relevant_products if p.get("category") == "bottom"]

    # Last chosen IDs from previous outfit (for diversity)
    last_ids = request.session.get("last_outfit_ids") or {}
    last_top_id = last_ids.get("top_id")
    last_bottom_id = last_ids.get("bottom_id")

    top_id, bottom_id, outfit_name, style_notes, error = generate_outfit_with_nosana(
        tops, bottoms, prefs, last_top_id=last_top_id, last_bottom_id=last_bottom_id
    )

    outfit_products = []
    total_price = 0
    currency = None

    prod_by_id = {p["id"]: p for p in products}

    if top_id and top_id in prod_by_id:
        p = prod_by_id[top_id]
        outfit_products.append(p)
        total_price += p.get("price") or 0
        currency = currency or p.get("currency")

    if bottom_id and bottom_id in prod_by_id:
        p = prod_by_id[bottom_id]
        outfit_products.append(p)
        total_price += p.get("price") or 0
        currency = currency or p.get("currency")

    outfit = {
        "name": outfit_name,
        "style_notes": style_notes,
        "items": outfit_products,
        "total_price": total_price,
        "currency": currency or "EUR",
    }

    # Save current choice so next time we can forbid repeats
    request.session["last_outfit_ids"] = {
        "top_id": top_id,
        "bottom_id": bottom_id,
    }
    request.session.modified = True

    context = {
        "model_image_url": model_image_url,
        "first_name": first_name,
        "has_preferences": True,
        "outfit": outfit,
        "error": error,
    }
    return render(request, "sandbox/outfits_logic.html", context)