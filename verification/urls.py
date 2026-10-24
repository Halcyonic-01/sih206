from django.urls import path
from .api import Evidence, Statements, BankRequests

urlpatterns = [path('instruments/<int:pk>/verification/', Evidence.as_view()),
               path('instruments/<int:pk>/bank-requests/', BankRequests.as_view()),
               path('verification/statements/', Statements.as_view())]
