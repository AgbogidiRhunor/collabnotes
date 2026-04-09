from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password

User = get_user_model()


class RegisterForm(forms.ModelForm):
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={'placeholder': 'Min. 8 characters'}),
        label='Password',
    )
    password_confirm = forms.CharField(
        widget=forms.PasswordInput(attrs={'placeholder': 'Repeat password'}),
        label='Confirm password',
    )

    class Meta:
        model = User
        fields = ['display_name', 'email']
        widgets = {
            'display_name': forms.TextInput(attrs={'placeholder': 'Your full name'}),
            'email': forms.EmailInput(attrs={'placeholder': 'you@example.com'}),
        }

    def clean_email(self):
        email = self.cleaned_data['email'].lower().strip()
        if User.objects.filter(email=email).exists():
            # Generic message — do not reveal whether email exists
            raise forms.ValidationError('Unable to register with this email address.')
        return email

    def clean_password(self):
        password = self.cleaned_data.get('password')
        if password:
            validate_password(password)
        return password

    def clean(self):
        cleaned = super().clean()
        p1 = cleaned.get('password')
        p2 = cleaned.get('password_confirm')
        if p1 and p2 and p1 != p2:
            self.add_error('password_confirm', 'Passwords do not match.')
        return cleaned

    def save(self, commit=True):
        user = super().save(commit=False)
        user.set_password(self.cleaned_data['password'])
        user.is_email_verified = False
        if commit:
            user.save()
        return user


class LoginForm(forms.Form):
    email = forms.EmailField(
        widget=forms.EmailInput(attrs={'placeholder': 'you@example.com'}),
        label='Email',
    )
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={'placeholder': '••••••••'}),
        label='Password',
    )


class PasswordResetRequestForm(forms.Form):
    email = forms.EmailField(
        widget=forms.EmailInput(attrs={'placeholder': 'you@example.com'}),
        label='Email address',
    )


class PasswordResetConfirmForm(forms.Form):
    new_password = forms.CharField(
        widget=forms.PasswordInput(attrs={'placeholder': 'New password'}),
        label='New password',
    )
    new_password_confirm = forms.CharField(
        widget=forms.PasswordInput(attrs={'placeholder': 'Repeat new password'}),
        label='Confirm new password',
    )

    def clean_new_password(self):
        password = self.cleaned_data.get('new_password')
        if password:
            validate_password(password)
        return password

    def clean(self):
        cleaned = super().clean()
        p1 = cleaned.get('new_password')
        p2 = cleaned.get('new_password_confirm')
        if p1 and p2 and p1 != p2:
            self.add_error('new_password_confirm', 'Passwords do not match.')
        return cleaned


class EditProfileForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ['display_name']
        widgets = {
            'display_name': forms.TextInput(attrs={'placeholder': 'Your name'}),
        }
