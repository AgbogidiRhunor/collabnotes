from django import forms
from .models import Note, ShareLink


class NoteForm(forms.ModelForm):
    """Used for create and edit."""
    class Meta:
        model = Note
        fields = ['title', 'content', 'workspace']
        widgets = {
            'title': forms.TextInput(attrs={
                'placeholder': 'Note title',
                'class': 'note-title-input',
                'autofocus': True,
            }),
            'content': forms.Textarea(attrs={
                'id': 'note-content',
                'class': 'note-content-input',
                'placeholder': 'Start writing…',
                'rows': 20,
            }),
            'workspace': forms.Select(attrs={'class': 'select-input'}),
        }

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['workspace'].required = False
        self.fields['workspace'].empty_label = '— No workspace —'
        if user:
            from apps.workspaces.models import Workspace
            self.fields['workspace'].queryset = Workspace.objects.filter(
                owner=user, is_deleted=False
            )
        # content is not required on creation
        self.fields['content'].required = False


class ShareLinkForm(forms.Form):
    role = forms.ChoiceField(
        choices=[('viewer', 'Viewer — can read'), ('editor', 'Editor — can edit')],
        initial='viewer',
        widget=forms.Select(attrs={'class': 'select-input'}),
    )
    days = forms.IntegerField(
        min_value=1,
        max_value=30,
        initial=7,
        widget=forms.NumberInput(attrs={'class': 'input-field'}),
        label='Expires in (days)',
    )


class InviteByEmailForm(forms.Form):
    email = forms.EmailField(
        widget=forms.EmailInput(attrs={'placeholder': 'colleague@example.com'}),
        label='Invite by email',
    )
    role = forms.ChoiceField(
        choices=[('viewer', 'Viewer'), ('editor', 'Editor')],
        widget=forms.Select(attrs={'class': 'select-input'}),
    )


class VersionLabelForm(forms.Form):
    label = forms.CharField(
        max_length=200,
        required=False,
        widget=forms.TextInput(attrs={'placeholder': 'Optional label (e.g. "Before big edit")'}),
    )
