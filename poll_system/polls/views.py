from django.shortcuts import render
from django.db import IntegrityError
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, IsAuthenticatedOrReadOnly
from .models import Poll, Vote
from .serializers import PollSerializer, VoteSerializer



class PollViewSet(viewsets.ModelViewSet):
    queryset = Poll.objects.filter(is_active=True)  # Only active polls
    serializer_class = PollSerializer
    permission_class = [IsAuthenticatedOrReadOnly]


    @action(detail=True, methods=['get', 'post'], permission_classes=[IsAuthenticated])
    def vote(self, request, pk=None):
        poll = self.get_object()
        serializer = VoteSerializer(data=request.data, context={'request': request})
        if serializer.is_valid():
            question = serializer.validated_data['question']
            choice = serializer.validated_data['choice']
            if question.poll != poll:
                return Response({"error": "Question does not belong to this poll"}, status=status.HTTP_400_BAD_REQUEST)
            try:
                Vote.objects.create(
                    question=question,
                    choice=choice,
                    user=request.user
                )
                choice.vote_count += 1
                choice.save()
                return Response({"message": "Vote recorded"}, status=status.HTTP_201_CREATED)
            except IntegrityError:
                return Response({"error": "User already voted on this question"}, status=status.HTTP_400_BAD_REQUEST)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)