from django.shortcuts import render, redirect
from django.conf import settings
from pathlib import Path
from django.conf import settings
from django.core.files.storage import default_storage
from django.utils.crypto import get_random_string
import json

# ========= Outfit data loader =========
_OUTFITS_CACHE = None

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
        return redirect("swipe_dev")

    return render(request, "core/onboarding.html")

# ======= Production Views (= Parsa Styling) ========
def mystore_view(request):
    return render(request, 'core/mystore.html')

def swipe_view(request):
    outfits = load_outfits()
    total = len(outfits)

    # current index from session, default 0
    idx = request.session.get("current_outfit_index", 0)

    # Handle POST like/dislike
    if request.method == "POST":
        action = request.POST.get("action")
        prefs = get_preferences(request.session)

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
    return render(request, 'core/outfits.html')

# ======= Sandbox Views (= Mehmet Logic) ========
def mystore_view_dev(request):
    return render(request, 'sandbox/mystore_logic.html')

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
    model_image_url = request.session.get("model_image_url")
    first_name = request.session.get("user_first_name", "")

    context = {
        "model_image_url": model_image_url,
        "first_name": first_name,
        # later: also pass selected outfit items here
    }
    return render(request, "sandbox/outfits_logic.html", context)