"""scTWAS URL Configuration

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/2.1/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
try:
    from django.urls import re_path as url
except ImportError:  # Legacy deployment during the staged runtime migration.
    from django.conf.urls import url

from . import views, association_views, explore, provenance
from .task_views import download_twas, detail_training, download_training

app_name = 'sctwas'

urlpatterns = [
        url(r'^provenance$', provenance.page, name='provenance'),
        url(r'^provenance_download$', provenance.download, name='provenance_download'),
        url(r'^explore_data$', explore.search_data, name='explore_data'),
        url(r'^association_data$', association_views.table_data, name='association_data'),
        url(r'^association_models$', association_views.model_data, name='association_models'),
        url(r'^association_download$', association_views.table_download, name='association_download'),
        url(r'^association_export$', association_views.prepare_export, name='association_export'),
        url(r'^association_export_status$', association_views.export_status, name='association_export_status'),
        url(r'^association_file$', association_views.export_file, name='association_file'),
        url(r'^health$', views.health, name='health'),
        url(r'^example_download$', views.example_download, name='example_download'),
        url(r'^catalog_download$', views.catalog_download, name='catalog_download'),
        url(r'^documentation$', views.documentation, name='documentation'),
        url(r'^downloads$', views.downloads, name='downloads'),
        url(r'^test', views.test, name='test'),
        url(r'^twas', views.twas, name='twas'),
        url(r'^grex', views.grex, name='grex'),
        url(r'^query', views.query, name='query'),
        url(r'^upload_twas', views.upload_twas, name='upload_twas'),
        url(r'^upload_grex', views.upload_grex, name='upload_grex'),
        url(r'^getTraitData', views.getTraitData, name='getTraitData'),
        url(r'^detail', views.detail, name='detail'),
        url(r'^browse', views.browse, name='browse'),
        url(r'^training_result$', detail_training, name='training_result'),
        url(r'^download_training$', download_training, name='download_training'),
        url(r'^download_twas$', download_twas, name='download_twas'),
        url(r'^download', views.download, name='download'),
        url(r'^celltypes', views.celltypes, name='celltypes'),
        url(r'^$', views.index, name='index'),
]
