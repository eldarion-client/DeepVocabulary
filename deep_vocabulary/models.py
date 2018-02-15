from collections import OrderedDict, deque
from io import StringIO

from django.db import connection, models

from .db.fields import ArrayField
from .greeklit import TEXT_GROUPS, WORKS
from .querysets import PassageLemmaQuerySet
from .utils import (
    chunker,
    natural_sort_key,
    pg_array_format,
    sort_key,
    strip_accents
)


class Lemma(models.Model):

    text = models.CharField(max_length=100, unique=True)

    unaccented = models.CharField(max_length=100)
    sort_key = models.TextField()

    corpus_count = models.IntegerField(default=0)
    core_count = models.IntegerField(default=0)

    class Meta:
        indexes = [
            models.Index(fields=["unaccented"]),
            models.Index(fields=["sort_key"]),
        ]

    def frequencies(self):  # @@@ might remove this and just do in views
        corpus_total, core_total = calc_overall_counts()

        # per 10k
        corpus_freq = round(10000 * self.corpus_count / corpus_total, 1)
        core_freq = round(10000 * self.core_count / core_total, 1)

        return corpus_freq, core_freq

    def calc_counts(self):
        corpus_count = self.passages.all(
        ).aggregate(
            models.Sum("count")
        )["count__sum"]
        if corpus_count is not None:
            self.corpus_count = corpus_count

        core_count = self.passages.filter(
            text_edition__is_core=True
        ).aggregate(
            models.Sum("count")
        )["count__sum"]
        if core_count is not None:
            self.core_count = core_count

        self.save()

    def calc_unaccented(self):
        self.unaccented = strip_accents(self.text).lower()
        if self.unaccented[-1] in "12345":
            self.unaccented = self.unaccented[:-1]
        self.save()

    def calc_sort_key(self):
        self.sort_key = sort_key(self.text)
        self.save()


class Definition(models.Model):

    lemma = models.ForeignKey(Lemma, related_name="definitions")
    shortdef = models.TextField()
    source = models.CharField(max_length=100)


class TextEdition(models.Model):
    cts_urn = models.CharField(max_length=250, unique=True)
    is_core = models.BooleanField(default=False)
    token_count = models.IntegerField(default=0)

    def text_group_urn(self):
        parts = self.cts_urn.split(":")
        return ":".join(parts[0:3]) + ":" + parts[3].split(".")[0]

    def text_group_label(self):
        return TEXT_GROUPS.get(self.text_group_urn(), "unknown")

    def work_label(self):
        parts = self.cts_urn.split(":")
        work_urn = ":".join(parts[0:3]) + ":" + ".".join(parts[3].split(".")[0:2])
        return WORKS.get(work_urn, "unknown")

    def calc_counts(self):
        self.token_count = self.passage_lemmas.all(
        ).aggregate(
            models.Sum("count")
        )["count__sum"]

        self.save()


class PassageLemma(models.Model):

    text_edition = models.ForeignKey(TextEdition, related_name="passage_lemmas")
    reference = models.CharField(max_length=100)
    lemma = models.ForeignKey(Lemma, related_name="passages")
    count = models.IntegerField()

    # reference hierarchy up to four deep
    ref1 = ArrayField(models.CharField(max_length=60), default=list)
    ref2 = ArrayField(models.CharField(max_length=60), default=list)
    ref3 = ArrayField(models.CharField(max_length=60), default=list)
    ref4 = ArrayField(models.CharField(max_length=60), default=list)

    objects = PassageLemmaQuerySet.as_manager()

    def cts_urn(self):
        return f"{self.text_edition.cts_urn}:{self.reference}"


