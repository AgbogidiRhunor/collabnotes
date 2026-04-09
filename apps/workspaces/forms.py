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


class WorkspaceShareForm(forms.Form):
    role = forms.ChoiceField(
        choices=[('viewer', 'Viewer — can read notes'), ('editor', 'Editor — can add/edit notes')],
        widget=forms.Select(attrs={'class': 'select-input'}),
    )
    days = forms.IntegerField(
        min_value=1, max_value=30, initial=7,
        widget=forms.NumberInput(attrs={'class': 'input-field'}),
        label='Expires in (days)',
    )


class WorkspaceInviteForm(forms.Form):
    email = forms.EmailField(
        widget=forms.EmailInput(attrs={'placeholder': 'colleague@example.com'}),
        label='Invite by email',
    )
    role = forms.ChoiceField(
        choices=[('viewer', 'Viewer'), ('editor', 'Editor')],
        widget=forms.Select(attrs={'class': 'select-input'}),
    )