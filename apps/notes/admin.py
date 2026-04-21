from django.contrib import admin
from .models import Note, NotePermission, NoteInvite, NoteVersion, ShareLink


@admin.register(Note)
class NoteAdmin(admin.ModelAdmin):
    list_display = ('title', 'creator', 'workspace', 'is_deleted', 'created_at', 'updated_at')
    list_filter = ('is_deleted',)
    search_fields = ('title', 'creator__email')
    readonly_fields = ('id', 'created_at', 'updated_at')


@admin.register(NotePermission)
class NotePermissionAdmin(admin.ModelAdmin):
    list_display = ('note', 'user', 'role', 'granted_by', 'created_at')
    list_filter = ('role',)
    search_fields = ('note__title', 'user__email')


@admin.register(NoteInvite)
class NoteInviteAdmin(admin.ModelAdmin):
    list_display = ('note', 'invited_user', 'invited_by', 'role', 'status', 'created_at')
    list_filter = ('status', 'role')
    search_fields = ('note__title', 'invited_user__email')
    readonly_fields = ('token',)


@admin.register(NoteVersion)
class NoteVersionAdmin(admin.ModelAdmin):
    list_display = ('note', 'saved_by', 'label', 'created_at')
    search_fields = ('note__title', 'saved_by__email')
    readonly_fields = ('id', 'created_at')


@admin.register(ShareLink)
class ShareLinkAdmin(admin.ModelAdmin):
    list_display = ('note', 'role', 'created_by', 'expires_at', 'is_active')
    list_filter = ('role', 'is_active')
    search_fields = ('note__title', 'created_by__email')
    readonly_fields = ('token',)