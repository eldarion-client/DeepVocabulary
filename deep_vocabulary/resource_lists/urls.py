from django.conf.urls import url

from . import views


urlpatterns = [
    url(r"^reading/$", views.ReadingListsView, name="reading_lists"),
    url(r"^vocabulary/$", views.VocabularyListsView, name="vocabulary_lists"),
    url(r"^reading/(?P<pk>\d+)/$", views.ReadingListView, name="reading_list"),
    url(r"^vocabulary/(?P<pk>\d+)/$", views.VocabularyListView, name="vocabulary_list"),
]
