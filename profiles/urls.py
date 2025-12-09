from django.urls import path

from .views import (
    ProfileDetailView,
    ProfileEditView,
    DiscoverView,
    ConnectActionView,
    ProfilePublicView,
    StartConversationView,
    UpgradePlanView,
    CheckoutView,
    ToggleShareView,
    CheckShareView,
)

app_name = "profiles"

urlpatterns = [
    path("", ProfileDetailView.as_view(), name="detail"),
    path("edit/", ProfileEditView.as_view(), name="edit"),
    path("discover/", DiscoverView.as_view(), name="discover"),
    path("discover/connect/<int:profile_id>/", ConnectActionView.as_view(), name="connect_action"),
    path("discover/message/<int:profile_id>/", StartConversationView.as_view(), name="start_message"),
    path("view/<int:pk>/", ProfilePublicView.as_view(), name="public"),
    path("upgrade/<str:tier>/", UpgradePlanView.as_view(), name="upgrade_plan"),
    path("checkout/<str:tier>/", CheckoutView.as_view(), name="checkout"),
    path("toggle-share/", ToggleShareView.as_view(), name="toggle_share"),
    path("check-share/<int:pk>/", CheckShareView.as_view(), name="check_share"),
]
