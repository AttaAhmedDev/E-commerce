from django.db import models


class TimeStampedModel(models.Model):
    """
    Abstract base model that adds self-updating created/updated timestamps.
    Every domain model in this project should inherit from this instead of
    models.Model directly, so we get consistent audit fields everywhere.
    """

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True
