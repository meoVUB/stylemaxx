from django.urls import path
from . import views

urlpatterns = [
    path('', views.swipe_view, name='swipe_dev'), # default = swipe, like tinder
    path('mystore/', views.mystore_view, name='mystore'),
    path('swipe/', views.swipe_view, name='swipe'),
    path('outfits/', views.outfits_view, name='outfits'),
    path("onboarding/", views.onboarding_view, name="onboarding"),

    # sandbox routes for mehmet :)
    path('dev/mystore/', views.mystore_view_dev, name='mystore_dev'),
    path('dev/swipe/', views.swipe_view_dev, name='swipe_dev'),
    path('dev/outfits/', views.outfits_view_dev, name='outfits_dev'),
]