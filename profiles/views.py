import os

from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import redirect, render
from django.http import JsonResponse
from django.urls import reverse
from django.views import View
from django.contrib import messages

from django.db.models import Q
from datetime import date

from .forms import ProfileForm, ExperienceFormSet
from .models import Profile, Experience, Connection
from messaging.models import Conversation
from django.views.generic import TemplateView
from .paypal import verify_payment, TIER_PRICING


class ProfileDetailView(LoginRequiredMixin, View):
    template_name = "profiles/detail.html"

    def get(self, request):
        user = request.user
        profile, created = Profile.objects.get_or_create(
            user=user,
            defaults={
                "headline": "Full Stack Developer",
                "bio": "About yourself",
                "about": "About yourself",
                "location": "",
                "skills": ["React", "Node.js", "TypeScript", "PostgreSQL", "AWS"],
                "remaining_connections": 2,
            },
        )
        # Ensure remaining matches tier on first creation
        limit = profile.connection_limit
        if created and limit is not None:
            profile.remaining_connections = limit
            profile.last_connection_reset = date.today()
            profile.save(update_fields=["remaining_connections", "last_connection_reset"])
        else:
            profile.reset_daily_connections()
        experiences = profile.experiences.all()
        limit = profile.connection_limit
        remaining_display = "∞" if limit is None else f"{profile.remaining_connections}/{limit}"
        stats = {
            "connections": profile.active_connections,
            "remaining_today": remaining_display,
            "views": profile.views,
        }
        context = {
            "user": user,
            "profile": profile,
            "experiences": experiences,
            "stats": stats,
            "is_self": True,
        }
        return render(request, self.template_name, context)


class DiscoverView(LoginRequiredMixin, View):
    template_name = "profiles/discover.html"

    def get(self, request):
        user = request.user
        profile, created = Profile.objects.get_or_create(
            user=user,
            defaults={
                "headline": "Full Stack Developer",
                "bio": "About yourself",
                "about": "About yourself",
                "location": "",
                "skills": ["React", "Node.js", "TypeScript", "PostgreSQL", "AWS"],
                "remaining_connections": 2,
            },
        )
        limit = profile.connection_limit
        if created and limit is not None:
            profile.remaining_connections = limit
            profile.last_connection_reset = date.today()
            profile.save(update_fields=["remaining_connections", "last_connection_reset"])
        else:
            profile.reset_daily_connections()
        opposite_role = (
            Profile.ROLE_DEVELOPER if profile.role == Profile.ROLE_CLIENT else Profile.ROLE_CLIENT
        )
        others = (
            Profile.objects.filter(Q(role=opposite_role) | Q(role__isnull=True) | Q(role=""))
            .exclude(pk=profile.pk)
            .select_related("user")
        )
        query = request.GET.get("q", "").strip()
        if query:
            others = others.filter(
                Q(user__username__icontains=query)
                | Q(user__first_name__icontains=query)
                | Q(user__last_name__icontains=query)
                | Q(headline__icontains=query)
                | Q(location__icontains=query)
                | Q(skills__icontains=query)
            )
        connections = list(
            Connection.objects.filter(
                Q(requester=profile, status="accepted") | Q(receiver=profile, status="accepted")
            )
        )
        connections_profiles = [
            c.receiver if c.requester == profile else c.requester for c in connections
        ]
        popular_skills = ["React", "Node.js", "Python", "AWS", "TypeScript", "Docker"]
        limit = profile.connection_limit
        stats = {
            "daily_limit": limit if limit is not None else "∞",
            "remaining": profile.remaining_connections if limit is not None else "∞",
            "tier": profile.membership_tier,
        }
        # Connection statuses
        connection_map = {}
        for c in Connection.objects.filter(
            Q(requester=profile, receiver__in=others) | Q(receiver=profile, requester__in=others)
        ):
            key = c.receiver_id if c.requester == profile else c.requester_id
            if c.status == "accepted":
                connection_map[key] = "accepted"
            elif c.requester == profile:
                connection_map[key] = c.status
            else:
                connection_map[key] = "incoming-pending"
        context = {
            "profile": profile,
            "candidates": others,
            "connections": connections_profiles,
            "connection_map": connection_map,
            "popular_skills": popular_skills,
            "stats": stats,
            "discover_label": "Clients" if profile.role == Profile.ROLE_DEVELOPER else "Developers",
            "query": query,
        }
        return render(request, self.template_name, context)


class ConnectActionView(LoginRequiredMixin, View):
    def post(self, request, profile_id):
        me, _ = Profile.objects.get_or_create(user=request.user)
        me.reset_daily_connections()
        try:
            target = Profile.objects.get(pk=profile_id)
        except Profile.DoesNotExist:
            return redirect("profiles:discover")
        action = request.POST.get("action", "connect")
        if action == "connect":
            limit = me.connection_limit
            if limit is not None and me.remaining_connections <= 0:
                return redirect("profiles:discover")
            conn, created = Connection.objects.get_or_create(
                requester=me, receiver=target, defaults={"status": "pending"}
            )
            if created and limit is not None:
                me.remaining_connections = max(me.remaining_connections - 1, 0)
                me.save(update_fields=["remaining_connections"])
        elif action == "accept":
            try:
                conn = Connection.objects.get(requester=target, receiver=me)
                if conn.status != "accepted":
                    conn.status = "accepted"
                    conn.save(update_fields=["status"])
                    me.active_connections += 1
                    target.active_connections += 1
                    me.save(update_fields=["active_connections"])
                    target.save(update_fields=["active_connections"])
            except Connection.DoesNotExist:
                pass
        return redirect("profiles:discover")


