import uuid
import secrets
from django.conf import settings
from django.db import models
from django.utils import timezone


class Workspace(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='workspaces',
    )
    color = models.CharField(max_length=7, default='#c8a97a')
    is_deleted = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'workspaces_workspace'
        ordering = ['name']

    def __str__(self):
        return self.name


class WorkspacePermission(models.Model):
    class Role(models.TextChoices):
        EDITOR = 'editor', 'Editor'
        VIEWER = 'viewer', 'Viewer'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    workspace = models.ForeignKey(Workspace, on_delete=models.CASCADE, related_name='permissions')
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='workspace_permissions',
    )
    role = models.CharField(max_length=10, choices=Role.choices, default=Role.VIEWER)
    granted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='granted_workspace_permissions',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'workspaces_permission'
        unique_together = [('workspace', 'user')]

    def __str__(self):
        return f'{self.user} — {self.role} on "{self.workspace}"'


class WorkspaceInvite(models.Model):
    """Pending email invitation to a workspace."""

    class Status(models.TextChoices):
        PENDING = 'pending', 'Pending'
        ACCEPTED = 'accepted', 'Accepted'
        DECLINED = 'declined', 'Declined'

    class Role(models.TextChoices):
        EDITOR = 'editor', 'Editor'
        VIEWER = 'viewer', 'Viewer'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    workspace = models.ForeignKey(Workspace, on_delete=models.CASCADE, related_name='invites')
    invited_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='sent_workspace_invites',
    )
    invited_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='received_workspace_invites',
    )
    role = models.CharField(max_length=10, choices=Role.choices, default=Role.VIEWER)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING)
    token = models.CharField(max_length=64, unique=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    responded_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'workspaces_invite'
        unique_together = [('workspace', 'invited_user')]
        indexes = [models.Index(fields=['invited_user', 'status'])]

    @classmethod
    def create(cls, workspace, invited_by, invited_user, role):
        cls.objects.filter(workspace=workspace, invited_user=invited_user).delete()
        return cls.objects.create(
            workspace=workspace,
            invited_by=invited_by,
            invited_user=invited_user,
            role=role,
            token=secrets.token_urlsafe(32),
        )

    def accept(self):
        WorkspacePermission.objects.update_or_create(
            workspace=self.workspace,
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
        return f'Invite: {self.invited_user} to "{self.workspace}" as {self.role}'


class WorkspaceShareLink(models.Model):
    class Role(models.TextChoices):
        EDITOR = 'editor', 'Editor'
        VIEWER = 'viewer', 'Viewer'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    workspace = models.ForeignKey(Workspace, on_delete=models.CASCADE, related_name='share_links')
    token = models.CharField(max_length=64, unique=True, db_index=True)
    role = models.CharField(max_length=10, choices=Role.choices, default=Role.VIEWER)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='created_workspace_share_links',
    )
    expires_at = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'workspaces_share_link'

    @classmethod
    def create(cls, workspace, created_by, role='viewer', days=7):
        from datetime import timedelta
        return cls.objects.create(
            workspace=workspace,
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
        role_rank = {'editor': 2, 'viewer': 1}
        perm, created = WorkspacePermission.objects.get_or_create(
            workspace=self.workspace,
            user=user,
            defaults={'role': self.role, 'granted_by': self.created_by},
        )
        if not created and role_rank.get(self.role, 0) > role_rank.get(perm.role, 0):
            perm.role = self.role
            perm.save(update_fields=['role'])
        return perm