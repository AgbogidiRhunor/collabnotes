from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.core.mail import send_mail
from django.conf import settings
from django.shortcuts import render, redirect, get_object_or_404
from django.template.loader import render_to_string
from django.utils.decorators import method_decorator
from django.views import View

from .forms import WorkspaceForm, WorkspaceShareForm, WorkspaceInviteForm
from .models import Workspace, WorkspacePermission, WorkspaceInvite, WorkspaceShareLink

User = get_user_model()


@method_decorator(login_required, name='dispatch')
class WorkspaceListView(View):
    template_name = 'workspaces/list.html'

    def get(self, request):
        owned = Workspace.objects.filter(owner=request.user, is_deleted=False)
        shared_perms = (
            WorkspacePermission.objects
            .filter(user=request.user, workspace__is_deleted=False)
            .select_related('workspace', 'workspace__owner')
        )
        return render(request, self.template_name, {
            'owned_workspaces': owned,
            'shared_perms': shared_perms,
        })


@method_decorator(login_required, name='dispatch')
class WorkspaceDetailView(View):
    template_name = 'workspaces/detail.html'

    def _get_workspace_and_role(self, pk, user):
        from django.http import Http404
        try:
            ws = Workspace.objects.get(pk=pk, is_deleted=False)
        except Workspace.DoesNotExist:
            raise Http404

        if ws.owner == user:
            return ws, 'owner'

        try:
            perm = WorkspacePermission.objects.get(workspace=ws, user=user)
            return ws, perm.role
        except WorkspacePermission.DoesNotExist:
            raise Http404

    def get(self, request, pk):
        workspace, role = self._get_workspace_and_role(pk, request.user)
        notes = workspace.notes.filter(is_deleted=False).order_by('-updated_at')
        return render(request, self.template_name, {
            'workspace': workspace,
            'notes': notes,
            'role': role,
            'is_owner': role == 'owner',
            'is_shared': workspace.owner != request.user,
        })


@method_decorator(login_required, name='dispatch')
class WorkspaceCreateView(View):
    template_name = 'workspaces/form.html'

    def get(self, request):
        form = WorkspaceForm()
        return render(request, self.template_name, {'form': form, 'action': 'Create'})

    def post(self, request):
        form = WorkspaceForm(request.POST)
        if form.is_valid():
            workspace = form.save(commit=False)
            workspace.owner = request.user
            workspace.save()
            messages.success(request, f'Workspace "{workspace.name}" created.')
            return redirect('workspaces:detail', pk=workspace.pk)
        return render(request, self.template_name, {'form': form, 'action': 'Create'})


@method_decorator(login_required, name='dispatch')
class WorkspaceEditView(View):
    template_name = 'workspaces/form.html'

    def get(self, request, pk):
        # Feature 4: only owner can rename
        workspace = get_object_or_404(Workspace, pk=pk, owner=request.user, is_deleted=False)
        form = WorkspaceForm(instance=workspace)
        return render(request, self.template_name, {'form': form, 'workspace': workspace, 'action': 'Edit'})

    def post(self, request, pk):
        workspace = get_object_or_404(Workspace, pk=pk, owner=request.user, is_deleted=False)
        form = WorkspaceForm(request.POST, instance=workspace)
        if form.is_valid():
            form.save()
            messages.success(request, 'Workspace updated.')
            return redirect('workspaces:detail', pk=workspace.pk)
        return render(request, self.template_name, {'form': form, 'workspace': workspace, 'action': 'Edit'})


@method_decorator(login_required, name='dispatch')
class WorkspaceDeleteView(View):
    def post(self, request, pk):
        workspace = get_object_or_404(Workspace, pk=pk, owner=request.user, is_deleted=False)
        workspace.is_deleted = True
        workspace.save(update_fields=['is_deleted'])
        messages.success(request, f'Workspace "{workspace.name}" deleted.')
        return redirect('workspaces:list')


