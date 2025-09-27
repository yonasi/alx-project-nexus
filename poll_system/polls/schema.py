import graphene
from graphene_django import DjangoObjectType
from .models import Poll, Question, Choice, Vote
from .tasks import process_vote
from django.db import IntegrityError 

#Types

class PollType(DjangoObjectType):
    class Meta:
        model = Poll
        fields = ('id', 'title', 'description', 'created_at', 'updated_at', 'end_date', 'created_by', 'is_active', 'questions')

class QuestionType(DjangoObjectType):
    class Meta:
        model = Question
        fields = ('id', 'text', 'poll', 'choices')

class ChoiceType(DjangoObjectType):
    votes_count = graphene.Int()

    class Meta:
        model = Choice
        fields = ('id', 'text', 'question', 'votes_count')


# Queries

class Query(graphene.ObjectType):
    all_polls = graphene.List(PollType)
    poll = graphene.Field(PollType, id=graphene.Int())

    def resolve_all_polls(self, info):
        return Poll.objects.filter(is_active=True).prefetch_related('questions__choices')

    def resolve_poll(self, info, id):
        return Poll.objects.get(id=id, is_active=True)

# Mutations

class CreatePollMutation(graphene.Mutation):
    class Arguments:
        title = graphene.String(required=True)
        description = graphene.String(required=False)
        end_date = graphene.DateTime(required=False)
    poll = graphene.Field(PollType)

    def mutate(self, info, title, description=None, end_date=None):
        if not info.context.user.is_authenticated:
            raise Exception("Authentication required")
        poll = Poll.objects.create(
            title=title, 
            description=description,
            end_date=end_date,
            created_by=info.context.user, 
            is_active=True
        )
        return CreatePollMutation(poll=poll)

class VoteMutation(graphene.Mutation):
    class Arguments:
        question_id = graphene.Int(required=True)
        choice_id = graphene.Int(required=True)
    success = graphene.Boolean()
    message = graphene.String()

    def mutate(self, info, question_id, choice_id):
        if not info.context.user.is_authenticated:
            raise Exception("Authentication required. Please log in to vote.")
            
        user = info.context.user
        
        try:
            # Validate Choice/Question relationship and existence
            choice = Choice.objects.select_related('question').get(id=choice_id, question__id=question_id)
            question = choice.question

            # Check for duplicate vote *before* queueing the task
            if Vote.objects.filter(question=question, user=user).exists():
                raise Exception("You have already voted on this question.")

            # Queue the asynchronous vote processing task
            task = process_vote.delay(question.id, choice.id, user.id)
            
            return VoteMutation(success=True, message=f'Vote queued for processing. Task ID: {task.id}')
        
        except Choice.DoesNotExist:
            raise Exception("Invalid choice ID or choice does not belong to the specified question.")
        except Exception as e:
            return VoteMutation(success=False, message=str(e))


class Mutation(graphene.ObjectType):
    create_poll = CreatePollMutation.Field()
    vote = VoteMutation.Field()

schema = graphene.Schema(query=Query, mutation=Mutation)