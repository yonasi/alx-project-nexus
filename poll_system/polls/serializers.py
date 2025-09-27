from rest_framework import serializers
from .models import Poll, Question, Choice, Vote
from django.contrib.auth.models import User

class ChoiceSerializer(serializers.ModelSerializer):
    vote_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = Choice
        fields = ['id', 'text', 'question', 'vote_count']

class QuestionSerializer(serializers.ModelSerializer):
    choices = ChoiceSerializer(many=True, read_only=True)

    class Meta:
        model = Question
        fields = ['id', 'text', 'poll', 'choices']

class PollSerializer(serializers.ModelSerializer):
    questions = QuestionSerializer(many=True, read_only=True)
    created_by = serializers.ReadOnlyField(source='created_by.username')

    class Meta:
        model = Poll
        fields = ['id', 'title','description', 'created_at', 'created_by', 'is_active', 'questions']

class VoteSerializer(serializers.ModelSerializer):
    class Meta:
        model = Vote
        fields = ['id', 'question', 'choice', 'user', 'created_at']
        read_only_fields = ['user', 'created_at']

    def validate(self, data):
        question = data['question']
        choice = data['choice']
        if choice.question != question:
            raise serializers.ValidationError('Choice does not belong to the question.')
        if Vote.objects.filter(question=question, user=self.context['request'].user).exists():
            raise serializers.ValidationError('User already voted on this question.')
        return data

class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'password']
        extra_kwargs = {'password': {'write_only': True}}

    def create(self, validated_data):
        user = User.objects.create_user(**validated_data)
        return user