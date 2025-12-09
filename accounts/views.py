from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.views import LoginView
from django.http import HttpResponseRedirect
from django.urls import reverse_lazy
from django.views.generic import TemplateView
from allauth.account.views import LogoutView

from .forms import EmailOrUsernameAuthenticationForm


class CustomLoginView(LoginView):
    template_name = "accounts/login.html"
    redirect_authenticated_user = True
    form_class = EmailOrUsernameAuthenticationForm

    def get_success_url(self):
        return self.get_redirect_url() or reverse_lazy("dashboard")


class DashboardView(LoginRequiredMixin, TemplateView):
    template_name = "accounts/dashboard.html"

    def get(self, request, *args, **kwargs):
        return HttpResponseRedirect(reverse_lazy("profiles:detail"))

class CustomLogoutView(LogoutView):
    def get_next_url(self):
        return reverse_lazy("login")

# Create your views here.
