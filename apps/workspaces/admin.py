from django.contrib import admin
from .models import Workspace, WorkspacePermission, WorkspaceShareLink


@admin.register(Workspace)
class WorkspaceAdmin(admin.ModelAdmin):
    list_display = ('name', 'owner', 'is_deleted', 'created_at')
    list_filter = ('is_deleted',)
    search_fields = ('name', 'owner__email')
    readonly_fields = ('id', 'created_at', 'updated_at')


@admin.register(WorkspacePermission)
class WorkspacePermissionAdmin(admin.ModelAdmin):
    list_display = ('workspace', 'user', 'role', 'granted_by', 'created_at')
    list_filter = ('role',)
    search_fields = ('workspace__name', 'user__email')


@admin.register(WorkspaceShareLink)
class WorkspaceShareLinkAdmin(admin.ModelAdmin):
    list_display = ('workspace', 'role', 'created_by', 'expires_at', 'is_active')
    list_filter = ('role', 'is_active')
    readonly_fields = ('token',)