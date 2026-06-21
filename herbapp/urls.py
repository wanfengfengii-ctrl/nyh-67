from django.urls import path

from . import views

app_name = 'herbapp'

urlpatterns = [
    path('', views.BatchListView.as_view(), name='batch_list'),
    path('batch/create/', views.BatchCreateView.as_view(), name='batch_create'),
    path('batch/<int:pk>/', views.BatchDetailView.as_view(), name='batch_detail'),
    path('batch/<int:pk>/round/create/', views.RoundCreateView.as_view(), name='round_create'),
    path('batch/<int:pk>/accept/', views.AcceptanceView.as_view(), name='acceptance'),
    path('batch/<int:pk>/chart/', views.BatchChartView.as_view(), name='batch_chart'),
]
