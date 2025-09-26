import graphene
from graphene_django import DjangoObjectType
from .models import Poll, Question, Choice
from .tasks import process_vote


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


class CreatePollMutation(graphene.Mutation):
    class Arguments:
        title = graphene.String(required=True)
    poll = graphene.Field(PollType)

    def mutate(self, info, title):
        if not info.context.user.is_authenticated:
            raise Exception("Authentication required")
        poll = Poll.objects.create(title=title, created_by=info.context.user, is_active=True)
        return CreatePollMutation(poll=poll)


class VoteMutation(graphene.Mutation):
    class Arguments:
        poll_id = graphene.Int(required=True)
        choice_id = graphene.Int(required=True)
    success = graphene.Boolean()
    message = graphene.String()

    def mutate(self, info, poll_id, choice_id):
        if not info.context.user.is_authenticated:
            raise Exception("Authentication required")
        poll = Poll.objects.get(id=poll_id, is_active=True)
        choice = Choice.objects.get(id=choice_id, question__poll=poll)
        question = choice.question
        task = process_vote.delay(question.id, choice_id, info.context.user.id)
        return VoteMutation(success=True, message='Vote queued')


class Mutation(graphene.ObjectType):
    create_poll = CreatePollMutation.Field()
    vote = VoteMutation.Field()

schema = graphene.Schema(query=Query, mutation=Mutation)
