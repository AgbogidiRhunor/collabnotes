from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout, get_user_model
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.views import View
from django.utils.decorators import method_decorator
from django.core.mail import send_mail
from django.conf import settings
from django.template.loader import render_to_string

from .forms import (
    RegisterForm, LoginForm,
    PasswordResetRequestForm, PasswordResetConfirmForm,
    EditProfileForm,
)
from .models import EmailVerificationToken, PasswordResetToken

User = get_user_model()


class RegisterView(View):
    template_name = 'accounts/register.html'

    def get(self, request):
        if request.user.is_authenticated:
            return redirect('notes:list')
        form = RegisterForm()
        return render(request, self.template_name, {'form': form})

    def post(self, request):
        if request.user.is_authenticated:
            return redirect('notes:list')
        form = RegisterForm(request.POST)
        if form.is_valid():
            user = form.save()
            # Send verification email
            token = EmailVerificationToken.create_for_user(user)
            self._send_verification_email(request, user, token)
            messages.success(
                request,
                'Account created! Please check your email to verify your account.'
            )
            return redirect('accounts:login')
        return render(request, self.template_name, {'form': form})

    def _send_verification_email(self, request, user, token):
        verify_url = (
            f"{settings.FRONTEND_URL}/accounts/verify-email/?token={token.token}"
        )
        html = render_to_string('emails/verify_email.html', {
            'user': user,
            'verify_url': verify_url,
        })
        send_mail(
            subject='Verify your CollabNotes email',
            message=f'Verify your email: {verify_url}',
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email],
            html_message=html,
            fail_silently=True,
        )


class LoginView(View):
    template_name = 'accounts/login.html'

    def get(self, request):
        if request.user.is_authenticated:
            return redirect('notes:list')
        form = LoginForm()
        return render(request, self.template_name, {'form': form})

    def post(self, request):
        if request.user.is_authenticated:
            return redirect('notes:list')
        form = LoginForm(request.POST)
        if form.is_valid():
            email = form.cleaned_data['email'].lower()
            password = form.cleaned_data['password']
            user = authenticate(request, username=email, password=password)

            if user is None:
                form.add_error(None, 'Invalid email or password.')
                return render(request, self.template_name, {'form': form})

            if not user.is_email_verified:
                form.add_error(None, 'Please verify your email before logging in.')
                return render(request, self.template_name, {'form': form})

            login(request, user)
            next_url = request.GET.get('next', settings.LOGIN_REDIRECT_URL)
            return redirect(next_url)

        return render(request, self.template_name, {'form': form})


class LogoutView(View):
    def post(self, request):
        logout(request)
        return redirect('accounts:login')


class VerifyEmailView(View):
    def get(self, request):
        token_str = request.GET.get('token', '').strip()
        if not token_str:
            messages.error(request, 'Missing verification token.')
            return redirect('accounts:login')

        try:
            token = EmailVerificationToken.objects.select_related('user').get(
                token=token_str
            )
        except EmailVerificationToken.DoesNotExist:
            messages.error(request, 'Invalid verification link.')
            return redirect('accounts:login')

        if not token.is_valid:
            messages.error(request, 'This verification link has expired or already been used.')
            return redirect('accounts:login')

        token.user.is_email_verified = True
        token.user.save(update_fields=['is_email_verified'])
        token.used = True
        token.save(update_fields=['used'])

        messages.success(request, 'Email verified! You can now log in.')
        return redirect('accounts:login')


class PasswordResetRequestView(View):
    template_name = 'accounts/password_reset.html'

    def get(self, request):
        form = PasswordResetRequestForm()
        return render(request, self.template_name, {'form': form, 'step': 'request'})

    def post(self, request):
        form = PasswordResetRequestForm(request.POST)
        if form.is_valid():
            email = form.cleaned_data['email'].lower()
            # Always show success to prevent email enumeration
            try:
                user = User.objects.get(email=email)
                token = PasswordResetToken.create_for_user(user)
                self._send_reset_email(user, token)
            except User.DoesNotExist:
                pass
            messages.success(
                request,
                'If that email is registered, you will receive a reset link shortly.'
            )
            return redirect('accounts:password_reset')
        return render(request, self.template_name, {'form': form, 'step': 'request'})

    def _send_reset_email(self, user, token):
        reset_url = f"{settings.FRONTEND_URL}/accounts/password-reset/confirm/?token={token.token}"
        html = render_to_string('emails/password_reset.html', {
            'user': user,
            'reset_url': reset_url,
        })
        send_mail(
            subject='Reset your CollabNotes password',
            message=f'Reset your password: {reset_url}',
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email],
            html_message=html,
            fail_silently=True,
        )


class PasswordResetConfirmView(View):
    template_name = 'accounts/password_reset.html'

    def get(self, request):
        token_str = request.GET.get('token', '').strip()
        if not token_str:
            messages.error(request, 'Missing reset token.')
            return redirect('accounts:password_reset')
        form = PasswordResetConfirmForm()
        return render(request, self.template_name, {
            'form': form, 'step': 'confirm', 'token': token_str
        })

    def post(self, request):
        token_str = request.POST.get('token', '').strip()
        form = PasswordResetConfirmForm(request.POST)
        if form.is_valid():
            try:
                token = PasswordResetToken.objects.select_related('user').get(
                    token=token_str
                )
            except PasswordResetToken.DoesNotExist:
                messages.error(request, 'Invalid reset link.')
                return redirect('accounts:password_reset')

            if not token.is_valid:
                messages.error(request, 'This reset link has expired or already been used.')
                return redirect('accounts:password_reset')

            token.consume()
            token.user.set_password(form.cleaned_data['new_password'])
            token.user.save()
            messages.success(request, 'Password reset successful. You can now log in.')
            return redirect('accounts:login')

        return render(request, self.template_name, {
            'form': form, 'step': 'confirm', 'token': token_str
        })


@method_decorator(login_required, name='dispatch')
class ProfileView(View):
    template_name = 'accounts/profile.html'

    def get(self, request):
        form = EditProfileForm(instance=request.user)
        return render(request, self.template_name, {'form': form})

    def post(self, request):
        form = EditProfileForm(request.POST, instance=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, 'Profile updated.')
            return redirect('accounts:profile')
        return render(request, self.template_name, {'form': form})
