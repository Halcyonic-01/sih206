from django.urls import path
from .api import Evidence, Statements

urlpatterns = [path('instruments/<int:pk>/verification/', Evidence.as_view()),
               path('verification/statements/', Statements.as_view())]
