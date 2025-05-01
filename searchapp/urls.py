from django.urls import path
from . import views

urlpatterns = [
    path('search/', views.search_view, name='search'),  # Маршрут для поиска
    path('api/patients/', views.get_patient_list, name='get_patient_list'),
    path('api/check_patient/', views.check_patient, name='check_patient'),
    path('api/register_patient/', views.register_patient, name='register_patient'),
    path('search/', views.search_form, name='search_form'),
    path('patient/', views.patient_form, name='patient_form'),
]