from django import forms
from django.contrib.auth import authenticate, get_user_model
from django.contrib.auth.forms import AuthenticationForm, UsernameField
from django.utils.translation import gettext_lazy as _
from allauth.account.forms import SignupForm

from profiles.models import Profile

ROLE_CHOICES = [
    ("client", "Client (Looking for developers)"),
    ("developer", "Developer (Looking for projects)"),
]


class EmailOrUsernameAuthenticationForm(AuthenticationForm):
    username = UsernameField(
        label=_("Email or Username"),
        widget=forms.TextInput(attrs={"autofocus": True}),
    )

    def clean(self):
        username = self.cleaned_data.get("username")
        password = self.cleaned_data.get("password")

        if username and password:
            self.user_cache = authenticate(
                self.request, username=username, password=password
            )

            if self.user_cache is None:
                UserModel = get_user_model()
                try:
                    user_obj = UserModel.objects.get(email__iexact=username)
                    self.user_cache = authenticate(
                        self.request,
                        username=user_obj.get_username(),
                        password=password,
                    )
                except UserModel.DoesNotExist:
                    self.user_cache = None

            if self.user_cache is None:
                raise self.get_invalid_login_error()
            else:
                self.confirm_login_allowed(self.user_cache)

        return self.cleaned_data


class ConnectSignupForm(SignupForm):
    full_name = forms.CharField(
        label=_("Full Name"),
        max_length=150,
        widget=forms.TextInput(attrs={"placeholder": "John Doe"}),
    )
    role = forms.ChoiceField(
        label=_("I am a"),
        choices=ROLE_CHOICES,
        initial="client",
        widget=forms.RadioSelect,
    )

    def save(self, request):
        user = super().save(request)
        full_name = self.cleaned_data.get("full_name")
        role = self.cleaned_data.get("role")

        if full_name:
            user.first_name = full_name
            user.save(update_fields=["first_name"])

        Profile.objects.update_or_create(
            user=user,
            defaults={
                "headline": role.replace("_", " ").title() if role else "",
                "bio": "",
                "skills": [],
                "role": role or Profile.ROLE_DEVELOPER,
            },
        )
        return user

    def clean(self):
        cleaned_data = super().clean()
        password1 = cleaned_data.get("password1")
        password2 = cleaned_data.get("password2")

        if password1 and password2 and password1 != password2:
            raise forms.ValidationError(_("The two password fields didn't match."))

        return cleaned_data

    def clean_password2(self):
        password1 = self.cleaned_data.get("password1")
        password2 = self.cleaned_data.get("password2")
        if password1 and password2 and password1 != password2:
            raise forms.ValidationError(_("The two password fields didn't match."))
        return password2
