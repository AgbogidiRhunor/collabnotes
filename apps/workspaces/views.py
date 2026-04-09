from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.shortcuts import render, redirect, get_object_or_404
from django.utils.decorators import method_decorator
from django.views import View

from .forms import WorkspaceForm, WorkspaceShareForm, WorkspaceInviteForm
from .models import Workspace, WorkspacePermission, WorkspaceShareLink

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
        # Owner always has full access
        try:
            ws = Workspace.objects.get(pk=pk, is_deleted=False)
        except Workspace.DoesNotExist:
            from django.http import Http404
            raise Http404

        if ws.owner == user:
            return ws, 'owner'

        # Check shared permission
        try:
            perm = WorkspacePermission.objects.get(workspace=ws, user=user)
            return ws, perm.role
        except WorkspacePermission.DoesNotExist:
            from django.http import Http404
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
        workspace = get_object_or_404(Workspace, pk=pk, owner=request.user, is_deleted=False)
        form = WorkspaceForm(instance=workspace)
        return render(request, self.template_name, {
            'form': form, 'workspace': workspace, 'action': 'Edit'
        })

    def post(self, request, pk):
        workspace = get_object_or_404(Workspace, pk=pk, owner=request.user, is_deleted=False)
        form = WorkspaceForm(request.POST, instance=workspace)
        if form.is_valid():
            form.save()
            messages.success(request, 'Workspace updated.')
            return redirect('workspaces:detail', pk=workspace.pk)
        return render(request, self.template_name, {
            'form': form, 'workspace': workspace, 'action': 'Edit'
        })


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
        return render(request, self.template_name, {
            'workspace': workspace,
            'share_form': WorkspaceShareForm(),
            'invite_form': WorkspaceInviteForm(),
            'links': links,
            'members': members,
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
                        WorkspacePermission.objects.update_or_create(
                            workspace=workspace,
                            user=invited,
                            defaults={'role': role, 'granted_by': request.user},
                        )
                        messages.success(request, f'{email} added as {role}.')
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