def import_data(edition_filename, dictionary_filename, passage_lemmas_filename, source):
    editions_by_id = {}
    count = 0
    with open(edition_filename) as f:
        for line in f:
            edition_id, cts_urn = line.strip().split("|")
            text_edition, _ = TextEdition.objects.get_or_create(cts_urn=cts_urn)
            editions_by_id[edition_id] = text_edition
            count += 1
    print(f"{count} editions")
    lemmas_by_text = {}
    lemmas_by_id = {}
    count = 0
    with open(dictionary_filename) as f:
        for chunk in chunker(f.readlines(), 200):
            definitions = deque()
            for line in chunk:
                lemma_id, lemma_text, shortdef = line.strip().split("|")
                if lemma_text not in lemmas_by_text:
                    lemma = Lemma.objects.create(text=lemma_text)
                else:
                    lemma = lemmas_by_text[lemma_text]
                definitions.append(
                    Definition(
                        lemma=lemma,
                        shortdef=shortdef,
                        source=source,
                    )
                )
                lemmas_by_id[lemma_id] = lemma
                count += 1
            Definition.objects.bulk_create(definitions)
            definitions.clear()
    print(f"{count} lemmas")
    count1 = 0
    count2 = 0
    with open(passage_lemmas_filename) as f:
        buf = StringIO()
        for line in f:
            passage, lemma_list = line.strip().split("|")
            edition_id, passage_ref = passage.split(":")
            for lemma_count in lemma_list.split():
                if "." in lemma_count:
                    lemma_id, lcount = lemma_count.split(".")
                    lcount = int(lcount)
                else:
                    lemma_id = lemma_count
                    lcount = 1
                row = OrderedDict()
                row["text_edition_id"] = editions_by_id[edition_id].id
                row["reference"] = passage_ref
                row["lemma_id"] = lemmas_by_id[lemma_id].id
                row["count"] = lcount
                ref_sort_key = natural_sort_key(passage_ref, depth=4)
                row["ref1"] = pg_array_format(ref_sort_key[0])
                row["ref2"] = pg_array_format(ref_sort_key[1])
                row["ref3"] = pg_array_format(ref_sort_key[2])
                row["ref4"] = pg_array_format(ref_sort_key[3])
                buf.write("\t".join([str(v) for v in row.values()]) + "\n")
                count2 += 1
            count1 += 1
        buf.seek(0)
        with connection.cursor() as cursor:
            cursor.copy_from(buf, "deep_vocabulary_passagelemma", columns=row.keys())
    print(f"{count1} passages; {count2} passage lemmas")


def mark_core(filename):
    with open(filename) as f:
        for line in f:
            text_editions = TextEdition.objects.filter(
                cts_urn__startswith=line.strip())
            if len(text_editions) == 0:
                print("couldn't find:", line.strip())
            else:
                text_edition = text_editions[0]
                text_edition.is_core = True
                text_edition.save()


def update_lemma_counts():
    qs = Lemma.objects.annotate(pc=models.Sum("passages__count"))
    with connection.cursor() as cursor:
        sql, params = qs.query.sql_with_params()
        cursor.execute("""
            WITH qs AS ({})
            UPDATE deep_vocabulary_lemma SET corpus_count = COALESCE(qs.pc, 0)
            FROM qs WHERE qs.id = deep_vocabulary_lemma.id
        """.format(sql), params)

    qs = Lemma.objects.filter(passages__text_edition__is_core=True).annotate(pc=models.Sum("passages__count"))
    with connection.cursor() as cursor:
        sql, params = qs.query.sql_with_params()
        cursor.execute("""
            WITH qs AS ({})
            UPDATE deep_vocabulary_lemma SET core_count = COALESCE(qs.pc, 0)
            FROM qs WHERE qs.id = deep_vocabulary_lemma.id
        """.format(sql), params)


def update_edition_token_counts():
    for edition in TextEdition.objects.all():
        edition.calc_counts()


def update_lemma_unaccented():
    for lemma in Lemma.objects.iterator():
        lemma.calc_unaccented()


def update_lemma_sort_keys():
    for lemma in Lemma.objects.iterator():
        lemma.calc_sort_key()


CORPUS_COUNT = None
CORE_COUNT = None


def calc_overall_counts():
    global CORPUS_COUNT, CORE_COUNT

    if not CORPUS_COUNT:
        CORPUS_COUNT = PassageLemma.objects.all().aggregate(
            models.Sum("count")
        )["count__sum"]

    if not CORE_COUNT:
        CORE_COUNT = PassageLemma.objects.filter(
            text_edition__is_core=True
        ).aggregate(
            models.Sum("count")
        )["count__sum"]

    return CORPUS_COUNT, CORE_COUNT