class StartConversationView(LoginRequiredMixin, View):
    def _get_conversation(self, me, target):
        conv = (
            Conversation.objects.filter(participants=me)
            .filter(participants=target)
            .first()
        )
        if not conv:
            conv = Conversation.objects.create()
            conv.participants.add(me, target)
        return conv

    def get(self, request, profile_id):
        me, _ = Profile.objects.get_or_create(user=request.user)
        try:
            target = Profile.objects.get(pk=profile_id)
        except Profile.DoesNotExist:
            return redirect("profiles:discover")
        conv = self._get_conversation(me, target)
        return redirect(f"{reverse('messaging:inbox')}?conversation={conv.id}")

    def post(self, request, profile_id):
        return self.get(request, profile_id)


class ProfilePublicView(LoginRequiredMixin, View):
    template_name = "profiles/detail.html"

    def get(self, request, pk):
        try:
            profile = Profile.objects.select_related("user").get(pk=pk)
        except Profile.DoesNotExist:
            return redirect("profiles:discover")
        profile.views += 1
        profile.save(update_fields=["views"])
        experiences = profile.experiences.all()
        limit = profile.connection_limit
        remaining_display = "∞" if limit is None else f"{profile.remaining_connections}/{limit}"
        stats = {
            "connections": profile.active_connections,
            "remaining_today": remaining_display,
            "views": profile.views,
        }
        context = {
            "user": profile.user,
            "profile": profile,
            "experiences": experiences,
            "stats": stats,
            "is_self": False,
        }
        return render(request, self.template_name, context)


class ProfileEditView(LoginRequiredMixin, View):
    template_name = "profiles/edit.html"
    http_method_names = ["get", "post", "head", "options"]

    def get(self, request):
        profile, _ = Profile.objects.get_or_create(user=request.user)
        form = ProfileForm(instance=profile, user=request.user)
        exp_formset = ExperienceFormSet(queryset=profile.experiences.all())
        return render(
            request,
            self.template_name,
            {"form": form, "profile": profile, "exp_formset": exp_formset},
        )

    def post(self, request):
        profile, _ = Profile.objects.get_or_create(user=request.user)
        form = ProfileForm(
            request.POST, request.FILES, instance=profile, user=request.user
        )
        exp_formset = ExperienceFormSet(request.POST, queryset=profile.experiences.all())
        if form.is_valid() and exp_formset.is_valid():
            form.save(request.user)
            # Handle saves and deletions manually to respect delete flags and empties
            for f in exp_formset.forms:
                cd = f.cleaned_data
                if not cd:
                    continue
                # Delete flagged rows
                if cd.get("DELETE"):
                    inst = cd.get("id")
                    if inst:
                        inst.delete()
                    continue
                # Skip empties
                has_content = any(
                    cd.get(k)
                    for k in ["title", "company", "location", "start_date", "end_date", "description"]
                )
                if not has_content:
                    continue
                instance = f.save(commit=False)
                instance.profile = profile
                instance.save()
            return redirect(reverse("profiles:detail"))
        return render(
            request,
            self.template_name,
            {"form": form, "profile": profile, "exp_formset": exp_formset},
        )


class HomeView(TemplateView):
    template_name = "home.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        return ctx

    def post(self, request):
        profile, _ = Profile.objects.get_or_create(user=request.user)
        form = ProfileForm(
            request.POST, request.FILES, instance=profile, user=request.user
        )
        if form.is_valid():
            form.save(request.user)
            return redirect(reverse("profiles:detail"))
        return render(
            request,
            self.template_name,
            {"form": form, "profile": profile},
        )


class UpgradePlanView(LoginRequiredMixin, View):
    def post(self, request, tier):
        tier = tier.lower()
        if tier not in ["common", "plus", "pro"]:
            return redirect("profiles:detail")
        payment_token = request.POST.get("payment_token")
        if not verify_payment(payment_token, tier):
            messages.error(request, "Payment verification failed. Please complete payment and retry.")
            return redirect(reverse("profiles:checkout", args=[tier]))
        profile, _ = Profile.objects.get_or_create(user=request.user)
        # compute used connections under current plan
        current_limit = profile.connection_limit
        used = 0
        if current_limit is not None:
            used = max(current_limit - profile.remaining_connections, 0)

        profile.membership_tier = tier
        new_limit = profile.connection_limit
        if new_limit is not None:
            profile.remaining_connections = max(new_limit - used, 0)
        profile.last_connection_reset = date.today()
        profile.save(update_fields=["membership_tier", "remaining_connections", "last_connection_reset"])
        return redirect("profiles:detail")


class CheckoutView(LoginRequiredMixin, TemplateView):
    template_name = "billing/checkout.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        tier = self.kwargs.get("tier", "plus").lower()
        if tier not in ["common", "plus", "pro"]:
            tier = "plus"
        ctx["tier"] = tier
        ctx["tier_price"] = TIER_PRICING.get(tier, TIER_PRICING.get("plus"))
        ctx["paypal_client_id"] = os.getenv("PAYPAL_CLIENT_ID", "sb")
        return ctx


class ToggleShareView(LoginRequiredMixin, View):
    def post(self, request):
        profile, _ = Profile.objects.get_or_create(user=request.user)
        profile.share_enabled = not profile.share_enabled
        profile.save(update_fields=["share_enabled"])
        return redirect("profiles:detail")


class CheckShareView(LoginRequiredMixin, View):
    def get(self, request, pk):
        try:
            profile = Profile.objects.get(pk=pk)
        except Profile.DoesNotExist:
            return JsonResponse({"exists": False, "share_enabled": False})
        return JsonResponse(
            {
                "exists": True,
                "share_enabled": profile.share_enabled,
                "name": profile.user.get_full_name() or profile.user.username,
            }
        )
