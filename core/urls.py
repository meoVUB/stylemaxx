from django.urls import path
from . import views

urlpatterns = [
    path('', views.swipe_view, name='swipe'), # default = swipe, like tinder
    path('mystore/', views.mystore_view, name='mystore'),
    path('swipe/', views.swipe_view, name='swipe'),
    path('outfits/', views.outfits_view, name='outfits'),
]