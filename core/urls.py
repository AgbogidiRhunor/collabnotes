from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('admin/', admin.site.urls),

    # Accounts (root routes)
    path('', include(('apps.accounts.urls', 'accounts'), namespace='accounts')),

    # Notes app
    path('notes/', include(('apps.notes.urls', 'notes'), namespace='notes')),

    # Workspaces app
    path('workspaces/', include(('apps.workspaces.urls', 'workspaces'), namespace='workspaces')),
]

# Serve media files only in development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)