from django.conf import settings
from django.conf.urls import include, url
from django.conf.urls.static import static
from django.views.generic import TemplateView

from django.contrib import admin

from .views import lemma_list, lemma_detail, word_list, editions_list, reader_redirect


urlpatterns = [
    url(r"^$", TemplateView.as_view(template_name="homepage.html"), name="home"),
    url(r"^admin/", include(admin.site.urls)),
    # url(r"^account/", include("account.urls")),

    url(r"^lemma/$", lemma_list, name="lemma_list"),
    url(r"^lemma/(?P<pk>\d+)/$", lemma_detail, name="lemma_detail"),

    url(r"^editions/$", editions_list, name="editions_list"),
    url(r"^word-list/(?P<cts_urn>[^/]+)/$", word_list, name="word_list"),
    url(r"^word-list/(?P<cts_urn>[^/]+)/(?P<response_format>json)/$", word_list, name="word_list_json"),

    url(r"^rr/(?P<cts_urn>[^/]+)/$", reader_redirect, name="reader_redirect"),

    url(r"^resource-lists/", include("deep_vocabulary.resource_lists.urls")),
]

urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
