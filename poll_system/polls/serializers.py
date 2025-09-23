from rest_framework import serializers
from .models import Poll, Question, Choice, Vote
from django.db import IntegrityError

class ChoiceSerializer(serializers.ModelSerializer):
    class Meta:
        model = Choice
        fields = ['id', 'text', 'vote_count', 'question']
        read_only_fields = ['vote_count', 'question']  # Prevent updating vote_count directly

class QuestionSerializer(serializers.ModelSerializer):
    choices = ChoiceSerializer(many=True, read_only=True)

    class Meta:
        model = Question
        fields = ['id', 'text', 'poll', 'choices']
        read_only_fields = ['poll']  # Set by parent poll


    def create(self, validated_data):
        choices_data = validated_data.pop('choices')
        question = Question.objects.create(**validated_data)
        for choice_data in choices_data:
            Choice.objects.create(question = question, **choices_data)
        return question
    

class PollSerializer(serializers.ModelSerializer):
    questions = QuestionSerializer(many=True, read_only=True)

    class Meta:
        model = Poll
        fields = ['id', 'title', 'created_at', 'created_by', 'is_active', 'questions']
        read_only_fields = ['created_at', 'created_by']  # Auto-set fields

    
    def create(self, validated_data):
        questions_data = validated_data.pop('questions')
        poll = Poll.objects.create(created_by=self.context['request'].user, **validated_data)
        for question_data in questions_data:
            QuestionSerializer().create({**question_data, 'poll': poll})
        return poll
    

    def update(self, validated_data):
        questions_data = validated_data.pop('questions', None)
        poll = self.instance
        for attr, value in validated_data.items():
            setattr(poll, attr, value)
        poll.save()
        if questions_data is not None:
            poll.questions.all().delete()  # Deleting existing questions
            for question_data in questions_data:
                QuestionSerializer().create({**question_data, 'poll':poll})
            return poll
        

class VoteSerializer(serializers.ModelSerializer):
    class Meta:
        model = Vote
        fields = ['id', 'question', 'choice', 'user', 'created_at']
        read_only_fields = ['user', 'created_at']


        def validate(self, data):
            question = data['question']
            choice = data['choice']
            if choice.question!= question:
                raise serializers.ValidationError('Choice does not belong to the question.')
            return data
