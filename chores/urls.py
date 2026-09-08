from django.urls import path

from chores import views

app_name = 'chores'

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('settings/', views.household_settings, name='household_settings'),
    path('chore/<int:pk>/', views.occurrence_detail, name='occurrence_detail'),
    path('chore/<int:pk>/complete/', views.complete, name='complete'),
    path('chore/<int:pk>/claim/', views.claim, name='claim'),
]
