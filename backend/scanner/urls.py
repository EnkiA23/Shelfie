from django.urls import include, path
from rest_framework.routers import DefaultRouter

from scanner.views import CatalogSearchView, LibraryViewSet, ScanBookshelfView

router = DefaultRouter()
router.register("library", LibraryViewSet, basename="library")

urlpatterns = [
    path("scan/", ScanBookshelfView.as_view(), name="scan"),
    path("catalog/search/", CatalogSearchView.as_view(), name="catalog-search"),
    path("", include(router.urls)),
]
