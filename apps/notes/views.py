import bleach
from django.conf import settings
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.shortcuts import render, redirect, get_object_or_404
from django.utils.decorators import method_decorator
from django.views import View

from .forms import NoteForm, ShareLinkForm, InviteByEmailForm, VersionLabelForm
from .models import Note, NotePermission, NoteVersion, ShareLink

User = get_user_model()


def sanitize(html):
    return bleach.clean(
        html or '',
        tags=settings.BLEACH_ALLOWED_TAGS,
        attributes=settings.BLEACH_ALLOWED_ATTRIBUTES,
        strip=True,
    )


def get_note_for_user(note_id, user, required_role='viewer'):
    """
    Fetch a note and verify the user holds at least required_role.
    Returns (note, permission).
    Raises 404 for missing notes AND for notes the user cannot see — prevents IDOR.
    """
    rank = {'owner': 3, 'editor': 2, 'viewer': 1}
    try:
        perm = NotePermission.objects.select_related('note').get(
            note_id=note_id,
            user=user,
            note__is_deleted=False,
        )
    except NotePermission.DoesNotExist:
        from django.http import Http404
        raise Http404

    if rank.get(perm.role, 0) < rank[required_role]:
        from django.http import Http404
        raise Http404

    return perm.note, perm


# Note List 
@method_decorator(login_required, name='dispatch')
class NoteListView(View):
    template_name = 'notes/list.html'

    def get(self, request):
        # All notes the user has any permission on
        permissions = (
            NotePermission.objects
            .filter(user=request.user, note__is_deleted=False)
            .select_related('note', 'note__workspace')
            .order_by('-note__updated_at')
        )
        workspace_filter = request.GET.get('workspace')
        if workspace_filter:
            permissions = permissions.filter(note__workspace_id=workspace_filter)

        notes_with_role = [
            {'note': p.note, 'role': p.role, 'can_edit': p.can_edit}
            for p in permissions
        ]

        from apps.workspaces.models import Workspace
        workspaces = Workspace.objects.filter(owner=request.user, is_deleted=False)

        return render(request, self.template_name, {
            'notes_with_role': notes_with_role,
            'workspaces': workspaces,
            'active_workspace': workspace_filter,
        })


# Note Create 
@method_decorator(login_required, name='dispatch')
class NoteCreateView(View):
    template_name = 'notes/create.html'

    def get(self, request):
        workspace_id = request.GET.get('workspace')
        initial = {'workspace': workspace_id} if workspace_id else {}
        form = NoteForm(user=request.user, initial=initial)
        return render(request, self.template_name, {'form': form})

    def post(self, request):
        form = NoteForm(request.POST, user=request.user)
        if form.is_valid():
            with transaction.atomic():
                note = form.save(commit=False)
                note.creator = request.user
                note.content = sanitize(note.content)
                note.save()
                NotePermission.objects.create(
                    note=note,
                    user=request.user,
                    role=NotePermission.Role.OWNER,
                    granted_by=request.user,
                )
                NoteVersion.objects.create(
                    note=note,
                    title_snapshot=note.title,
                    content_snapshot=note.content,
                    saved_by=request.user,
                    label='Initial version',
                )
            return redirect('notes:detail', pk=note.pk)
        return render(request, self.template_name, {'form': form})



# Note Detail / Editor 
@method_decorator(login_required, name='dispatch')
class NoteDetailView(View):
    template_name = 'notes/detail.html'

    def get(self, request, pk):
        note, perm = get_note_for_user(pk, request.user, required_role='viewer')
        form = NoteForm(instance=note, user=request.user)
        collaborators = (
            NotePermission.objects
            .filter(note=note)
            .select_related('user')
            .order_by('created_at')
        )
        return render(request, self.template_name, {
            'note': note,
            'perm': perm,
            'form': form,
            'collaborators': collaborators,
            'owner': note.creator,
            'is_shared': note.creator != request.user,
        })

    def post(self, request, pk):
        note, perm = get_note_for_user(pk, request.user, required_role='editor')
        form = NoteForm(request.POST, instance=note, user=request.user)
        if form.is_valid():
            updated_note = form.save(commit=False)
            updated_note.content = sanitize(updated_note.content)
            updated_note.save()
            # Save a version snapshot
            NoteVersion.objects.create(
                note=updated_note,
                title_snapshot=updated_note.title,
                content_snapshot=updated_note.content,
                saved_by=request.user,
            )
            messages.success(request, 'Note saved.')
            return redirect('notes:detail', pk=note.pk)

        collaborators = (
            NotePermission.objects
            .filter(note=note)
            .select_related('user')
        )
        return render(request, self.template_name, {
            'note': note,
            'perm': perm,
            'form': form,
            'collaborators': collaborators,
        })


# Note Delete 
@method_decorator(login_required, name='dispatch')
class NoteDeleteView(View):
    template_name = 'notes/confirm_delete.html'

    def get(self, request, pk):
        note, perm = get_note_for_user(pk, request.user, required_role='owner')
        return render(request, self.template_name, {'note': note})

    def post(self, request, pk):
        note, perm = get_note_for_user(pk, request.user, required_role='owner')
        note.delete()
        messages.success(request, f'"{note.title}" has been permanently deleted.')
        return redirect('notes:list')


# Version History
@method_decorator(login_required, name='dispatch')
class NoteHistoryView(View):
    template_name = 'notes/history.html'

    def get(self, request, pk):
        note, perm = get_note_for_user(pk, request.user, required_role='viewer')
        versions = note.versions.select_related('saved_by').all()
        return render(request, self.template_name, {
            'note': note,
            'perm': perm,
            'versions': versions,
        })


