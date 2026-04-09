from django.urls import path
from . import views

app_name = 'notes'

urlpatterns = [
    path('', views.NoteListView.as_view(), name='list'),
    path('create/', views.NoteCreateView.as_view(), name='create'),
    path('<uuid:pk>/', views.NoteDetailView.as_view(), name='detail'),
    path('<uuid:pk>/delete/', views.NoteDeleteView.as_view(), name='delete'),
    path('<uuid:pk>/share/', views.NoteShareView.as_view(), name='share'),
    path('<uuid:pk>/history/', views.NoteHistoryView.as_view(), name='history'),
    path('<uuid:pk>/history/save/', views.SaveVersionView.as_view(), name='save_version'),
    path('<uuid:pk>/history/<uuid:version_pk>/restore/', views.NoteRestoreVersionView.as_view(), name='restore_version'),
    path('join/<str:token>/', views.JoinNoteView.as_view(), name='join'),
]
