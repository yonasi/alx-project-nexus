from django.db import IntegrityError
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, IsAuthenticatedOrReadOnly
from rest_framework.exceptions import PermissionDenied, ValidationError
from django.shortcuts import get_object_or_404
from .models import Poll, Question, Choice, Vote
from .serializers import PollSerializer, QuestionSerializer, ChoiceSerializer, VoteSerializer


class PollViewSet(viewsets.ModelViewSet):
    '''
    API endpoint for managing polls.
    - GET /api/v1/polls/: List all polls.
    - GET /api/v1/polls/{id}/: Retrieves poll details.
    - POST /api/v1/polls/: Create a poll (authenticated).
    - PUT/PATCH /api/v1/polls/{id}: Update a poll (creator only).
    - DELETE /api/v1/polls/{id}/: Delete a poll (creator only).
    '''
    queryset = Poll.objects.filter(is_active=True)
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
        serializer.save()

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
        Request body: {'choice': <id>}
        '''
        poll = get_object_or_404(Poll, pk=pk)
        
        try:
            choice_id = request.data.get('choice')
            if not choice_id:
                raise ValidationError({"error": "The 'choice' field is required."})

            choice = get_object_or_404(Choice, id=choice_id)

            if choice.question.poll != poll:
                raise ValidationError({"error": "Choice does not belong to this poll."})

            # Check if the user has already voted on the question
            if Vote.objects.filter(user=request.user, question=choice.question).exists():
                return Response({"error": "You have already voted on this question."}, status=status.HTTP_409_CONFLICT)
            
            # Create the vote
            Vote.objects.create(user=request.user, question=choice.question, choice=choice)
            
            return Response({"message": "Vote recorded successfully."}, status=status.HTTP_201_CREATED)

        except ValidationError as e:
            return Response(e.detail, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)


class QuestionViewSet(viewsets.ReadOnlyModelViewSet):
    '''
    API endpoint for listing questions.
    '''
    queryset = Question.objects.all()
    serializer_class = QuestionSerializer
    permission_classes = [IsAuthenticatedOrReadOnly]


class ChoiceViewSet(viewsets.ReadOnlyModelViewSet):
    '''
    API endpoints for choices.
    '''
    queryset = Choice.objects.all()
    serializer_class = ChoiceSerializer
    permission_classes = [IsAuthenticatedOrReadOnly]