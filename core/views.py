from django.shortcuts import render

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
    # TODO: real logic
    context = {}
    return render(request, 'sandbox/swipe_logic.html', context)

def outfits_view_dev(request):
    return render(request, 'sandbox/outfits_logic.html')