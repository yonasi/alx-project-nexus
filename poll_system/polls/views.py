from django.shortcuts import render
from django.db import IntegrityError, transaction
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, IsAuthenticatedOrReadOnly
from rest_framework.views import APIView
from django.contrib.auth.models import User
from django.db.models import Sum, Max, F 
from .models import Poll, Question, Choice, Vote
from .serializers import PollSerializer, ChoiceSerializer, UserSerializer, QuestionSerializer
from rest_framework.exceptions import PermissionDenied, ValidationError
from .tasks import process_vote
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi
from django.utils.decorators import method_decorator
from django.core.cache import cache
from django.views.decorators.cache import cache_page
from django_ratelimit.decorators import ratelimit
import logging


logger = logging.getLogger(__name__)


def get_poll_stats_cache_key(poll_pk):
    """Generates the cache key fragment for poll stats."""
    return f'poll_stats_pk_{poll_pk}'

def invalidate_poll_stats_cache(poll_pk):
    """Clears the cache for a specific poll's stats view."""
    cache_key = get_poll_stats_cache_key(poll_pk)
    # Using pattern matching to clear the cache page
    cache.delete_pattern(f'*{cache_key}*') 
    logger.info(f"Invalidated cache for poll stats key pattern: *{cache_key}*")


class RegisterView(APIView):
    @swagger_auto_schema(
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            required=['username', 'password'],
            properties={
                'username': openapi.Schema(type=openapi.TYPE_STRING, description='Unique username'),
                'email': openapi.Schema(type=openapi.TYPE_STRING, format='email', description='User email (optional)'),
                'password': openapi.Schema(type=openapi.TYPE_STRING, format='password', description='User password')
            },
        ),
        responses={
            201: openapi.Response('User created', openapi.Schema(
                type=openapi.TYPE_OBJECT,
                properties={
                    'id': openapi.Schema(type=openapi.TYPE_INTEGER),
                    'username': openapi.Schema(type=openapi.TYPE_STRING),
                    'email': openapi.Schema(type=openapi.TYPE_STRING)
                }
            )),
            400: 'Bad Request'
        }
    )
    def post(self, request):
        serializer = UserSerializer(data=request.data)
        if serializer.is_valid():
            user = serializer.save()
            return Response({
                'id': user.id,
                'username': user.username,
                'email': user.email
            }, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class ChangePasswordView(APIView):
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            required=['old_password', 'new_password'],
            properties={
                'old_password': openapi.Schema(type=openapi.TYPE_STRING, format='password', description='Current password'),
                'new_password': openapi.Schema(type=openapi.TYPE_STRING, format='password', description='New password')
            },
        ),
        responses={
            200: openapi.Response('Password changed', openapi.Schema(
                type=openapi.TYPE_OBJECT,
                properties={'message': openapi.Schema(type=openapi.TYPE_STRING)}
            )),
            400: 'Bad Request'
        },
        security=[{'Bearer': []}]
    )
    def post(self, request):
        user = request.user
        old_password = request.data.get('old_password')
        new_password = request.data.get('new_password')
        if not old_password or not new_password:
            return Response({'error': 'old_password and new_password are required'}, status=status.HTTP_400_BAD_REQUEST)
        if not user.check_password(old_password):
            return Response({'error': 'Invalid old password'}, status=status.HTTP_400_BAD_REQUEST)
        user.set_password(new_password)
        user.save()
        logger.info(f"Password changed for user {user.username}")
        return Response({'message': 'Password changed successfully'}, status=status.HTTP_200_OK)


