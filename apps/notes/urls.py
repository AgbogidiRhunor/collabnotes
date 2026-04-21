from django.urls import path
from . import views

app_name = 'notes'

urlpatterns = [
    path('', views.NoteListView.as_view(), name='list'),
    path('create/', views.NoteCreateView.as_view(), name='create'),
    path('<uuid:pk>/', views.NoteDetailView.as_view(), name='detail'),
    path('<uuid:pk>/delete/', views.NoteDeleteView.as_view(), name='delete'),
    path('<uuid:pk>/share/', views.NoteShareView.as_view(), name='share'),
    path('<uuid:pk>/versions/', views.NoteVersionsView.as_view(), name='versions'),
    path('<uuid:pk>/history/<uuid:version_pk>/restore/', views.NoteRestoreVersionView.as_view(), name='restore_version'),
    path('join/<str:token>/', views.JoinNoteView.as_view(), name='join'),
    path('invite/<str:token>/<str:action>/', views.NoteInviteRespondView.as_view(), name='invite_respond'),
]