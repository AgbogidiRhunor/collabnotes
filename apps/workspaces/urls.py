from django.urls import path
from . import views

app_name = 'workspaces'

urlpatterns = [
    path('', views.WorkspaceListView.as_view(), name='list'),
    path('create/', views.WorkspaceCreateView.as_view(), name='create'),
    path('<uuid:pk>/', views.WorkspaceDetailView.as_view(), name='detail'),
    path('<uuid:pk>/edit/', views.WorkspaceEditView.as_view(), name='edit'),
    path('<uuid:pk>/delete/', views.WorkspaceDeleteView.as_view(), name='delete'),
    path('<uuid:pk>/share/', views.WorkspaceShareView.as_view(), name='share'),
    path('join/<str:token>/', views.WorkspaceJoinView.as_view(), name='join'),
    path('invite/<str:token>/<str:action>/', views.WorkspaceInviteRespondView.as_view(), name='invite_respond'),
]