@method_decorator(login_required, name='dispatch')
class NoteRestoreVersionView(View):
    def post(self, request, pk, version_pk):
        note, perm = get_note_for_user(pk, request.user, required_role='editor')
        version = get_object_or_404(NoteVersion, pk=version_pk, note=note)

        with transaction.atomic():
            # Snapshot current state before overwriting
            NoteVersion.objects.create(
                note=note,
                title_snapshot=note.title,
                content_snapshot=note.content,
                saved_by=request.user,
                label=f'Auto-saved before restore to "{version.label or version.created_at:%Y-%m-%d %H:%M}"',
            )
            note.title = version.title_snapshot
            note.content = version.content_snapshot
            note.save(update_fields=['title', 'content', 'updated_at'])

        messages.success(request, 'Note restored to selected version.')
        return redirect('notes:detail', pk=note.pk)


# Save Version (manual snapshot)
@method_decorator(login_required, name='dispatch')
class SaveVersionView(View):
    def post(self, request, pk):
        note, perm = get_note_for_user(pk, request.user, required_role='editor')
        form = VersionLabelForm(request.POST)
        if form.is_valid():
            NoteVersion.objects.create(
                note=note,
                title_snapshot=note.title,
                content_snapshot=note.content,
                saved_by=request.user,
                label=form.cleaned_data['label'],
            )
            messages.success(request, 'Version saved.')
        return redirect('notes:history', pk=note.pk)


# Share: create link 
@method_decorator(login_required, name='dispatch')
class NoteShareView(View):
    template_name = 'notes/share.html'

    def get(self, request, pk):
        note, perm = get_note_for_user(pk, request.user, required_role='owner')
        share_form = ShareLinkForm()
        invite_form = InviteByEmailForm()
        links = note.share_links.filter(is_active=True).order_by('-created_at')
        collaborators = (
            note.permissions.select_related('user').order_by('created_at')
        )
        return render(request, self.template_name, {
            'note': note,
            'perm': perm,
            'share_form': share_form,
            'invite_form': invite_form,
            'links': links,
            'collaborators': collaborators,
        })

    def post(self, request, pk):
        note, perm = get_note_for_user(pk, request.user, required_role='owner')
        action = request.POST.get('action')

        if action == 'create_link':
            share_form = ShareLinkForm(request.POST)
            invite_form = InviteByEmailForm()
            if share_form.is_valid():
                link = ShareLink.create(
                    note=note,
                    created_by=request.user,
                    role=share_form.cleaned_data['role'],
                    days=share_form.cleaned_data['days'],
                )
                messages.success(
                    request,
                    f'Share link created. Copy it from below.'
                )
                return redirect('notes:share', pk=note.pk)

        elif action == 'invite_email':
            share_form = ShareLinkForm()
            invite_form = InviteByEmailForm(request.POST)
            if invite_form.is_valid():
                email = invite_form.cleaned_data['email'].lower()
                role = invite_form.cleaned_data['role']
                try:
                    invited_user = User.objects.get(email=email)
                    NotePermission.objects.update_or_create(
                        note=note,
                        user=invited_user,
                        defaults={'role': role, 'granted_by': request.user},
                    )
                    messages.success(request, f'{email} added as {role}.')
                except User.DoesNotExist:
                    messages.error(request, 'No account found with that email.')
                return redirect('notes:share', pk=note.pk)

        elif action == 'revoke_link':
            link_id = request.POST.get('link_id')
            ShareLink.objects.filter(
                id=link_id, note=note
            ).update(is_active=False)
            messages.success(request, 'Link revoked.')
            return redirect('notes:share', pk=note.pk)

        elif action == 'remove_collaborator':
            user_id = request.POST.get('user_id')
            if str(user_id) != str(request.user.id):
                NotePermission.objects.filter(
                    note=note, user_id=user_id
                ).exclude(role='owner').delete()
                messages.success(request, 'Collaborator removed.')
            return redirect('notes:share', pk=note.pk)

        elif action == 'change_role':
            user_id = request.POST.get('user_id')
            new_role = request.POST.get('role')
            if new_role in ('editor', 'viewer') and str(user_id) != str(request.user.id):
                NotePermission.objects.filter(
                    note=note, user_id=user_id
                ).exclude(role='owner').update(role=new_role)
                messages.success(request, 'Role updated.')
            return redirect('notes:share', pk=note.pk)

        # Re-render with errors
        links = note.share_links.filter(is_active=True).order_by('-created_at')
        collaborators = note.permissions.select_related('user').order_by('created_at')
        return render(request, self.template_name, {
            'note': note,
            'perm': perm,
            'share_form': share_form,
            'invite_form': invite_form,
            'links': links,
            'collaborators': collaborators,
        })


# Join via share link 
@method_decorator(login_required, name='dispatch')
class JoinNoteView(View):
    def get(self, request, token):
        try:
            link = ShareLink.objects.select_related('note').get(token=token)
        except ShareLink.DoesNotExist:
            messages.error(request, 'Invalid share link.')
            return redirect('notes:list')

        if not link.is_valid:
            messages.error(request, 'This share link has expired or been revoked.')
            return redirect('notes:list')

        if link.note.is_deleted:
            messages.error(request, 'This note is no longer available.')
            return redirect('notes:list')

        link.accept(request.user)
        messages.success(request, f'You now have access to "{link.note.title}".')
        return redirect('notes:detail', pk=link.note.pk)