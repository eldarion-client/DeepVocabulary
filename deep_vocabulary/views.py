from operator import itemgetter
from urllib.parse import urlencode

from django.core.paginator import EmptyPage, PageNotAnInteger, Paginator, Page
from django.core.urlresolvers import reverse
from django.db.models import Q, Sum
from django.http import JsonResponse, Http404
from django.shortcuts import get_object_or_404, redirect, render

from .models import (Definition, Lemma, PassageLemma, TextEdition,
                     calc_overall_counts)
from .querysets import Q_by_ref
from .utils import encode_link_header, strip_accents


def lemma_list(request):

    query = request.GET.get("q")
    order = request.GET.get("o")
    mincore = request.GET.get("mincore")
    maxcore = request.GET.get("maxcore")
    page = request.GET.get("page")

    if mincore:
        try:
            mincore = float(mincore)
        except ValueError:
            mincore = None
    if maxcore:
        try:
            maxcore = float(maxcore)
        except ValueError:
            maxcore = None

    if query:
        query = strip_accents(query).lower()
        if query.startswith("*"):
            lemma_list = Lemma.objects.filter(unaccented__endswith=query[1:])
        elif query.endswith("*"):
            lemma_list = Lemma.objects.filter(unaccented__startswith=query[:-1])
        else:
            lemma_list = Lemma.objects.filter(Q(unaccented=query)|(Q(definitions__shortdef__icontains=query)))
    else:
        lemma_list = Lemma.objects

    corpus_total, core_total = calc_overall_counts()

    if mincore:
        lemma_list = lemma_list.filter(core_count__gte=mincore * core_total / 10000)
    if maxcore:
        lemma_list = lemma_list.filter(core_count__lte=maxcore * core_total / 10000)

    lemma_list = lemma_list.order_by({
        "1": "-core_count",
        "2": "-corpus_count",
        "3": "sort_key",
    }.get(order, "-core_count"))

    paginator = Paginator(lemma_list, 20)

    try:
        lemmas = paginator.page(page)
    except PageNotAnInteger:
        lemmas = paginator.page(1)
    except EmptyPage:
        lemmas = paginator.page(paginator.num_pages)

    return render(request, "deep_vocabulary/lemma_list.html", {
        "lemmas": lemmas,
    })


def editions_list(request):
    core = "core" in request.GET

    if core:
        editions = TextEdition.objects.filter(is_core=True).order_by("cts_urn")
    else:
        editions = TextEdition.objects.order_by("cts_urn")

    text_groups = {}

    for edition in editions:
        text_groups.setdefault(
            (edition.text_group_urn(), edition.text_group_label()), []
        ).append(edition)

    return render(request, "deep_vocabulary/editions_list.html", {
        "text_groups": text_groups,
        "core": core,
    })


def lemma_detail(request, pk):
    lemma = get_object_or_404(Lemma, pk=pk)
    filt = request.GET.get("filter")

    if filt:
        passages = lemma.passages.filter(text_edition__cts_urn=filt).select_related().order_by_ref()
        filtered_edition = TextEdition.objects.filter(cts_urn=filt).first()
    else:
        passages = lemma.passages.all()
        filtered_edition = None

    lemma_counts_per_edition = dict(
        lemma.passages.values_list("text_edition").annotate(total=Sum("count")),
    )

    corpus_freq, core_freq = lemma.frequencies()

    editions = [
        {
            "text_edition": text_edition,
            "lemma_count": lemma_counts_per_edition[text_edition.pk],
            "frequency": round(10000 * lemma_counts_per_edition[text_edition.pk] / text_edition.token_count, 1),
            "ratio": (
                (10000 * lemma_counts_per_edition[text_edition.pk] / text_edition.token_count) / core_freq
            ) if core_freq != 0 else None,
        }
        for text_edition in TextEdition.objects.filter(
            pk__in=lemma_counts_per_edition.keys()
        )
    ]
    text_groups = {}
    for edition in editions:
        text_group_key = (edition["text_edition"].text_group_urn(), edition["text_edition"].text_group_label())
        text_groups.setdefault(text_group_key, []).append(edition)

    return render(request, "deep_vocabulary/lemma_detail.html", {
        "object": lemma,
        "filter": filt,
        "filtered_edition": filtered_edition,
        "editions_count": len(editions),
        "text_groups": text_groups,
        "passages": passages,
        "corpus_freq": corpus_freq,
        "core_freq": core_freq,
    })


