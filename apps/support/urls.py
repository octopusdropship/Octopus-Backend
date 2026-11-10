from django.urls import path
from .views import SupportTicketListView, SupportTicketDetailView, SupportCallRequestView

urlpatterns = [
    path("tickets/", SupportTicketListView.as_view(), name="support_ticket_list"),
    path("tickets/<uuid:pk>/", SupportTicketDetailView.as_view(), name="support_ticket_detail"),
    path("call-requests/", SupportCallRequestView.as_view(), name="support_call_request"),
]
