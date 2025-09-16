from rest_framework import viewsets
from django.shortcuts import render
from .models import Poll
from .serializers import PollSerializer


class PollViewSet(viewsets.ModelViewSet):
    queryset = Poll.objects.all()
    serializer_class = PollSerializer