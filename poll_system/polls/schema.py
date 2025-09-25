import graphene
from graphene_django import DjangoObjectType
from .models import Poll

class PollType(DjangoObjectType):
    class Meta:
        model = Poll
        fields = '__all__'

class Query(graphene.ObjectType):
    all_polls = graphene.List(PollType)
    def resolve_all_polls(self, info):
        return Poll.objects.filter(is_active=True)

schema = graphene.Schema(query=Query)