class PollViewSet(viewsets.ModelViewSet):
    '''
    API endpoint for managing polls.
    - GET /api/v1/polls/: List all polls.
    - GET /api/v1/polls/{id}/: Retrieve poll details.
    - POST /api/v1/polls/: Create a poll (authenticated).
    - PUT /api/v1/polls/{id}/: Update a poll (creator only).
    - DELETE /api/v1/polls/{id}/: Delete a poll (creator only).
    - POST /api/v1/polls/{id}/vote/: Submit a vote (authenticated).
    - GET /api/v1/polls/{id}/stats/: View poll vote statistics.
    '''
    queryset = Poll.objects.filter(is_active=True).prefetch_related('questions__choices') 
    serializer_class = PollSerializer
    permission_classes = [IsAuthenticatedOrReadOnly]

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

    @transaction.atomic
    def perform_update(self, serializer):
        poll = self.get_object()
        
        if poll.created_by != self.request.user:
            raise PermissionDenied('You can only update your own polls.')
            
        has_votes = Vote.objects.filter(question__poll=poll).exists()
        reset_confirmed = self.request.data.get('reset_votes', 'false').lower() == 'true'

        if has_votes:
            if not reset_confirmed:
                #give  Warning if without confirmation flag
                raise ValidationError({
                    'warning': 'This poll has recorded votes. To update, you must confirm vote reset.',
                    'action_required': 'Send "reset_votes": true in your request body to reset all votes for this poll.'
                })
            
            # If confirmed, reset votes
            if reset_confirmed:
                Vote.objects.filter(question__poll=poll).delete()
                Choice.objects.filter(question__poll=poll).update(votes_count=0)
                logger.info(f"Votes reset for poll {poll.pk} by user {self.request.user.id}")
                invalidate_poll_stats_cache(poll.pk) # Invalidate stats cache

        serializer.save()

    def perform_destroy(self, instance):
        if instance.created_by != self.request.user:
            raise PermissionDenied('You can only delete your own polls.')
        invalidate_poll_stats_cache(instance.pk) # Invalidate stats cache before delete
        instance.delete()

    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated])
    @method_decorator(ratelimit(key='user', rate='5/m', method='POST', block=True))
    @swagger_auto_schema(
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            required=['choice_id'],
            properties={
                'choice_id': openapi.Schema(type=openapi.TYPE_INTEGER, description='ID of the choice to vote for')
            },
        ),
        responses={
            202: openapi.Response('Vote queued', openapi.Schema(
                type=openapi.TYPE_OBJECT,
                properties={
                    'message': openapi.Schema(type=openapi.TYPE_STRING),
                    'task_id': openapi.Schema(type=openapi.TYPE_STRING)
                }
            )),
            400: 'Bad Request'
        },
        security=[{'Bearer': []}]
    )
    def vote(self, request, pk=None):
        '''
        Submit a vote for a poll's choice.
        '''
        poll = self.get_object()
        choice_id = request.data.get('choice_id')
        if not choice_id:
            return Response({'error': 'choice_id is required'}, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            choice = Choice.objects.get(id=choice_id, question__poll=poll)
            question = choice.question
            
            if Vote.objects.filter(question=question, user=request.user).exists():
                return Response({'error': 'User already voted on this question'}, status=status.HTTP_400_BAD_REQUEST)
            
            task = process_vote.delay(question.id, choice_id, request.user.id)
            
            invalidate_poll_stats_cache(poll.pk)
            
            return Response({"message": "Vote processing started", 'task_id': task.id}, status=status.HTTP_202_ACCEPTED)
        except Choice.DoesNotExist:
            return Response({'error': 'Invalid choice'}, status=status.HTTP_400_BAD_REQUEST)


    @action(detail=True, methods=['get'], permission_classes=[IsAuthenticatedOrReadOnly])
    @method_decorator(cache_page(60 * 5, key_prefix='poll_stats_pk_'))
    @swagger_auto_schema(
        responses={
            200: openapi.Response('Poll statistics', openapi.Schema(
                type=openapi.TYPE_OBJECT,
                properties={
                    'total_votes': openapi.Schema(type=openapi.TYPE_INTEGER, description='Total votes across all questions'),
                    'questions': openapi.Schema(
                        type=openapi.TYPE_ARRAY,
                        description='Detailed statistics per question',
                        items=openapi.Schema(
                            type=openapi.TYPE_OBJECT,
                            properties={
                                'question_id': openapi.Schema(type=openapi.TYPE_INTEGER),
                                'question_text': openapi.Schema(type=openapi.TYPE_STRING),
                                'total_question_votes': openapi.Schema(type=openapi.TYPE_INTEGER),
                                'choices': openapi.Schema(
                                    type=openapi.TYPE_ARRAY,
                                    items=openapi.Schema(
                                        type=openapi.TYPE_OBJECT,
                                        properties={
                                            'choice_id': openapi.Schema(type=openapi.TYPE_INTEGER),
                                            'text': openapi.Schema(type=openapi.TYPE_STRING),
                                            'votes_count': openapi.Schema(type=openapi.TYPE_INTEGER),
                                            'percentage': openapi.Schema(type=openapi.TYPE_NUMBER, format='float')
                                        }
                                    )
                                )
                            }
                        )
                    )
                }
            ))
        }
    )
    def stats(self, request, pk=None):
        '''
        Retrieve nested vote statistics for a poll, grouped by question.
        Utilizes the denormalized Choice.votes_count field.
        '''
        poll = self.get_object()
        
        questions_with_choices = Question.objects.filter(poll=poll).prefetch_related('choices')
        
        poll_stats = {
            'total_votes': 0,
            'questions': []
        }
        
        for question in questions_with_choices:
            question_votes = 0
            choices_data = []

            for choice in question.choices.all():
                question_votes += choice.votes_count

            for choice in question.choices.all():
                votes = choice.votes_count
                percentage = (votes / question_votes * 100) if question_votes > 0 else 0
                
                choices_data.append({
                    'choice_id': choice.id,
                    'text': choice.text,
                    'votes_count': votes,
                    'percentage': round(percentage, 2)
                })

            poll_stats['questions'].append({
                'question_id': question.id,
                'question_text': question.text,
                'total_question_votes': question_votes,
                'choices': choices_data
            })
            
            poll_stats['total_votes'] += question_votes

        return Response(poll_stats)


class QuestionViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Question.objects.all().prefetch_related('choices')
    serializer_class = QuestionSerializer 
    permission_classes = [IsAuthenticatedOrReadOnly]


class ChoiceViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Choice.objects.all()
    serializer_class = ChoiceSerializer
    permission_classes = [IsAuthenticatedOrReadOnly]