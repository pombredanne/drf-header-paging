from unittest import mock
from unittest import TestCase

from rest_framework.test import APITestCase, APIRequestFactory
from rest_framework.exceptions import ParseError

from mongoengine import Document, fields

from rest_framework_mongoengine.serializers import DocumentSerializer
from rest_framework_mongoengine.viewsets import MongoGenericViewSet

from ..testing import DatasetTesting
from ..paginating import Paginator, PagedListModelMixin

class TestDoc(Document):
    foo = fields.IntField()

class TestSerializer(DocumentSerializer):
    class Meta:
        model = TestDoc

class DumbView(PagedListModelMixin, MongoGenericViewSet):
    queryset = TestDoc.objects.all().order_by('foo')
    serializer_class = TestSerializer

class PagingView(DumbView):
    pagination_class = Paginator

class LimitedPagingView(PagingView):
    pagination_default_limit = 10


class DumbViewTests(DatasetTesting, APITestCase):
    client_class = APIRequestFactory

    def setUp(self):
        self.objects = [ TestDoc.objects.create(foo=i) for i in range(0,20) ]
        self.view = DumbView.as_view({'get': 'list'})

    def tearDown(self):
        TestDoc.objects.delete()

    def test_list_default(self):
        res = self.view(self.client.get("/"))
        self.assertEqual(res.status_code, 200)
        self.assertNotIn('Content-Range', res)
        self.assertEqual(len(res.data), 20)
        self.assertDatasetDocsOrdered(res.data, self.objects)

    def test_list_ranged(self):
        res = self.view(self.client.get("/", HTTP_RANGE="items=3-7"))
        self.assertEqual(res.status_code, 200)
        self.assertNotIn('Content-Range', res)
        self.assertEqual(len(res.data), 20)
        self.assertDatasetDocsOrdered(res.data, self.objects)


class PagedViewTests(DatasetTesting, APITestCase):
    client_class = APIRequestFactory

    def setUp(self):
        self.objects = [ TestDoc.objects.create(foo=i) for i in range(0,20) ]
        self.view = PagingView.as_view({'get': 'list'})

    def tearDown(self):
        TestDoc.objects.delete()

    def test_list_default(self):
        res = self.view(self.client.get("/"))
        self.assertEqual(res.status_code, 200)
        self.assertIn('Content-Range', res)
        self.assertEqual(res['Content-Range'], "items 0-19/20")
        self.assertEqual(len(res.data), 20)
        self.assertDatasetDocsOrdered(res.data, self.objects)

    def test_list_ranged(self):
        res = self.view(self.client.get("/", HTTP_RANGE="items=3-7"))
        self.assertEqual(res.status_code, 200)
        self.assertIn('Content-Range', res)
        self.assertEqual(res['Content-Range'], "items 3-7/20")
        self.assertEqual(len(res.data), 5)
        self.assertDatasetDocsOrdered(res.data, self.objects[3:8])

    def test_list_ranged_OOB(self):
        res = self.view(self.client.get("/", HTTP_RANGE="items=3-100"))
        self.assertEqual(res.status_code, 416)
        self.assertIn('Content-Range', res)
        self.assertEqual(res['Content-Range'], "items */20")

    def test_list_skipped(self):
        res = self.view(self.client.get("/", HTTP_RANGE="items=3-"))
        self.assertEqual(res.status_code, 200)
        self.assertIn('Content-Range', res)
        self.assertEqual(res['Content-Range'], "items 3-19/20")
        self.assertEqual(len(res.data), 17)
        self.assertDatasetDocsOrdered(res.data, self.objects[3:20])

    def test_list_skipped_OOB(self):
        res = self.view(self.client.get("/", HTTP_RANGE="items=100-"))
        self.assertEqual(res.status_code, 416)
        self.assertIn('Content-Range', res)
        self.assertEqual(res['Content-Range'], "items */20")

class LimitedViewTests(DatasetTesting, APITestCase):
    client_class = APIRequestFactory

    def setUp(self):
        self.objects = [ TestDoc.objects.create(foo=i) for i in range(0,20) ]
        self.view = LimitedPagingView.as_view({'get': 'list'})

    def tearDown(self):
        TestDoc.objects.delete()

    def test_list_default(self):
        res = self.view(self.client.get("/"))
        self.assertEqual(res.status_code, 200)
        self.assertIn('Content-Range', res)
        self.assertEqual(res['Content-Range'], "items 0-9/20")
        self.assertEqual(len(res.data), 10)
        self.assertDatasetDocsOrdered(res.data, self.objects[:10])

    def test_list_skipped(self):
        res = self.view(self.client.get("/", HTTP_RANGE="items=3-"))
        self.assertEqual(res.status_code, 200)
        self.assertIn('Content-Range', res)
        self.assertEqual(res['Content-Range'], "items 3-12/20")
        self.assertEqual(len(res.data), 10)
        self.assertDatasetDocsOrdered(res.data, self.objects[3:13])
