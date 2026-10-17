from django.urls import path

from .views import PayView, WebhookView

app_name = "payments"

urlpatterns = [
    path("orders/<int:pk>/pay/", PayView.as_view(), name="order-pay"),
    path("payments/webhook/<str:provider>/", WebhookView.as_view(), name="webhook"),
]
