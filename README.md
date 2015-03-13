# drf-header-paging
Header-based paginf for django-rest-framework 3.0 (does not use new 3.1 paging API because it's insufficient)

Handles HTTP header Range and respond with Content-Range with unit 'items' to slice your queryset.

# Status

coding in process

# Behaviour
* no header: slice queryset as [:default_limit]
* `Range: items N-`: [N:][:default_limit]
* `Range: items N-M`: [N:M]
* `Range: items N-OOB`: returns HTTP 416 response with `Content-Range: */total`
* `Range: items OOB-*`: returns HTTP 416 response with `Content-Range: */total`
* `Range: items -M`: slice [-M:]

Header `Accept-Range` is not installed

# Usage

```python
from drf_header_pager import PagedListModelMixin, Paginator
class PaginatedView(PagedListModelMixin, GenericViewSet):
  pagination_class = Paginator
  pagination_default_limit = 1000
```

The `PagedListModelMixin` redefines method `list`
