import re
from rest_framework.response import Response
from rest_framework.exceptions import ParseError

class Range():
    """ representation of possible ranges
    [s:e]
    [s:]
    [:e]
    [-s:]
    """
    def __init__(self, first=None, last=None, count=None, total=None):
        """
        first, last: [s:e]
        first, count: [s:e]
        first [s:] | [-s:]
        """
        self.first = None
        self.last = None
        self.count = None
        self.total = total

        if total is not None: # normalized
            if first is not None and last is not None:
                self.first = first
                self.last = last
                self.count = last - first + 1
        else:
            if first is None:
                raise TypeError("missing required arg `first`")

            self.first = first
            if last is not None:
                self.last = last
                self.count = last - first + 1
            if count is not None:
                self.last = first + count - 1
                self.count = count

    def normalize(self, total, maximum=None):
        """ return normalized to boundaries as [s:e] in respect of total or maximum
        may raise OOB error
        """
        if self.first < 0: # [-s:] -> [s:t]/t
            tail = -self.first
            first = total + self.first
            if first < 0:
                first = 0
            return Range(first, total-1, total=total)

        if self.last is None: # [s:] -> [s:max]
            if maximum is not None:
                self.last = min(total, self.first + maximum) - 1
            else:
                self.last = total - 1

        if self.first > total or self.last > total:
            raise IndexError("OOB", self.first, self.last, total)

        return Range(self.first, self.last, total=total)

    @property
    def slice(self):
        return slice(self.first, self.last+1 if self.last else None)

    def __str__(self):
        return "<Range [%s:%s]/%s>" % (self.first, self.last, self.total)

    def __eq__(self, other):
        return self.first == other.first and self.last == other.last and self.total == other.total

class Paginator(object):
    default_limit = None

    def __init__(self, default_limit=None):
        if default_limit is not None:
            self.default_limit = default_limit

    _re = re.compile('items=(\d+)?-(\d+)?')

    def parse_header(self, header):
        """ parses request header into Range """
        m = self._re.match(header)

        try:
            if not m:
                raise ParseError()
            try:
                args = (int(m.group(1)) if m.group(1) else None, int(m.group(2)) if m.group(2) else None)
            except ValueError:
                raise ParseError()
            if args[0] is None and args[1] is None:
                raise ParseError()
        except ParseError:
            raise ParseError({'HTTP Range': 'invalid header: %s' % header})
        if args[0] is None:
            return Range(-args[1])
        else:
            return Range(args[0], args[1])

    def format_header(self, prange):
        if prange.total is None:
            raise TypeError("cannot format unnormalized range")

        if prange.count:
            return "items %d-%d/%s" % (prange.first, prange.last, prange.total)
        else:
            return "items */%s" % prange.total

    def get_reqrange(self, request):
        header = request.META.get("HTTP_RANGE",None)
        if header:
            return self.parse_header(header)
        else:
            return None

    def paginate_queryset(self, queryset, request, view=None):
        total = queryset.count()

        prange = self.get_reqrange(request)
        if prange is None:
            prange = Range(0)
        try:
            prange = prange.normalize(total, self.default_limit)
            paged_queryset = queryset[prange.slice]
            return { 'data': paged_queryset, 'range': prange }
        except IndexError:
            return { 'data': None, 'range': Range(total=total) }

    def get_paginated_response(self, data, prange):
        if data is None:
            return Response(status=416, headers={"Content-Range": self.format_header(prange) })
        else:
            return Response(data=data, headers={"Content-Range": self.format_header(prange) })

class PagedListModelMixin(object):
    @property
    def paginator(self):
        """
        The paginator instance associated with the view, or `None`.
        """
        if not hasattr(self, '_paginator'):
            if getattr(self, 'pagination_class', None) is None:
                self._paginator = None
            else:
                self._paginator = self.pagination_class(getattr(self,'pagination_default_limit', None))
        return self._paginator

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())

        if self.paginator is not None:
            page = self.paginator.paginate_queryset(queryset, request, view=self)
            if page['data'] is not None:
                serializer = self.get_serializer(page['data'], many=True)
                return self.paginator.get_paginated_response(serializer.data, page['range'])
            else:
                return self.paginator.get_paginated_response(None, page['range'])


        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)
