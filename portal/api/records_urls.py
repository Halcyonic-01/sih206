from django.urls import path
from .records import CorrectRecord, Dashboard, Download, Export, RecordAction, RecordDetail, Records

urlpatterns = [
    path('instruments/', Records.as_view()),
    path('instruments/export.csv', Export.as_view()),
    path('instruments/<int:pk>/', RecordDetail.as_view()),
    path('instruments/<int:pk>/correct/', CorrectRecord.as_view()),
    path('instruments/<int:pk>/observations/<int:observation_pk>/resolve/', RecordAction.as_view(), {'action': 'resolve'}),
    path('documents/<int:pk>/download/', Download.as_view()),
    path('dashboard/', Dashboard.as_view()),
]
for segment, action in [('submit', 'submit'), ('review', 'review'), ('observations', 'observe'),
                        ('renew', 'renew'), ('documents', 'upload')]:
    urlpatterns.append(path(f'instruments/<int:pk>/{segment}/', RecordAction.as_view(), {'action': action}))
