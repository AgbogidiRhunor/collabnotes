from django import forms
from .models import Workspace


class WorkspaceForm(forms.ModelForm):
    class Meta:
        model = Workspace
        fields = ['name', 'description', 'color']
        widgets = {
            'name': forms.TextInput(attrs={'placeholder': 'Workspace name'}),
            'description': forms.Textarea(attrs={'rows': 3, 'placeholder': 'Optional description'}),
            'color': forms.TextInput(attrs={'type': 'color'}),
        }
