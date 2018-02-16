from django.views.generic.detail import DetailView
from django.views.generic.list import ListView

from . import models


class BaseListsView(ListView):
    context_object_name = "resource_lists"


class ReadingListsView(BaseListsView):
    model = models.ReadingList
    template_name = "resource_lists/reading_lists.html"


class VocabularyListsView(BaseListsView):
    model = models.VocabularyList
    template_name = "resource_lists/vocabulary_lists.html"


class BaseListDetailView(DetailView):
    pk_url_kwarg = "list_pk"
    context_object_name = "resource_list"


class ReadingListView(BaseListDetailView):
    model = models.ReadingList
    template_name = "resource_lists/reading_list.html"


class VocabularyListView(BaseListDetailView):
    model = models.VocabularyList
    template_name = "resource_lists/vocabulary_list.html"
