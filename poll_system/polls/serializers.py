from rest_framework import serializers
from .models import Poll, Question, Choice, Vote
from django.db import transaction

class ChoiceSerializer(serializers.ModelSerializer):
    """
    Serializer for the Choice model.
    The `vote_count` is now a `SerializerMethodField` that dynamically
    counts the number of `Vote` objects related to this choice.
    """
    vote_count = serializers.SerializerMethodField()

    def get_vote_count(self, obj):
        return obj.votes.count()

    class Meta:
        model = Choice
        fields = ['id', 'text', 'vote_count', 'question']
        # The 'question' field updates to link choices to questions.
        read_only_fields = ['vote_count']


class QuestionSerializer(serializers.ModelSerializer):
    """
    Serializer for the Question model, with writable nested choices.
    """
    choices = ChoiceSerializer(many=True)

    class Meta:
        model = Question
        fields = ['id', 'text', 'poll', 'choices']
        read_only_fields = ['poll']


class PollSerializer(serializers.ModelSerializer):
    """
    Main serializer for the Poll model.
    This handles nested questions and choices, and includes the vote reset
    confirmation logic.
    """
    questions = QuestionSerializer(many=True)
    created_by = serializers.CharField(read_only=True, source='created_by.username')
    confirm_reset = serializers.BooleanField(write_only=True, required=False)
    description = serializers.CharField(required=False, allow_blank=True)
    end_date = serializers.DateTimeField(required=False)


    class Meta:
        model = Poll
        fields = ['id', 'title', 'description', 'created_at', 'updated_at', 'end_date', 'created_by', 'is_active', 'questions', 'confirm_reset']
        read_only_fields = ['created_at', 'updated_at']

    @transaction.atomic
    def create(self, validated_data):
        questions_data = validated_data.pop('questions', [])
        poll = Poll.objects.create(**validated_data)
        
        for question_data in questions_data:
            choices_data = question_data.pop('choices', [])
            question = Question.objects.create(poll=poll, **question_data)
            
            for choice_data in choices_data:
                Choice.objects.create(question=question, **choice_data)

        return poll

    @transaction.atomic
    def update(self, instance, validated_data):
        has_votes = Vote.objects.filter(question__poll=instance).exists()
        confirm_reset = validated_data.pop('confirm_reset', False)

        if has_votes and not confirm_reset:
            raise serializers.ValidationError(
                {"error": "This poll has votes. To update its content, you must confirm that all votes will be reset by including 'confirm_reset': true in your request."}
            )

        # Update poll-level fields
        instance.title = validated_data.get('title', instance.title)
        instance.description = validated_data.get('description', instance.description)
        instance.end_date = validated_data.get('end_date', instance.end_date)
        instance.is_active = validated_data.get('is_active', instance.is_active)
        instance.save()
        
        # Handle the nested questions
        questions_data = validated_data.pop('questions', [])
        questions_to_keep = []
        
        for question_data in questions_data:
            question_id = question_data.get('id', None)
            
            if question_id:
                try:
                    question = Question.objects.get(id=question_id, poll=instance)
                    question.text = question_data.get('text', question.text)
                    question.save()
                    questions_to_keep.append(question.id)
                    
                    # Handle nested choices
                    choices_data = question_data.pop('choices', [])
                    choices_to_keep = []
                    for choice_data in choices_data:
                        choice_id = choice_data.get('id', None)
                        
                        if choice_id:
                            try:
                                choice = Choice.objects.get(id=choice_id, question=question)
                                choice.text = choice_data.get('text', choice.text)
                                choice.save()
                                choices_to_keep.append(choice.id)
                            except Choice.DoesNotExist:
                                Choice.objects.create(question=question, **choice_data)
                        else:
                            Choice.objects.create(question=question, **choice_data)

                    # Delete choices that are no longer in the request
                    Choice.objects.filter(question=question).exclude(id__in=choices_to_keep).delete()

                except Question.DoesNotExist:
                    question = Question.objects.create(poll=instance, **question_data)
                    questions_to_keep.append(question.id)
                    for choice_data in question_data.pop('choices', []):
                        Choice.objects.create(question=question, **choice_data)
            else:
                question = Question.objects.create(poll=instance, **question_data)
                questions_to_keep.append(question.id)
                for choice_data in question_data.pop('choices', []):
                    Choice.objects.create(question=question, **choice_data)

        # Delete questions that are no longer in the request
        Question.objects.filter(poll=instance).exclude(id__in=questions_to_keep).delete()

        # If confirmation was provided and votes existed, delete all related Vote objects.
        if has_votes and confirm_reset:
            Vote.objects.filter(question__poll=instance).delete()

        return instance


class VoteSerializer(serializers.ModelSerializer):
    """
    Serializer for the Vote model, used by the API to create new votes.
    """
    class Meta:
        model = Vote
        fields = ['id', 'question', 'choice', 'user', 'created_at']
        read_only_fields = ['user', 'created_at']

    def validate(self, data):
        """
        Custom validation to ensure the submitted choice belongs to the submitted question.
        """
        question = data['question']
        choice = data['choice']
        if choice.question != question:
            raise serializers.ValidationError('Choice does not belong to the question.')
        return data
