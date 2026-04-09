"""
NoteConsumer — Real-time collaborative editing via Django Channels.

Flow:
  1. User opens a note detail page → browser connects to ws/notes/<pk>/
  2. Consumer verifies the user has at least viewer permission (from DB)
  3. Editor users can send content updates; viewer users are read-only
  4. Any content update is broadcast to all other users in the same room
  5. On disconnect the latest content is saved to the database
"""

import json
import logging
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.utils import timezone

logger = logging.getLogger(__name__)


class NoteConsumer(AsyncWebsocketConsumer):

    # ── Connection ────────────────────────────────────────────────────────────

    async def connect(self):
        self.note_id = self.scope['url_route']['kwargs']['note_id']
        self.room_group = f'note_{self.note_id}'
        self.user = self.scope['user']

        # Reject unauthenticated connections immediately
        if not self.user.is_authenticated:
            await self.close(code=4001)
            return

        # Check the user has at least viewer access
        self.permission = await self._get_permission()
        if self.permission is None:
            await self.close(code=4003)
            return

        await self.channel_layer.group_add(self.room_group, self.channel_name)
        await self.accept()

        # Tell everyone else this user joined
        await self.channel_layer.group_send(self.room_group, {
            'type': 'user_joined',
            'user_id': str(self.user.id),
            'display_name': self.user.display_name,
            'initials': self.user.get_initials(),
        })

    async def disconnect(self, close_code):
        if not self.user.is_authenticated:
            return

        await self.channel_layer.group_discard(self.room_group, self.channel_name)

        # Tell everyone this user left
        await self.channel_layer.group_send(self.room_group, {
            'type': 'user_left',
            'user_id': str(self.user.id),
            'display_name': self.user.display_name,
        })

    # ── Receive from browser ──────────────────────────────────────────────────

    async def receive(self, text_data):
        try:
            data = json.loads(text_data)
        except (json.JSONDecodeError, ValueError):
            await self._send_error('Invalid message format.')
            return

        msg_type = data.get('type')

        if msg_type == 'content_update':
            await self._handle_content_update(data)

        elif msg_type == 'title_update':
            await self._handle_title_update(data)

        elif msg_type == 'cursor':
            await self._handle_cursor(data)

        elif msg_type == 'ping':
            await self.send(text_data=json.dumps({'type': 'pong'}))

    # ── Message handlers ──────────────────────────────────────────────────────

    async def _handle_content_update(self, data):
        """Editor sends full note content; server saves and broadcasts."""
        if not self.permission.can_edit:
            await self._send_error('You only have viewer access to this note.')
            return

        content = str(data.get('content', ''))
        title = str(data.get('title', '')).strip()[:500]

        # Sanitise on the server — never trust the client
        import bleach
        from django.conf import settings
        clean_content = bleach.clean(
            content,
            tags=settings.BLEACH_ALLOWED_TAGS,
            attributes=settings.BLEACH_ALLOWED_ATTRIBUTES,
            strip=True,
        )

        # Persist to the database
        await self._save_note(title, clean_content)

        # Broadcast the clean content to all OTHER users in the room
        await self.channel_layer.group_send(self.room_group, {
            'type': 'broadcast_content',
            'content': clean_content,
            'title': title,
            'sender_channel': self.channel_name,
            'display_name': self.user.display_name,
        })

    async def _handle_title_update(self, data):
        if not self.permission.can_edit:
            return
        title = str(data.get('title', '')).strip()[:500]
        await self._save_title(title)
        await self.channel_layer.group_send(self.room_group, {
            'type': 'broadcast_title',
            'title': title,
            'sender_channel': self.channel_name,
        })

    async def _handle_cursor(self, data):
        """Broadcast cursor position so collaborators see where others are."""
        await self.channel_layer.group_send(self.room_group, {
            'type': 'broadcast_cursor',
            'user_id': str(self.user.id),
            'display_name': self.user.display_name,
            'initials': self.user.get_initials(),
            'position': data.get('position', 0),
            'sender_channel': self.channel_name,
        })

    # ── Group event handlers (called by channel layer) ────────────────────────

    async def broadcast_content(self, event):
        """Deliver content update to this specific client (skip the sender)."""
        if event['sender_channel'] == self.channel_name:
            # Confirm save back to sender
            await self.send(text_data=json.dumps({
                'type': 'saved',
                'timestamp': timezone.now().isoformat(),
            }))
            return

        await self.send(text_data=json.dumps({
            'type': 'content_update',
            'content': event['content'],
            'title': event['title'],
            'updated_by': event['display_name'],
        }))

    async def broadcast_title(self, event):
        if event['sender_channel'] == self.channel_name:
            return
        await self.send(text_data=json.dumps({
            'type': 'title_update',
            'title': event['title'],
        }))

    async def broadcast_cursor(self, event):
        if event['sender_channel'] == self.channel_name:
            return
        await self.send(text_data=json.dumps({
            'type': 'cursor',
            'user_id': event['user_id'],
            'display_name': event['display_name'],
            'initials': event['initials'],
            'position': event['position'],
        }))

    async def user_joined(self, event):
        await self.send(text_data=json.dumps({
            'type': 'user_joined',
            'user_id': event['user_id'],
            'display_name': event['display_name'],
            'initials': event['initials'],
        }))

    async def user_left(self, event):
        await self.send(text_data=json.dumps({
            'type': 'user_left',
            'user_id': event['user_id'],
            'display_name': event['display_name'],
        }))

    # ── Database helpers ──────────────────────────────────────────────────────

    @database_sync_to_async
    def _get_permission(self):
        from .models import NotePermission
        try:
            return NotePermission.objects.select_related('note').get(
                note_id=self.note_id,
                user=self.user,
                note__is_deleted=False,
            )
        except NotePermission.DoesNotExist:
            return None

    @database_sync_to_async
    def _save_note(self, title, content):
        from .models import Note
        try:
            Note.objects.filter(pk=self.note_id).update(
                title=title,
                content=content,
                updated_at=timezone.now(),
            )
        except Exception as exc:
            logger.error('Failed to save note %s: %s', self.note_id, exc)

    @database_sync_to_async
    def _save_title(self, title):
        from .models import Note
        Note.objects.filter(pk=self.note_id).update(
            title=title,
            updated_at=timezone.now(),
        )

    # ── Helpers ───────────────────────────────────────────────────────────────

    async def _send_error(self, message):
        await self.send(text_data=json.dumps({
            'type': 'error',
            'message': message,
        }))
