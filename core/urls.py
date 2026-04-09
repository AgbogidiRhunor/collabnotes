from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.views.generic import RedirectView

urlpatterns = [
    path('admin/', admin.site.urls),
    path('accounts/', include('apps.accounts.urls', namespace='accounts')),
    path('notes/', include('apps.notes.urls', namespace='notes')),
    path('workspaces/', include('apps.workspaces.urls', namespace='workspaces')),
    # Root redirect to notes list
    path('', RedirectView.as_view(url='/notes/', permanent=False)),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
