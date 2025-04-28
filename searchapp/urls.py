from django.urls import path
from . import views

urlpatterns = [
    path('search/', views.search_view, name='search'),  # Маршрут для поиска
    path('api/patients/', views.get_patient_list, name='get_patient_list'),
    path('api/check_patient/', views.check_patient, name='check_patient'),
    path('api/register_patient/', views.register_patient, name='register_patient'),
]