@method_decorator(login_required, name='dispatch')
class WorkspaceShareView(View):
    template_name = 'workspaces/share.html'

    def get(self, request, pk):
        workspace = get_object_or_404(Workspace, pk=pk, owner=request.user, is_deleted=False)
        links = workspace.share_links.filter(is_active=True).order_by('-created_at')
        members = workspace.permissions.select_related('user').order_by('created_at')
        pending_invites = workspace.invites.filter(status='pending').select_related('invited_user')
        return render(request, self.template_name, {
            'workspace': workspace,
            'share_form': WorkspaceShareForm(),
            'invite_form': WorkspaceInviteForm(),
            'links': links,
            'members': members,
            'pending_invites': pending_invites,
        })

    def post(self, request, pk):
        workspace = get_object_or_404(Workspace, pk=pk, owner=request.user, is_deleted=False)
        action = request.POST.get('action')

        if action == 'create_link':
            form = WorkspaceShareForm(request.POST)
            if form.is_valid():
                WorkspaceShareLink.create(
                    workspace=workspace,
                    created_by=request.user,
                    role=form.cleaned_data['role'],
                    days=form.cleaned_data['days'],
                )
                messages.success(request, 'Share link created.')
            return redirect('workspaces:share', pk=pk)

        elif action == 'invite_email':
            form = WorkspaceInviteForm(request.POST)
            if form.is_valid():
                email = form.cleaned_data['email'].lower()
                role = form.cleaned_data['role']
                try:
                    invited = User.objects.get(email=email)
                    if invited == request.user:
                        messages.error(request, 'You cannot invite yourself.')
                    else:
                        invite = WorkspaceInvite.create(
                            workspace=workspace,
                            invited_by=request.user,
                            invited_user=invited,
                            role=role,
                        )
                        self._send_invite_email(request, workspace, invite, invited, role)
                        messages.success(request, f'Invitation sent to {email}.')
                except User.DoesNotExist:
                    messages.error(request, 'No account found with that email.')
            return redirect('workspaces:share', pk=pk)

        elif action == 'remove_member':
            user_id = request.POST.get('user_id')
            WorkspacePermission.objects.filter(workspace=workspace, user_id=user_id).delete()
            messages.success(request, 'Member removed.')
            return redirect('workspaces:share', pk=pk)

        elif action == 'change_role':
            user_id = request.POST.get('user_id')
            new_role = request.POST.get('role')
            if new_role in ('editor', 'viewer'):
                WorkspacePermission.objects.filter(
                    workspace=workspace, user_id=user_id
                ).update(role=new_role)
            return redirect('workspaces:share', pk=pk)

        elif action == 'revoke_link':
            link_id = request.POST.get('link_id')
            WorkspaceShareLink.objects.filter(id=link_id, workspace=workspace).update(is_active=False)
            messages.success(request, 'Link revoked.')
            return redirect('workspaces:share', pk=pk)

        return redirect('workspaces:share', pk=pk)

    def _send_invite_email(self, request, workspace, invite, invited_user, role):
        accept_url = request.build_absolute_uri(f'/workspaces/invite/{invite.token}/accept/')
        decline_url = request.build_absolute_uri(f'/workspaces/invite/{invite.token}/decline/')
        html = render_to_string('emails/workspace_invite.html', {
            'workspace': workspace,
            'invited_by': request.user,
            'invited_user': invited_user,
            'role': role,
            'accept_url': accept_url,
            'decline_url': decline_url,
        })
        send_mail(
            subject=f'{request.user.display_name} invited you to a workspace on CollabNotes',
            message=f'You have been invited to "{workspace.name}". Accept: {accept_url}',
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[invited_user.email],
            html_message=html,
            fail_silently=True,
        )


@method_decorator(login_required, name='dispatch')
class WorkspaceInviteRespondView(View):
    def get(self, request, token, action):
        try:
            invite = WorkspaceInvite.objects.select_related('workspace', 'invited_by').get(
                token=token,
                invited_user=request.user,
                status='pending',
            )
        except WorkspaceInvite.DoesNotExist:
            messages.error(request, 'This invitation is invalid or has already been responded to.')
            return redirect('workspaces:list')

        if action == 'accept':
            invite.accept()
            messages.success(request, f'You now have access to "{invite.workspace.name}".')
            return redirect('workspaces:detail', pk=invite.workspace.pk)
        elif action == 'decline':
            invite.decline()
            messages.info(request, f'You declined the invitation to "{invite.workspace.name}".')
            return redirect('workspaces:list')

        return redirect('workspaces:list')


@method_decorator(login_required, name='dispatch')
class WorkspaceJoinView(View):
    def get(self, request, token):
        try:
            link = WorkspaceShareLink.objects.select_related('workspace').get(token=token)
        except WorkspaceShareLink.DoesNotExist:
            messages.error(request, 'Invalid share link.')
            return redirect('workspaces:list')

        if not link.is_valid:
            messages.error(request, 'This share link has expired or been revoked.')
            return redirect('workspaces:list')

        if link.workspace.is_deleted:
            messages.error(request, 'This workspace is no longer available.')
            return redirect('workspaces:list')

        if link.workspace.owner == request.user:
            messages.info(request, 'You already own this workspace.')
            return redirect('workspaces:detail', pk=link.workspace.pk)

        link.accept(request.user)
        messages.success(request, f'You now have access to "{link.workspace.name}".')
        return redirect('workspaces:detail', pk=link.workspace.pk)