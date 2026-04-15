from django.urls import path
from . import views

app_name = 'accounts'

urlpatterns = [

    path('', views.LandingView.as_view(), name='landing_page'),

    path('register/', views.RegisterView.as_view(), name='register'),
    path('login/', views.LoginView.as_view(), name='login'),
    path('logout/', views.LogoutView.as_view(), name='logout'),
    path('verify-email/', views.VerifyEmailView.as_view(), name='verify_email'),
    path('password-reset/', views.PasswordResetRequestView.as_view(), name='password_reset'),
    path('password-reset/confirm/', views.PasswordResetConfirmView.as_view(), name='password_reset_confirm'),
    path('profile/', views.ProfileView.as_view(), name='profile'),
]
