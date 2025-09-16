from rest_framework import serializers
from .models import Poll, Question, Choice


class ChoiceSerializer(serializers.ModelSerializer):
    class Meta:
        model = Choice
        fields = ['id', 'text', 'vote_count']


class QuestionSerializer(serializers.ModelSerializer):
    choices = ChoiceSerializer(many = True, read_only=True)


    class Meta:
        fields = ['id', 'text', 'poll', 'choices']


class PollSerializer(serializers.ModelSerializer):
    questions = QuestionSerializer(many=True, read_only=True)


    class Meta:
        model = Poll
        fields = ['id', 'title', 'created_at', 'is_active', 'questions']
