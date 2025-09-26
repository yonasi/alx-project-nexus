from django.shortcuts import render
from django.db import IntegrityError
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, IsAuthenticatedOrReadOnly
from django.contrib.auth.models import User
from .models import Poll, Question, Choice, Vote
from .serializers import PollSerializer, QuestionSerializer, ChoiceSerializer, VoteSerializer
from rest_framework.exceptions import PermissionDenied
from .tasks import process_vote
import logging

logger = logging.getLogger(__name__)

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