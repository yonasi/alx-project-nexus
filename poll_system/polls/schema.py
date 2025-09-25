import graphene
from graphene_django import DjangoObjectType
from graphql import GraphQLError
from django.db import transaction
from .models import Poll, Question, Choice, Vote
from django.contrib.auth import get_user_model

# GraphQL Types for each Django model
class VoteType(DjangoObjectType):
    """
    GraphQL type for the Vote model.
    """
    class Meta:
        model = Vote
        fields = ('id', 'choice', 'user', 'created_at')

class ChoiceType(DjangoObjectType):
    """
    GraphQL type for the Choice model.
    Includes a custom field to dynamically calculate the vote count.
    """
    vote_count = graphene.Int()

    class Meta:
        model = Choice
        fields = ('id', 'text', 'question', 'vote_count')

    def resolve_vote_count(self, info):
        return self.votes.count()

class QuestionType(DjangoObjectType):
    """
    GraphQL type for the Question model.
    Includes nested choices.
    """
    class Meta:
        model = Question
        fields = ('id', 'text', 'poll', 'choices')

class PollType(DjangoObjectType):
    """
    GraphQL type for the Poll model.
    Exposes explicit fields and nested questions.
    """
    class Meta:
        model = Poll
        # Expose only the fields we want to make public
        fields = ('id', 'title', 'description', 'is_active', 'created_at', 'updated_at', 'end_date', 'questions')
    
    # Custom field to get the creator's username
    created_by_username = graphene.String()

    def resolve_created_by_username(self, info):
        return self.created_by.username


# Mutations to allow data creation and modification
class CreatePoll(graphene.Mutation):
    """
    Mutation to create a new poll.
    """
    class Arguments:
        title = graphene.String(required=True)
        description = graphene.String(required=False)
        is_active = graphene.Boolean(required=False, default_value=True)

    # Output fields after mutation
    poll = graphene.Field(PollType)

    @staticmethod
    def mutate(root, info, title, description, is_active):
        if not info.context.user.is_authenticated:
            raise GraphQLError("Authentication required to create a poll.")
        
        poll = Poll.objects.create(
            title=title,
            description=description,
            is_active=is_active,
            created_by=info.context.user
        )
        return CreatePoll(poll=poll)

class Mutation(graphene.ObjectType):
    create_poll = CreatePoll.Field()


# The main query
class Query(graphene.ObjectType):
    all_polls = graphene.List(PollType, search=graphene.String())

    def resolve_all_polls(self, info, search=None):
        queryset = Poll.objects.filter(is_active=True)
        if search:
            queryset = queryset.filter(title__icontains=search)
        return queryset

# The final schema configuration
schema = graphene.Schema(query=Query, mutation=Mutation)
