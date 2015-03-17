from unittest import mock
from unittest import TestCase

from rest_framework.test import APITestCase, APIRequestFactory
from rest_framework.exceptions import ParseError

from mongoengine import Document, fields
from rest_framework_mongoengine.serializers import DocumentSerializer

from ..testing import DatasetTesting

from ..paginating import Range, Paginator

class RangeTests(TestCase):
    def test_init_skip(self):
        r = Range(3)
        self.assertEqual(r.first, 3)
        self.assertEqual(r.last, None)
        self.assertEqual(r.count, None)

    def test_init_range(self):
        r = Range(3, 7)
        self.assertEqual(r.first, 3)
        self.assertEqual(r.last, 7)
        self.assertEqual(r.count, 5)

    def test_init_limit(self):
        r = Range(3, count=5)
        self.assertEqual(r.first, 3)
        self.assertEqual(r.last, 7)
        self.assertEqual(r.count, 5)

    def test_init_tail(self):
        r = Range(-3)
        self.assertEqual(r.first, -3)
        self.assertEqual(r.last, None)
        self.assertEqual(r.count, None)

    def test_init_total(self):
        r = Range(total=20)
        self.assertEqual(r.first, None)
        self.assertEqual(r.last, None)
        self.assertEqual(r.count, None)
        self.assertEqual(r.total, 20)

    def test_normalize(self):
        r = Range(3,7).normalize(20)
        self.assertEqual(r.first, 3)
        self.assertEqual(r.last, 7)
        self.assertEqual(r.count, 5)
        self.assertEqual(r.total, 20)

    def test_normalize_limited(self):
        r = Range(3,7).normalize(20,10)
        self.assertEqual(r.first, 3)
        self.assertEqual(r.last, 7)
        self.assertEqual(r.count, 5)
        self.assertEqual(r.total, 20)

    def test_normalize_skip(self):
        r = Range(3).normalize(20)
        self.assertEqual(r.first, 3)
        self.assertEqual(r.last, 19)
        self.assertEqual(r.count, 17)
        self.assertEqual(r.total, 20)

    def test_normalize_skip_limited(self):
        r = Range(3).normalize(20, 10)
        self.assertEqual(r.first, 3)
        self.assertEqual(r.last, 12)
        self.assertEqual(r.count, 10)
        self.assertEqual(r.total, 20)

    def test_normalize_tail(self):
        r = Range(-3).normalize(20)
        self.assertEqual(r.first, 17)
        self.assertEqual(r.last, 19)
        self.assertEqual(r.count, 3)
        self.assertEqual(r.total, 20)

    def test_normalize_tail_OOB(self):
        r = Range(-30).normalize(20)
        self.assertEqual(r.first, 0)
        self.assertEqual(r.last, 19)
        self.assertEqual(r.count, 20)
        self.assertEqual(r.total, 20)

    def test_normalize_OOB_first(self):
        with self.assertRaises(IndexError):
            Range(3,7).normalize(2)

    def test_normalize_OOB_last(self):
        with self.assertRaises(IndexError):
            Range(3,7).normalize(5)

class HeadersTests(TestCase):
    def test_parse_full(self):
        r = Paginator().parse_header("items=3-7")
        self.assertEqual(r, Range(3,7))

    def test_parse_start(self):
        r = Paginator().parse_header("items=3-")
        self.assertEqual(r, Range(3))

    def test_parse_end(self):
        r = Paginator().parse_header("items=-7")
        self.assertEqual(r, Range(-7))

    def test_parse_invalid(self):
        with self.assertRaises(ParseError):
            Paginator().parse_header("items=-")

    def test_format(self):
        s = Paginator().format_header(Range(3,7,total=10))
        self.assertEqual(s, "items 3-7/10")

    def test_format_total(self):
        s = Paginator().format_header(Range(total=10))
        self.assertEqual(s, "items */10")

    def test_format_unnormalized(self):
        with self.assertRaises(TypeError):
            Paginator().format_header(Range(3,7))

class TestDoc(Document):
    foo = fields.IntField()


