from django.shortcuts import render
from django.conf import settings
from pathlib import Path
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

# ======= Production Views (= Parsa Styling) ========
def mystore_view(request):
    return render(request, 'core/mystore.html')

def swipe_view(request):
    return render(request, 'core/swipe.html')

def outfits_view(request):
    return render(request, 'core/outfits.html')

# ======= Sandbox Views (= Mehmet Logic) ========
def mystore_view_dev(request):
    return render(request, 'sandbox/mystore_logic.html')

def swipe_view_dev(request):
    outfits = load_outfits()
    # UNFINISHED!
    outfit = outfits[0]
    context = {
        "outfit": outfit,
    }
    return render(request, 'sandbox/swipe_logic.html', context)

def outfits_view_dev(request):
    return render(request, 'sandbox/outfits_logic.html')