from django.urls import re_path
from .consumers import NoteConsumer

websocket_urlpatterns = [
    re_path(
        r'^ws/notes/(?P<note_id>[0-9a-f-]{36})/$',
        NoteConsumer.as_asgi(),
    ),
]
