from django.db import IntegrityError
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, IsAuthenticatedOrReadOnly
from rest_framework.views import APIView
from rest_framework.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404
from .models import Poll, Question, Choice, Vote
from .serializers import PollSerializer, QuestionSerializer, ChoiceSerializer, VoteSerializer
from .tasks import process_vote


class PollViewSet(viewsets.ModelViewSet):
    '''
    API endpoint for managing polls.
    API endpoint for managing polls.
    - GET /api/v1/polls/: List all polls.
    - GET /api/vl/polls/{id}/: Retrives poll details.
    - POST /api/v1/polls/: Create a poll (authenticated).
    - PUT /aip/v1/polls/{id}: Update a poll (creator only).
    - DELETE /api/v1/polls/{id}/: Delete a poll (creator only).
    - POST /api/v1/polls/{id}/: Submit a vote (authenticated).
    '''
    queryset = Poll.objects.filter(is_active=True) #lists only active polls
    serializer_class = PollSerializer
    permission_classes = [IsAuthenticatedOrReadOnly]

    def perform_create(self, serializer):
        """
        Sets the creator of the poll to the authenticated user.
        """
        serializer.save(created_by=self.request.user)

    def perform_update(self, serializer):
        """
        Ensures only the poll creator can update the poll.
        """
        if self.get_object().created_by != self.request.user:
            raise PermissionDenied('You can only update your own polls.')
        serializer.save(partial=True)

    def perform_destroy(self, instance):
        """
        Ensures only the poll creator can delete the poll.
        """
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
            
            # The API immediately responds while the task runs in the background.
            return Response({"message": "Vote processing started", 'task_id': result.id}, status=status.HTTP_202_ACCEPTED)

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
    API endpoints for choices.
    - GET /api/v1/choices/: List all choices with question IDs.
    '''
    queryset = Choice.objects.all()
    serializer_class = ChoiceSerializer
    permission_classes = [IsAuthenticatedOrReadOnly]
