from django.conf import settings
from django.utils.deprecation import MiddlewareMixin


class ReleaseHeader(MiddlewareMixin):
    def process_response(self, request, response):
        response['X-scTWAS-Release'] = settings.SCTWAS_RELEASE
        return response
