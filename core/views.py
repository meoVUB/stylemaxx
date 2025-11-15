from django.shortcuts import render

def mystore_view(request):
    return render(request, 'core/mystore.html')

def swipe_view(request):
    return render(request, 'core/swipe.html')

def outfits_view(request):
    return render(request, 'core/outfits.html')