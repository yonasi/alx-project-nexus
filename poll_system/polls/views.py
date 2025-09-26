from django.shortcuts import render
from django.db import IntegrityError
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, IsAuthenticatedOrReadOnly
from django.contrib.auth.models import User
from rest_framework.views import APIView
from .serializers import UserSerializer
from .models import Poll, Question, Choice, Vote
from .serializers import PollSerializer, QuestionSerializer, ChoiceSerializer, VoteSerializer
from rest_framework.exceptions import PermissionDenied
from .tasks import process_vote
import logging
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi

logger = logging.getLogger(__name__)


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
    '''
    queryset = Poll.objects.filter(is_active=True)
    serializer_class = PollSerializer
    permission_classes = [IsAuthenticatedOrReadOnly]

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

    def perform_update(self, serializer):
        if self.get_object().created_by != self.request.user:
            raise PermissionDenied('You can only update your own polls.')
        serializer.save(partial=True)

    def perform_destroy(self, instance):
        if instance.created_by != self.request.user:
            raise PermissionDenied('You can only delete your own polls.')
        instance.delete()

    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated])
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
        Request body: {'choice_id': <id>}
        '''
        poll = self.get_object()
        choice_id = request.data.get('choice_id')
        if not choice_id:
            logger.error(f"Missing choice_id in vote request for poll {pk}")
            return Response({'error': 'choice_id is required'}, status=status.HTTP_400_BAD_REQUEST)
        try:
            choice = Choice.objects.get(id=choice_id, question__poll=poll)
            question = choice.question
            # Queue Celery task
            task = process_vote.delay(question.id, choice_id, request.user.id)
            logger.info(f"Vote task queued for poll {pk}, choice {choice_id}, user {request.user.id}, task {task.id}")
            return Response({'message': 'Vote processing started', 'task_id': task.id}, status=status.HTTP_202_ACCEPTED)
        except Choice.DoesNotExist:
            logger.error(f"Invalid choice_id {choice_id} for poll {pk}")
            return Response({'error': 'Invalid choice'}, status=status.HTTP_400_BAD_REQUEST)

class QuestionViewSet(viewsets.ReadOnlyModelViewSet):
    '''
    API endpoint for listing questions.
    - GET /api/v1/questions/: List all questions with choices.
    '''
    queryset = Question.objects.all()
    serializer_class = QuestionSerializer
    permission_classes = [IsAuthenticatedOrReadOnly]

class ChoiceViewSet(viewsets.ReadOnlyModelViewSet):
    '''
    API endpoints for choices.
    - GET /api/v1/choices/: List all choices with question IDs.
    '''
    queryset = Choice.objects.all()
    serializer_class = ChoiceSerializer
    permission_classes = [IsAuthenticatedOrReadOnly]