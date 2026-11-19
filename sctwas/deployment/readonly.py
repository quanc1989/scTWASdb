"""Read-only example mode for local catalogue and saved-result browsing."""
from django.conf import settings
from django.http import HttpResponse


class DemoReadOnly:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        blocked = request.method not in ('GET', 'HEAD', 'OPTIONS') or request.path in (
            '/upload_twas', '/upload_grex', '/association_export',
        )
        if settings.SCTWAS_READ_ONLY_DEMO and blocked:
            return HttpResponse('This example installation supports read-only browsing.', status=405)
        return self.get_response(request)
