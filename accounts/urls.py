from django.urls import path, include

from .views import CustomLoginView, CustomLogoutView, DashboardView

urlpatterns = [
    path("", DashboardView.as_view(), name="dashboard"),
    path("login/", CustomLoginView.as_view(), name="login"),
    path("logout/", CustomLogoutView.as_view(), name="logout"),
    path("accounts/", include("allauth.urls")),
]
