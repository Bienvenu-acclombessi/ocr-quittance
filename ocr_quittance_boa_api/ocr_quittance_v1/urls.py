# myapp/urls.py

from django.urls import path
from .views import ProcessPDFView

urlpatterns = [
    path('process_pdf/', ProcessPDFView.as_view(), name='process_pdf'),
]
