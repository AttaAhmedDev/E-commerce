from random import choice
from django.db import models
from apps.common.models import TimeStampedModel
from apps.orders.models import Order


# Payment Status Choices
class PaymentStatus(models.TextChoices):
    PENDING = "pending", "Pending"
    PAID = "paid", "Paid"
    FAILED = "failed", "Failed"


class Payment(TimeStampedModel):
    """
    One attempt to pay for an order through an online gateway. An order
    can have several (a declined card, then a retry), so each attempt
    is its own row, which gives an audit trail. Stores only the
    gateway's reference, never card data.
    """

    order = models.ForeignKey(Order, on_delete=models.PROTECT, related_name="payments")
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(
        max_length=10, choices=PaymentStatus.choices, default=PaymentStatus.PENDING
    )
    provider = models.CharField(max_length=20)
    provider_reference = models.CharField(max_length=100, null=True, blank=True)

    class Meta:
        db_table = "payments"
        ordering = ["-created_at"]
        constraints = [
            # Makes duplicate webhooks detectable: one row per gateway transaction.
            # NULLs are allowed to repeat, so not-yet-initiated payments don't collide.
            models.UniqueConstraint(
                fields=["provider", "provider_reference"],
                name="unique_provider_reference",
            ),
            # Only one in-flight payment per order, so two tabs can't start two payments.
            models.UniqueConstraint(
                fields=["order"],
                condition=models.Q(status="pending"),
                name="one_pending_payment_per_order",
            ),
            models.CheckConstraint(
                condition=models.Q(amount__gt=0), name="payment_amount_positive"
            ),
        ]

    # String representation of the model
    def __str__(self) -> str:
        return f"Payment #{self.id} for order #{self.order_id} ({self.status})"
