from django.utils import timezone
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.generics import get_object_or_404

from apps.authentication.permissions import IsMerchantAuthenticated
from .models import Notification
from .serializers import NotificationSerializer


class NotificationListView(APIView):
    permission_classes = [IsMerchantAuthenticated]

    def get(self, request):
        notifications = Notification.objects.filter(
            merchant=request.user.merchant
        ).order_by("-created_at")[:50]
        return Response(NotificationSerializer(notifications, many=True).data)


class NotificationMarkReadView(APIView):
    permission_classes = [IsMerchantAuthenticated]

    def patch(self, request, pk):
        notification = get_object_or_404(
            Notification, pk=pk, merchant=request.user.merchant
        )
        notification.is_read = True
        notification.read_at = timezone.now()
        notification.save(update_fields=["is_read", "read_at"])
        return Response({"detail": "Marked as read."})
