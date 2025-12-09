from django import forms
from datetime import date

from django.forms import modelformset_factory
from .models import Profile, Experience


class ProfileForm(forms.ModelForm):
    first_name = forms.CharField(label="First name", max_length=150, required=False)
    last_name = forms.CharField(label="Last name", max_length=150, required=False)
    skills_text = forms.CharField(
        label="Skills",
        required=False,
        help_text="Comma separated (e.g. React, Node.js, PostgreSQL)",
    )

    class Meta:
        model = Profile
        fields = [
            "headline",
            "about",
            "location",
            "profile_picture",
            "role",
            "membership_tier",
        ]
        widgets = {
            "about": forms.Textarea(attrs={"rows": 3}),
            "profile_picture": forms.FileInput(attrs={"class": "file-input"}),
        }

    def __init__(self, *args, **kwargs):
        user = kwargs.pop("user", None)
        super().__init__(*args, **kwargs)
        self._initial_tier = self.instance.membership_tier
        if user:
            self.fields["first_name"].initial = user.first_name
            self.fields["last_name"].initial = user.last_name
        self.fields["headline"].label = "Developer Role"
        skills = ""
        if self.instance and self.instance.skills:
            skills = ", ".join(self.instance.skills)
        self.fields["skills_text"].initial = skills
        self.fields["role"].label = "Role"
        self.fields["role"].disabled = True
        self.fields["role"].required = False
        self.fields["role"].widget.attrs.update({"class": "select-input"})
        self.fields["membership_tier"].label = "Membership Plan"
        self.fields["membership_tier"].disabled = True
        self.fields["membership_tier"].required = False
        self.fields["membership_tier"].widget.attrs.update({"class": "select-input"})

    def save(self, user, commit=True):
        profile = super().save(commit=False)
        limit_before = profile.connection_limit
        skills_raw = self.cleaned_data.get("skills_text", "")
        profile.skills = [s.strip() for s in skills_raw.split(",") if s.strip()]
        # Reset remaining to limit if tier changed and has a numeric cap
        new_limit = profile.connection_limit
        if self._initial_tier != profile.membership_tier:
            if new_limit is not None:
                used = 0
                if limit_before is not None:
                    used = max(limit_before - profile.remaining_connections, 0)
                profile.remaining_connections = max(new_limit - used, 0)
                profile.last_connection_reset = date.today()
            else:
                # Pro tier: remaining not enforced
                profile.remaining_connections = profile.remaining_connections
        if commit:
            profile.save()
        user.first_name = self.cleaned_data.get("first_name", user.first_name)
        user.last_name = self.cleaned_data.get("last_name", user.last_name)
        user.save(update_fields=["first_name", "last_name"])
        return profile


class ExperienceForm(forms.ModelForm):
    class Meta:
        model = Experience
        fields = ["title", "company", "location", "start_date", "end_date", "is_current", "description"]
        widgets = {
            "start_date": forms.DateInput(attrs={"type": "date"}),
            "end_date": forms.DateInput(attrs={"type": "date"}),
            "is_current": forms.CheckboxInput(),
            "description": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["title"].required = False
        for field in ["company", "location", "start_date", "end_date", "description"]:
            self.fields[field].required = False

    def clean(self):
        cleaned = super().clean()
        if not any(
            cleaned.get(f)
            for f in ["title", "company", "start_date", "end_date", "description"]
        ):
            return cleaned
        if not cleaned.get("title"):
            self.add_error("title", "Title is required.")
        start = cleaned.get("start_date")
        end = cleaned.get("end_date")
        if start and end and end < start:
            self.add_error("end_date", "End date cannot be before start date.")
        if cleaned.get("is_current"):
            cleaned["end_date"] = None
        return cleaned


ExperienceFormSet = modelformset_factory(
    Experience,
    form=ExperienceForm,
    extra=0,
    can_delete=True,
)
