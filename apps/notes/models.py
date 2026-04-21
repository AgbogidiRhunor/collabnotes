import uuid
import secrets
from django.conf import settings
from django.db import models
from django.utils import timezone


class Note(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    title = models.CharField(max_length=500, default='Untitled Note')
    content = models.TextField(blank=True, default='')
    creator = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='created_notes',
    )
    workspace = models.ForeignKey(
        'workspaces.Workspace',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='notes',
    )
    is_deleted = models.BooleanField(default=False)
    deleted_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'notes_note'
        ordering = ['-updated_at']
        indexes = [
            models.Index(fields=['-updated_at']),
            models.Index(fields=['creator', '-updated_at']),
            models.Index(fields=['is_deleted']),
        ]

    def soft_delete(self):
        self.is_deleted = True
        self.deleted_at = timezone.now()
        self.save(update_fields=['is_deleted', 'deleted_at'])

    def __str__(self):
        return self.title


class NotePermission(models.Model):
    class Role(models.TextChoices):
        OWNER = 'owner', 'Owner'
        EDITOR = 'editor', 'Editor'
        VIEWER = 'viewer', 'Viewer'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    note = models.ForeignKey(Note, on_delete=models.CASCADE, related_name='permissions')
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='note_permissions',
    )
    role = models.CharField(max_length=10, choices=Role.choices, default=Role.VIEWER)
    granted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='granted_permissions',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'notes_permission'
        unique_together = [('note', 'user')]
        indexes = [
            models.Index(fields=['user', 'note']),
        ]

    @property
    def can_edit(self):
        return self.role in (self.Role.OWNER, self.Role.EDITOR)

    @property
    def can_delete(self):
        return self.role == self.Role.OWNER

    @property
    def can_manage(self):
        return self.role == self.Role.OWNER

    def __str__(self):
        return f'{self.user} — {self.role} on "{self.note}"'


class NoteInvite(models.Model):
    """Pending email invitation to a note. Requires accept/decline before access is granted."""

    class Status(models.TextChoices):
        PENDING = 'pending', 'Pending'
        ACCEPTED = 'accepted', 'Accepted'
        DECLINED = 'declined', 'Declined'

    class Role(models.TextChoices):
        EDITOR = 'editor', 'Editor'
        VIEWER = 'viewer', 'Viewer'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    note = models.ForeignKey(Note, on_delete=models.CASCADE, related_name='invites')
    invited_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='sent_note_invites',
    )
    invited_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='received_note_invites',
    )
    role = models.CharField(max_length=10, choices=Role.choices, default=Role.VIEWER)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING)
    token = models.CharField(max_length=64, unique=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    responded_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'notes_invite'
        # One pending invite per (note, invited_user) pair
        unique_together = [('note', 'invited_user')]
        indexes = [models.Index(fields=['invited_user', 'status'])]

    @classmethod
    def create(cls, note, invited_by, invited_user, role):
        # Replace any existing invite for this user on this note
        cls.objects.filter(note=note, invited_user=invited_user).delete()
        return cls.objects.create(
            note=note,
            invited_by=invited_by,
            invited_user=invited_user,
            role=role,
            token=secrets.token_urlsafe(32),
        )

    def accept(self):
        NotePermission.objects.update_or_create(
            note=self.note,
            user=self.invited_user,
            defaults={'role': self.role, 'granted_by': self.invited_by},
        )
        self.status = self.Status.ACCEPTED
        self.responded_at = timezone.now()
        self.save(update_fields=['status', 'responded_at'])

    def decline(self):
        self.status = self.Status.DECLINED
        self.responded_at = timezone.now()
        self.save(update_fields=['status', 'responded_at'])

    def __str__(self):
        return f'Invite: {self.invited_user} to "{self.note}" as {self.role}'


class NoteVersion(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    note = models.ForeignKey(Note, on_delete=models.CASCADE, related_name='versions')
    title_snapshot = models.CharField(max_length=500)
    content_snapshot = models.TextField()
    saved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='saved_versions',
    )
    label = models.CharField(max_length=200, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'notes_version'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['note', '-created_at']),
        ]

    def __str__(self):
        return f'Version of "{self.note}" at {self.created_at:%Y-%m-%d %H:%M}'


class ShareLink(models.Model):
    class Role(models.TextChoices):
        EDITOR = 'editor', 'Editor'
        VIEWER = 'viewer', 'Viewer'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    note = models.ForeignKey(Note, on_delete=models.CASCADE, related_name='share_links')
    token = models.CharField(max_length=64, unique=True, db_index=True)
    role = models.CharField(max_length=10, choices=Role.choices, default=Role.VIEWER)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='created_share_links',
    )
    expires_at = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'notes_share_link'

    @classmethod
    def create(cls, note, created_by, role='viewer', days=7):
        from datetime import timedelta
        return cls.objects.create(
            note=note,
            created_by=created_by,
            token=secrets.token_urlsafe(32),
            role=role,
            expires_at=timezone.now() + timedelta(days=days),
        )

    @property
    def is_valid(self):
        if not self.is_active:
            return False
        if self.expires_at and timezone.now() > self.expires_at:
            return False
        return True

    def accept(self, user):
        role_rank = {'owner': 3, 'editor': 2, 'viewer': 1}
        perm, created = NotePermission.objects.get_or_create(
            note=self.note,
            user=user,
            defaults={'role': self.role, 'granted_by': self.created_by},
        )
        if not created:
            if role_rank.get(self.role, 0) > role_rank.get(perm.role, 0):
                perm.role = self.role
                perm.save(update_fields=['role'])
        return perm

    def __str__(self):
        return f'ShareLink for "{self.note}" ({self.role})'