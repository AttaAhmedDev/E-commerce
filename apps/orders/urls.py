from django.urls import path
from .views import CheckoutView, OrderListView, OrderDetailView

app_name = "orders"

urlpatterns = [
    path("checkout/", CheckoutView.as_view(), name="checkout"),
    path("", OrderListView.as_view(), name="order-list"),
    # for get the order detail from the database use int:pk for RetrieveAPIView knows pk as default primary key
    path("<int:pk>/", OrderDetailView.as_view(), name="order-detail"),
]
