from rest_framework import serializers
from django.db import transaction
from django.contrib.auth.models import User
from .models import Poll, Question, Choice, Vote
from rest_framework.exceptions import ValidationError


class ChoiceSerializer(serializers.ModelSerializer):
    votes_count = serializers.IntegerField(read_only=True) 

    class Meta:
        model = Choice
        fields = ['id', 'text', 'question', 'votes_count']
        read_only_fields = ['question']


class QuestionSerializer(serializers.ModelSerializer):
    choices = ChoiceSerializer(many=True) 

    class Meta:
        model = Question
        fields = ['id', 'text', 'poll', 'choices']
        read_only_fields = ['poll']


class PollSerializer(serializers.ModelSerializer):
    questions = QuestionSerializer(many=True)
    created_by = serializers.ReadOnlyField(source='created_by.username')

    class Meta:
        model = Poll
        fields = [
            'id', 'title', 'description', 'created_at', 'updated_at', 
            'end_date', 'created_by', 'is_active', 'questions'
        ]
        read_only_fields = ['created_at', 'updated_at', 'created_by']


    @transaction.atomic
    def create(self, validated_data):
        questions_data = validated_data.pop('questions')
        poll = Poll.objects.create(**validated_data) 

        for question_data in questions_data:
            choices_data = question_data.pop('choices')
            question = Question.objects.create(poll=poll, **question_data)
            for choice_data in choices_data:
                Choice.objects.create(question=question, **choice_data)
        
        return poll

    @transaction.atomic
    def update(self, instance, validated_data):
        questions_data = validated_data.pop('questions', None)
        
        #Update Poll fields
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        #Handle Questions (Only if questions data was provided)
        if questions_data is not None:
            existing_question_ids = set(instance.questions.values_list('id', flat=True))
            incoming_question_ids = set()

            for question_data in questions_data:
                choices_data = question_data.pop('choices', [])
                question_id = question_data.get('id', None)

                if question_id and question_id in existing_question_ids:
                    # Update existing question
                    Question.objects.filter(id=question_id).update(text=question_data['text'])
                    question = Question.objects.get(id=question_id)
                    incoming_question_ids.add(question_id)
                else:
                    # Create new question
                    question = Question.objects.create(poll=instance, **question_data)
                    
                # Handle Choices for this question
                existing_choice_ids = set(question.choices.values_list('id', flat=True))
                incoming_choice_ids = set()
                
                for choice_data in choices_data:
                    choice_id = choice_data.get('id', None)

                    if choice_id and choice_id in existing_choice_ids:
                        # Update existing choice (text only, votes_count is read-only)
                        Choice.objects.filter(id=choice_id).update(text=choice_data['text'])
                        incoming_choice_ids.add(choice_id)
                    else:
                        # Create new choice
                        Choice.objects.create(question=question, **choice_data)

                # Delete choices that were in the DB but are not in the incoming data
                Choice.objects.filter(question=question).exclude(id__in=incoming_choice_ids).delete()

            # Delete questions that were in the DB but are not in the incoming data
            instance.questions.exclude(id__in=incoming_question_ids).delete()

        return instance


class VoteSerializer(serializers.ModelSerializer):
    class Meta:
        model = Vote
        fields = ['id', 'question', 'choice', 'user', 'created_at']
        read_only_fields = ['user', 'created_at']

    def validate(self, data):
        if Vote.objects.filter(question=data['question'], user=self.context['request'].user).exists():
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
