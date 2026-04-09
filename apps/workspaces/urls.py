from django.urls import path
from . import views

app_name = 'workspaces'

urlpatterns = [
    path('', views.WorkspaceListView.as_view(), name='list'),
    path('create/', views.WorkspaceCreateView.as_view(), name='create'),
    path('<uuid:pk>/edit/', views.WorkspaceEditView.as_view(), name='edit'),
    path('<uuid:pk>/delete/', views.WorkspaceDeleteView.as_view(), name='delete'),
]
