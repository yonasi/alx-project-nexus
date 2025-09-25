from django.shortcuts import render
from django.db import IntegrityError
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, IsAuthenticatedOrReadOnly
from rest_framework.views import APIView
from django.contrib.auth.models import User
from .models import Poll, Question, Choice, Vote
from .serializers import PollSerializer, QuestionSerializer, ChoiceSerializer, VoteSerializer
from rest_framework.exceptions import PermissionDenied
from .tasks import process_vote


class PollViewSet(viewsets.ModelViewSet):
    '''
    API endpoint for managing polls.
    - GET /api/v1/polls/: List all polls.
    - GET /api/vl/polls/{id}/: Retrives poll details.
    - POST /api/v1/polls/: Create a poll (authenticated).
    - PUT /aip/v1/polls/{id}: Update a poll (creator only).
    - DELETE /api/v1/polls/{id}/: Delete a poll (creator only).
    - POST /api/v1/polls/{id}/: Submit a vote (authenticated).
    '''
    queryset = Poll.objects.filter(is_active=True)  # Only active polls
    serializer_class = PollSerializer
    permission_class = [IsAuthenticatedOrReadOnly]


    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)
    

    def perform_update(self, serializer):
        if self.get_object().created_by != self.request.user:
            raise PermissionDenied('You can only update your own polls.')
        serializer.save(partial=True) # To support PATCH
    

    def perform_destroy(self, instance):
        if instance.created_by != self.request.user:
            raise PermissionDenied('You can only delete your own polls.')
        instance.delete()


    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated])
    def vote(self, request, pk=None):
        '''
        Submit a vote for a poll's question.
        Request body: {'question': <id>, 'choice': <id>}
        '''
        poll = self.get_object()
        serializer = VoteSerializer(data=request.data, context={'request': request})
        if serializer.is_valid():
            question = serializer.validated_data['question']
            choice = serializer.validated_data['choice']
            if question.poll != poll:
                return Response({"error": "Question does not belong to this poll"}, status=status.HTTP_400_BAD_REQUEST)
            # Queue Celery task
            result = process_vote.delay(question.id, choice.id, request.user.id)
            return Response({"message": "Vote processing started", 'task_id': result.id}, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    

class PollDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, poll_id):
        try:
            poll = Poll.objects.get(id=poll_id, is_active=True)
            serializer = PollSerializer(poll)
            return Response(serializer.data)
        except Poll.DoesNotExist:
            return Response({'error': 'Poll not found'}, status=status.HTTP_404_NOT_FOUND)


class QuestionViewSet(viewsets.ReadOnlyModelViewSet):
    '''
    API endpoint for listing questions.
    - GET /api/v1/questions/: List all questions with  choices.
    '''
    queryset = Question.objects.all()
    serializer_class = QuestionSerializer
    permission_classes = [IsAuthenticatedOrReadOnly]


class ChoiceViewSet(viewsets.ReadOnlyModelViewSet):
    '''
    API endpoints for chices.
    - GET /api/v1/choices/: List all choices with question IDs.
    '''
    queryset = Choice.objects.all()
    serializer_class = ChoiceSerializer
    permission_classes = [IsAuthenticatedOrReadOnly]


class VoteView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, poll_id):
        choice_id = request.data.get('choice_id')
        try:
            # Validate choice belongs to poll
            choice = Choice.objects.get(id=choice_id, question__poll_id=poll_id)
            question = choice.question
            # Trigger Celery task
            result = process_vote.delay(question.id, choice_id, request.user.id)
            # Wait for result (for tests; remove in production for async)
            result = result.get(timeout=5)
            if 'error' in result:
                return Response({'error': result['error']}, status=status.HTTP_400_BAD_REQUEST)
            return Response({'message': 'Vote recorded'}, status=status.HTTP_201_CREATED)
        except Choice.DoesNotExist:
            return Response({'error': 'Invalid choice'}, status=status.HTTP_400_BAD_REQUEST)
        