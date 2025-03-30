from django.urls import path
from .views import RegisterView, LoginView, VerifyTokenView, LogoutView
urlpatterns = [
    path("register/", RegisterView.as_view(), name="register"),
    path("login/", LoginView.as_view(), name="login"),
    path("verify/", VerifyTokenView.as_view(), name="verify"),
    path("logout/", LogoutView.as_view(), name="logout"),
]
