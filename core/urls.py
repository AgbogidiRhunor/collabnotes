from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('apps.accounts.urls', namespace='accounts')),
    path('accounts/', include('apps.accounts.urls', namespace='accounts')),
    path('notes/', include('apps.notes.urls', namespace='notes')),
    path('workspaces/', include('apps.workspaces.urls', namespace='workspaces')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)