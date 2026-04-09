from django.contrib import admin
from .models import Workspace


@admin.register(Workspace)
class WorkspaceAdmin(admin.ModelAdmin):
    list_display = ('name', 'owner', 'is_deleted', 'created_at')
    list_filter = ('is_deleted',)
    search_fields = ('name', 'owner__email')
    readonly_fields = ('id', 'created_at', 'updated_at')