from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect, get_object_or_404
from django.utils.decorators import method_decorator
from django.views import View

from .forms import WorkspaceForm
from .models import Workspace


@method_decorator(login_required, name='dispatch')
class WorkspaceListView(View):
    template_name = 'workspaces/list.html'

    def get(self, request):
        workspaces = Workspace.objects.filter(owner=request.user, is_deleted=False)
        return render(request, self.template_name, {'workspaces': workspaces})


@method_decorator(login_required, name='dispatch')
class WorkspaceDetailView(View):
    template_name = 'workspaces/detail.html'

    def get(self, request, pk):
        workspace = get_object_or_404(Workspace, pk=pk, owner=request.user, is_deleted=False)
        notes = workspace.notes.filter(is_deleted=False).order_by('-updated_at')
        return render(request, self.template_name, {
            'workspace': workspace,
            'notes': notes,
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

    def get_workspace(self, pk, user):
        return get_object_or_404(Workspace, pk=pk, owner=user, is_deleted=False)

    def get(self, request, pk):
        workspace = self.get_workspace(pk, request.user)
        form = WorkspaceForm(instance=workspace)
        return render(request, self.template_name, {
            'form': form, 'workspace': workspace, 'action': 'Edit'
        })

    def post(self, request, pk):
        workspace = self.get_workspace(pk, request.user)
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