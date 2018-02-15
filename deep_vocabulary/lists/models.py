import uuid

from django.conf import settings
from django.db import models


class AuditedModel(models.Model):
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class BaseList(models.Model):
    owner = models.ForeignKey(
        getattr(settings, "AUTH_USER_MODEL", "auth.User"),
        null=True,
        blank=True,
        on_delete=models.CASCADE
    )
    cloned_from = models.ForeignKey("self", null=True, on_delete=models.SET_NULL)
    title = models.CharField(max_length=255)
    description = models.TextField(null=True, blank=True)
    secret_key = models.UUIDField(editable=False, default=uuid.uuid4, unique=True)

    class Meta:
        abstract = True


class BaseListEntry(models.Model):
    note = models.TextField(null=True, blank=True)

    class Meta:
        abstract = True


class BaseSubscription(models.Model):
    subscriber = models.ForeignKey(
        getattr(settings, "AUTH_USER_MODEL", "auth.User"),
        null=True,
        blank=True,
        on_delete=models.CASCADE
    )

    class Meta:
        abstract = True


class ReadingList(AuditedModel, BaseList):
    class Meta:
        verbose_name = "reading list"


class VocabularyList(AuditedModel, BaseList):
    class Meta:
        verbose_name = "vocabulary list"


class ReadingListEntry(AuditedModel, BaseListEntry):
    resource_list = models.ForeignKey("lists.ReadingList", related_name="entries")
    cts_urn = models.CharField(max_length=250)

    class Meta:
        verbose_name = "reading list entry"
        verbose_name_plural = "reading list entries"


class VocabularyListEntry(AuditedModel, BaseListEntry):
    resource_list = models.ForeignKey("lists.VocabularyList", related_name="entries")

    class Meta:
        verbose_name = "vocabulary list entry"
        verbose_name_plural = "vocabulary list entries"


class ReadingListSubscription(AuditedModel, BaseSubscription):
    resource_list = models.ForeignKey(
        "lists.ReadingList", related_name="subscriptions"
    )

    class Meta:
        verbose_name = "reading list subscription"
        verbose_name_plural = "reading list subscriptions"


class VocabularyListSubscription(AuditedModel, BaseSubscription):
    resource_list = models.ForeignKey(
        "lists.VocabularyList", related_name="subscriptions"
    )

    class Meta:
        verbose_name = "vocabulary list subscription"
        verbose_name_plural = "vocabulary list subscriptions"
