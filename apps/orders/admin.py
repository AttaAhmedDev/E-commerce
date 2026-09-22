from django.contrib import admin
from .models import Order, OrderItem


# use TabularInline for show the order item in the order detail page
class OrderItemInLine(admin.TabularInline):
    model = OrderItem
    extra = 0
    readonly_fields = [
        "variant",
        "product_name",
        "variant_sku",
        "size",
        "color",
        "price",
        "quantity",
        "subtotal",
    ]


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ["id", "user", "status", "payment_method", "total", "created_at"]
    list_filter = ["status", "payment_method"]
    search_fields = ["user__email", "id"]
    inlines = [OrderItemInLine]
    readonly_fields = ["user", "subtotal", "shipping_cost", "total", "payment_method"]