def word_list(request, cts_urn, response_format="html"):

    # @@@ could use library for this but this will do for now
    parts = cts_urn.split(":")
    if len(parts) == 5:
        edition_urn = ":".join(parts[:4])
        ref = parts[4]
    else:
        edition_urn = cts_urn
        ref = None

    if "reference" in request.GET:
        if request.GET.get("reference"):
            cts_urn = edition_urn + ":" + request.GET.get("reference")
        else:
            cts_urn = edition_urn
        return redirect("word_list", cts_urn=cts_urn)

    text_edition = get_object_or_404(TextEdition, cts_urn=edition_urn)

    order = request.GET.get("o")
    mincore = request.GET.get("mincore")
    maxcore = request.GET.get("maxcore")
    page = request.GET.get("page")

    corpus_total, core_total = calc_overall_counts()

    min_core_count = 0
    if mincore:
        try:
            mincore = float(mincore)
            min_core_count = mincore * core_total / 10000
        except ValueError:
            mincore = None
    max_core_count = 10000000
    if maxcore:
        try:
            maxcore = float(maxcore)
            max_core_count = maxcore * core_total / 10000
        except ValueError:
            maxcore = None

    if ref:
        if "-" in ref:
            start, end = ref.split("-")
            ref_filter = Q_by_ref(start, "gte") & Q_by_ref(end, "lte")
        else:
            ref_filter = Q_by_ref(ref)
    else:
        ref_filter = Q()

    passage_lemmas = dict(
        PassageLemma.objects.filter(
            Q(text_edition=text_edition),
            ref_filter,
        ).values_list("lemma").annotate(total=Sum("count"))
    )
    definitions = dict(
        Definition.objects.filter(
            source="logeion_002",
            lemma__in=passage_lemmas.keys()
        ).values_list(
            "lemma_id",
            "shortdef"
        ),
    )
    lemma_values_list = Lemma.objects.filter(
        pk__in=passage_lemmas.keys()
    ).values_list(
        "pk", "text", "corpus_count", "core_count", "sort_key",
    )
    lemma_data = {item[0]: item[1:] for item in lemma_values_list}
    total = sum(passage_lemmas.values())
    corpus_total, core_total = calc_overall_counts()

    if order == "3":  # text (by sort_key)
        sort_key = itemgetter("sort_key")
        sort_reverse = False
    elif order == "4":  # log ratio descending
        sort_key = lambda x: x["ratio"] if x["ratio"] else 1  # noqa: E731
        sort_reverse = True
    elif order == "5":  # log ratio ascending
        sort_key = lambda x: x["ratio"] if x["ratio"] else 1  # noqa: E731
        sort_reverse = False
    else:  # usually "1" but also default: count descending
        sort_key = itemgetter("count")
        sort_reverse = True

    vocabulary = sorted(
        [
            {
                "lemma_id": lemma_id,
                "lemma_text": lemma_data[lemma_id][0],
                "sort_key": lemma_data[lemma_id][3],
                "shortdef": definitions[lemma_id],
                "count": passage_lemmas[lemma_id],
                "frequency": round(10000 * passage_lemmas[lemma_id] / total, 1),
                "corpus_frequency": round(10000 * lemma_data[lemma_id][1] / corpus_total, 3),
                "core_frequency": round(10000 * lemma_data[lemma_id][2] / core_total, 2),
                "ratio": (
                    (passage_lemmas[lemma_id] / total) / (lemma_data[lemma_id][2] / core_total)
                ) if (not ref and lemma_data[lemma_id][2] != 0 and passage_lemmas[lemma_id] > 1) else None,
            }
            for lemma_id in passage_lemmas.keys()
            if min_core_count <= lemma_data[lemma_id][2] <= max_core_count
        ],
        key=sort_key,
        reverse=sort_reverse,
    )

    lemma_count = len(vocabulary)

    if page == "all":
        lemmas = vocabulary
    else:
        paginator = Paginator(vocabulary, 20)

        try:
            lemmas = paginator.page(page)
        except PageNotAnInteger:
            lemmas = paginator.page(1)
        except EmptyPage:
            lemmas = paginator.page(paginator.num_pages)

    # lemmas = vocabulary

    if response_format == "html":
        return render(request, "deep_vocabulary/word_list.html", {
            "cts_urn": cts_urn,
            "text_edition": text_edition,
            "ref": ref,
            "lemmas": lemmas,
            "lemma_count": lemma_count,
            "token_total": total,
        })

    if response_format == "json":
        data = {
            "text_edition": {
                "cts_urn": text_edition.cts_urn,
                "is_core": text_edition.is_core,
            },
            "ref": ref,
            "lemmas": list(lemmas),
            "lemma_count": lemma_count,
            "token_total": total,
        }
        links = {}
        if isinstance(lemmas, Page):
            self_url = request.build_absolute_uri(reverse(
                "word_list_json",
                kwargs=dict(
                    cts_urn=cts_urn,
                    response_format=response_format
                )
            ))
            if lemmas.has_previous():
                params = urlencode({**request.GET.dict(), "page": lemmas.previous_page_number()})
                links["prev"] = {
                    "target": f"{self_url}?{params}",
                }
            if lemmas.has_next():
                params = urlencode({**request.GET.dict(), "page": lemmas.next_page_number()})
                links["next"] = {
                    "target": f"{self_url}?{params}",
                }
        response = JsonResponse(data)
        if links:
            response["Link"] = encode_link_header(links)
        return response


def reader_redirect(request, cts_urn):
    SCAIFE_HOST = "https://lk353.eu1.eldarioncloud.com"
    if len(cts_urn.split(":")) == 4:
        return redirect(f"{SCAIFE_HOST}/library/{cts_urn}/")
    elif len(cts_urn.split(":")) == 5:
        return redirect(f"{SCAIFE_HOST}/reader/{cts_urn}/")
    else:
        raise Http404()
