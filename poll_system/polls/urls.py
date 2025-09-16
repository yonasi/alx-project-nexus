from django.contrib import admin
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from polls.views import PollViewSet


router = DefaultRouter()
router.register(r'polls', PollViewSet)


urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/v1/', include.router.urls),
]