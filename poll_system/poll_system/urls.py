from django.contrib import admin
from django.urls import path, include
from django.views.generic import TemplateView
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from rest_framework.permissions import IsAuthenticatedOrReadOnly
import rest_framework_simplejwt.authentication
from drf_yasg.views import get_schema_view
from drf_yasg import openapi
from polls.views import PollViewSet, QuestionViewSet, ChoiceViewSet
from graphene_django.views import GraphQLView
from polls.schema import schema

schema_view = get_schema_view(
    openapi.Info(
        title='Online Poll System API',
        default_version='v1',
        description='API for creating, managing, and voting on polls',
        terms_of_service='https://www.example.com/terms/',
        contact=openapi.Contact(
            name='Yonas',
            email='yonasma416@gmail.com',
            url='https://github.com/yonasi'
        ),
        license=openapi.License(name='MIT License'),
    ),
    public=True,
    permission_classes=[IsAuthenticatedOrReadOnly],
    authentication_classes=[rest_framework_simplejwt.authentication.JWTAuthentication],
)

router = DefaultRouter()
router.register(r'polls', PollViewSet)
router.register(r'questions', QuestionViewSet)
router.register(r'choices', ChoiceViewSet)

urlpatterns = [
    path('', TemplateView.as_view(template_name='index.html'), name='home'),
    path('admin/', admin.site.urls),
    path('api/v1/', include(router.urls)),
    path('api/v1/token/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('api/v1/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('swagger/', schema_view.with_ui('swagger', cache_timeout=0), name='schema-swagger-ui'),
    path('redoc/', schema_view.with_ui('redoc', cache_timeout=0), name='schema-redoc'),
    path('graphql/', GraphQLView.as_view(graphiql=True, schema=schema)),
]