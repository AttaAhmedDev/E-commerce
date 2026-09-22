from django.apps import AppConfig


class OrdersConfig(AppConfig):
    # for auto-incrementing primary key
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.orders"
