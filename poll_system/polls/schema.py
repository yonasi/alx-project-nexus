import graphene
from graphene_django import DjangoObjectType
from .models import Poll, Question, Choice

class PollType(DjangoObjectType):
    class Meta:
        model = Poll
        fields = ('id', 'title', 'created_at', 'created_by', 'is_active', 'questions')

class QuestionType(DjangoObjectType):
    class Meta:
        model = Question
        fields = ('id', 'text', 'poll', 'choices')

class ChoiceType(DjangoObjectType):
    class Meta:
        model = Choice
        fields = ('id', 'text', 'vote_count', 'question')

class Query(graphene.ObjectType):
    all_polls = graphene.List(PollType)
    poll = graphene.Field(PollType, id=graphene.Int())

    def resolve_all_polls(self, info):
        return Poll.objects.filter(is_active=True)

    def resolve_poll(self, info, id):
        return Poll.objects.get(id=id, is_active=True)

schema = graphene.Schema(query=Query)