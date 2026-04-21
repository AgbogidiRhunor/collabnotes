import bleach
from django.conf import settings
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.core.mail import send_mail
from django.db import transaction
from django.http import JsonResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.template.loader import render_to_string
from django.utils.decorators import method_decorator
from django.contrib.auth.decorators import login_required
from django.views import View

from .forms import NoteForm, ShareLinkForm, InviteByEmailForm, VersionLabelForm
from .models import Note, NotePermission, NoteInvite, NoteVersion, ShareLink

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
    Returns (note, perm) or raises Http404.
    Also grants access if the user has workspace-level permission for the note's workspace.
    """
    from django.http import Http404
    rank = {'owner': 3, 'editor': 2, 'viewer': 1}

    # Check direct NotePermission first
    try:
        perm = NotePermission.objects.select_related('note').get(
            note_id=note_id,
            user=user,
            note__is_deleted=False,
        )
        if rank.get(perm.role, 0) >= rank[required_role]:
            return perm.note, perm
        raise Http404
    except NotePermission.DoesNotExist:
        pass

    # Feature 3: check workspace-level access
    # If the note belongs to a workspace and the user has workspace permission,
    # synthesise a viewer perm (or editor if workspace role is editor)
    try:
        note = Note.objects.get(pk=note_id, is_deleted=False)
    except Note.DoesNotExist:
        raise Http404

    if note.workspace_id:
        from apps.workspaces.models import WorkspacePermission
        try:
            ws_perm = WorkspacePermission.objects.get(
                workspace_id=note.workspace_id,
                user=user,
            )
            # Synthesise: workspace viewers get note-viewer, workspace editors get note-viewer
            # (they need explicit NotePermission to edit — feature 3 spec)
            synthetic_role = 'viewer'
            if rank.get(synthetic_role, 0) >= rank[required_role]:
                # Create a temporary unsaved perm object to return
                perm = NotePermission(note=note, user=user, role=synthetic_role)
                return note, perm
        except WorkspacePermission.DoesNotExist:
            pass

    raise Http404


# Note List 
@method_decorator(login_required, name='dispatch')
class NoteListView(View):
    template_name = 'notes/list.html'

    def get(self, request):
        permissions = (
            NotePermission.objects
            .filter(user=request.user, note__is_deleted=False)
            .select_related('note', 'note__workspace', 'note__creator')
            .order_by('-note__updated_at')
        )

        notes_with_role = [
            {'note': p.note, 'role': p.role, 'can_edit': p.can_edit}
            for p in permissions
        ]

        # Pending invites for dashboard display
        pending_note_invites = (
            NoteInvite.objects
            .filter(invited_user=request.user, status='pending')
            .select_related('note', 'invited_by')
            .order_by('-created_at')
        )

        from apps.workspaces.models import WorkspaceInvite
        pending_workspace_invites = (
            WorkspaceInvite.objects
            .filter(invited_user=request.user, status='pending')
            .select_related('workspace', 'invited_by')
            .order_by('-created_at')
        )

        return render(request, self.template_name, {
            'notes_with_role': notes_with_role,
            'pending_note_invites': pending_note_invites,
            'pending_workspace_invites': pending_workspace_invites,
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
        collaborators = (
            NotePermission.objects
            .filter(note=note)
            .select_related('user')
            .order_by('created_at')
        )
        # Last 10 versions for inline history panel
        versions = note.versions.select_related('saved_by').all()[:10]

        can_edit = perm.can_edit
        can_manage = perm.can_manage

        return render(request, self.template_name, {
            'note': note,
            'perm': perm,
            'can_edit': can_edit,
            'can_manage': can_manage,
            # Feature 4: only owner can rename
            'can_rename': can_manage,
            'collaborators': collaborators,
            'versions': versions,
            'owner': note.creator,
            'is_shared': note.creator != request.user,
        })

    def post(self, request, pk):
        note, perm = get_note_for_user(pk, request.user, required_role='editor')

        content = sanitize(request.POST.get('content', ''))
        workspace_id = request.POST.get('workspace') or None

        # Feature 4: only owner can change the title
        if perm.can_manage:
            title = request.POST.get('title', '').strip()[:500]
            note.title = title or 'Untitled Note'

        note.content = content
        if workspace_id:
            note.workspace_id = workspace_id
        note.save(update_fields=['title', 'content', 'workspace_id', 'updated_at'])

        NoteVersion.objects.create(
            note=note,
            title_snapshot=note.title,
            content_snapshot=note.content,
            saved_by=request.user,
        )
        messages.success(request, 'Note saved.')
        return redirect('notes:detail', pk=note.pk)


# Note Delete 
@method_decorator(login_required, name='dispatch')
class NoteDeleteView(View):
    template_name = 'notes/confirm_delete.html'

    def get(self, request, pk):
        note, perm = get_note_for_user(pk, request.user, required_role='owner')
        return render(request, self.template_name, {'note': note})

    def post(self, request, pk):
        note, perm = get_note_for_user(pk, request.user, required_role='owner')
        title = note.title
        note.delete()
        messages.success(request, f'"{title}" has been permanently deleted.')
        return redirect('notes:list')


# Inline Version History (replaces separate history page) 
@method_decorator(login_required, name='dispatch')
class NoteVersionsView(View):
    """Returns last 10 versions as JSON for the inline history panel."""

    def get(self, request, pk):
        note, perm = get_note_for_user(pk, request.user, required_role='viewer')
        versions = list(
            note.versions
            .select_related('saved_by')
            .values('id', 'title_snapshot', 'label', 'created_at', 'saved_by__display_name')
            [:10]
        )
        # Format dates for display
        from django.utils.timesince import timesince
        for v in versions:
            v['id'] = str(v['id'])
            v['time_ago'] = timesince(v['created_at']) + ' ago'
            v['created_at'] = v['created_at'].strftime('%b %d, %Y %H:%M')
        return JsonResponse({'versions': versions})


@method_decorator(login_required, name='dispatch')
class NoteRestoreVersionView(View):
    def post(self, request, pk, version_pk):
        note, perm = get_note_for_user(pk, request.user, required_role='editor')
        version = get_object_or_404(NoteVersion, pk=version_pk, note=note)

        with transaction.atomic():
            NoteVersion.objects.create(
                note=note,
                title_snapshot=note.title,
                content_snapshot=note.content,
                saved_by=request.user,
                label=f'Auto-saved before restore',
            )
            if perm.can_manage:
                note.title = version.title_snapshot
            note.content = version.content_snapshot
            note.save(update_fields=['title', 'content', 'updated_at'])

        messages.success(request, 'Note restored.')
        return redirect('notes:detail', pk=note.pk)


# Share
@method_decorator(login_required, name='dispatch')
class NoteShareView(View):
    template_name = 'notes/share.html'

    def get(self, request, pk):
        note, perm = get_note_for_user(pk, request.user, required_role='owner')
        share_form = ShareLinkForm()
        invite_form = InviteByEmailForm()
        links = note.share_links.filter(is_active=True).order_by('-created_at')
        collaborators = note.permissions.select_related('user').order_by('created_at')
        pending_invites = note.invites.filter(status='pending').select_related('invited_user')
        return render(request, self.template_name, {
            'note': note,
            'perm': perm,
            'share_form': share_form,
            'invite_form': invite_form,
            'links': links,
            'collaborators': collaborators,
            'pending_invites': pending_invites,
        })

    def post(self, request, pk):
        note, perm = get_note_for_user(pk, request.user, required_role='owner')
        action = request.POST.get('action')

        if action == 'create_link':
            share_form = ShareLinkForm(request.POST)
            if share_form.is_valid():
                ShareLink.create(
                    note=note,
                    created_by=request.user,
                    role=share_form.cleaned_data['role'],
                    days=share_form.cleaned_data['days'],
                )
                messages.success(request, 'Share link created.')
            return redirect('notes:share', pk=note.pk)

        elif action == 'invite_email':
            invite_form = InviteByEmailForm(request.POST)
            if invite_form.is_valid():
                email = invite_form.cleaned_data['email'].lower()
                role = invite_form.cleaned_data['role']
                try:
                    invited_user = User.objects.get(email=email)
                    if invited_user == request.user:
                        messages.error(request, 'You cannot invite yourself.')
                    else:
                        invite = NoteInvite.create(
                            note=note,
                            invited_by=request.user,
                            invited_user=invited_user,
                            role=role,
                        )
                        self._send_invite_email(request, note, invite, invited_user, role)
                        messages.success(request, f'Invitation sent to {email}.')
                except User.DoesNotExist:
                    messages.error(request, 'No account found with that email.')
            return redirect('notes:share', pk=note.pk)

        elif action == 'revoke_link':
            link_id = request.POST.get('link_id')
            ShareLink.objects.filter(id=link_id, note=note).update(is_active=False)
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

        return redirect('notes:share', pk=note.pk)

    def _send_invite_email(self, request, note, invite, invited_user, role):
        accept_url = request.build_absolute_uri(f'/notes/invite/{invite.token}/accept/')
        decline_url = request.build_absolute_uri(f'/notes/invite/{invite.token}/decline/')
        html = render_to_string('emails/note_invite.html', {
            'note': note,
            'invited_by': request.user,
            'invited_user': invited_user,
            'role': role,
            'accept_url': accept_url,
            'decline_url': decline_url,
        })
        send_mail(
            subject=f'{request.user.display_name} invited you to a note on CollabNotes',
            message=f'You have been invited to "{note.title}". Accept: {accept_url}',
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[invited_user.email],
            html_message=html,
            fail_silently=True,
        )


# Invite accept/decline 
@method_decorator(login_required, name='dispatch')
class NoteInviteRespondView(View):
    def get(self, request, token, action):
        try:
            invite = NoteInvite.objects.select_related('note', 'invited_by').get(
                token=token,
                invited_user=request.user,
                status='pending',
            )
        except NoteInvite.DoesNotExist:
            messages.error(request, 'This invitation is invalid or has already been responded to.')
            return redirect('notes:list')

        if action == 'accept':
            invite.accept()
            messages.success(request, f'You now have access to "{invite.note.title}".')
            return redirect('notes:detail', pk=invite.note.pk)
        elif action == 'decline':
            invite.decline()
            messages.info(request, f'You declined the invitation to "{invite.note.title}".')
            return redirect('notes:list')

        return redirect('notes:list')


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