class PaginatingTests(DatasetTesting, TestCase):
    def setUp(self):
        self.objects = [ TestDoc.objects.create(foo=i) for i in range(0,20) ]

    def tearDown(self):
        TestDoc.objects.delete()

    def test_skip(self):
        pager = Paginator()
        req = APIRequestFactory().get("/", HTTP_RANGE="items=3-")
        qs = TestDoc.objects.all().order_by('foo')

        page = pager.paginate_queryset(qs, req)

        self.assertEqual(page['data'].count(), 17)
        self.assertDatasetDocs(page['data'], self.objects[3:])

        res = pager.get_paginated_response(page['data'], page['range'])

        self.assertIn('Content-Range', res)
        self.assertEqual(res['Content-Range'], "items 3-19/20")

    def test_skip_limited(self):
        pager = Paginator(10)
        req = APIRequestFactory().get("/", HTTP_RANGE="items=3-")
        qs = TestDoc.objects.all().order_by('foo')

        page = pager.paginate_queryset(qs, req)

        self.assertEqual(page['data'].count(), 10)
        self.assertDatasetDocs(page['data'], self.objects[3:13])

        res = pager.get_paginated_response(page['data'], page['range'])

        self.assertEqual(res.status_code, 200)
        self.assertIn('Content-Range', res)
        self.assertEqual(res['Content-Range'], "items 3-12/20")

    def test_skip_limited_OOB(self):
        pager = Paginator(100)
        req = APIRequestFactory().get("/", HTTP_RANGE="items=3-")
        qs = TestDoc.objects.all().order_by('foo')

        page = pager.paginate_queryset(qs, req)

        self.assertEqual(page['data'].count(), 17)
        self.assertDatasetDocs(page['data'], self.objects[3:])

        res = pager.get_paginated_response(page['data'], page['range'])

        self.assertIn('Content-Range', res)
        self.assertEqual(res['Content-Range'], "items 3-19/20")

    def test_skip_OOB(self):
        pager = Paginator()
        req = APIRequestFactory().get("/", HTTP_RANGE="items=100-")
        qs = TestDoc.objects.all().order_by('foo')

        page = pager.paginate_queryset(qs, req)

        self.assertEqual(page['data'], None)

        res = pager.get_paginated_response(page['data'], page['range'])

        self.assertEqual(res.status_code, 416)
        self.assertIn('Content-Range', res)
        self.assertEqual(res['Content-Range'], "items */20")

    def test_range(self):
        pager = Paginator()
        req = APIRequestFactory().get("/", HTTP_RANGE="items=3-7")
        qs = TestDoc.objects.all().order_by('foo')

        page = pager.paginate_queryset(qs, req)

        self.assertEqual(page['data'].count(), 5)
        self.assertDatasetDocs(page['data'], self.objects[3:8])

        res = pager.get_paginated_response(page['data'], page['range'])

        self.assertEqual(res.status_code, 200)
        self.assertIn('Content-Range', res)
        self.assertEqual(res['Content-Range'], "items 3-7/20")

    def test_range_limited(self):
        pager = Paginator(10)
        req = APIRequestFactory().get("/", HTTP_RANGE="items=3-7")
        qs = TestDoc.objects.all().order_by('foo')

        page = pager.paginate_queryset(qs, req)

        self.assertEqual(page['data'].count(), 5)
        self.assertDatasetDocs(page['data'], self.objects[3:8])

        res = pager.get_paginated_response(page['data'], page['range'])

        self.assertEqual(res.status_code, 200)
        self.assertIn('Content-Range', res)
        self.assertEqual(res['Content-Range'], "items 3-7/20")

    def test_range_OOB(self):
        pager = Paginator()
        req = APIRequestFactory().get("/", HTTP_RANGE="items=3-100")
        qs = TestDoc.objects.all().order_by('foo')

        page = pager.paginate_queryset(qs, req)

        self.assertEqual(page['data'], None)

        res = pager.get_paginated_response(page['data'], page['range'])

        self.assertEqual(res.status_code, 416)
        self.assertIn('Content-Range', res)
        self.assertEqual(res['Content-Range'], "items */20")

    def test_tail(self):
        pager = Paginator()
        req = APIRequestFactory().get("/", HTTP_RANGE="items=-15")
        qs = TestDoc.objects.all().order_by('foo')

        page = pager.paginate_queryset(qs, req)

        self.assertEqual(page['data'].count(), 15)
        self.assertDatasetDocs(page['data'], self.objects[-15:])

        res = pager.get_paginated_response(page['data'], page['range'])

        self.assertEqual(res.status_code, 200)
        self.assertIn('Content-Range', res)
        self.assertEqual(res['Content-Range'], "items 5-19/20")

    def test_tail_limited(self):
        pager = Paginator(10)
        req = APIRequestFactory().get("/", HTTP_RANGE="items=-15")
        qs = TestDoc.objects.all().order_by('foo')

        page = pager.paginate_queryset(qs, req)

        self.assertEqual(page['data'].count(), 15)
        self.assertDatasetDocs(page['data'], self.objects[-15:])

        res = pager.get_paginated_response(page['data'], page['range'])

        self.assertEqual(res.status_code, 200)
        self.assertIn('Content-Range', res)
        self.assertEqual(res['Content-Range'], "items 5-19/20")

    def test_tail_OOB(self):
        pager = Paginator()
        req = APIRequestFactory().get("/", HTTP_RANGE="items=-100")
        qs = TestDoc.objects.all().order_by('foo')

        page = pager.paginate_queryset(qs, req)

        self.assertEqual(page['data'].count(), 20)
        self.assertDatasetDocs(page['data'], self.objects)

        res = pager.get_paginated_response(page['data'], page['range'])

        self.assertEqual(res.status_code, 200)
        self.assertIn('Content-Range', res)
        self.assertEqual(res['Content-Range'], "items 0-19/20")
