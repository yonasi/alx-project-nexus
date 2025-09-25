from rest_framework import serializers
from .models import Poll, Question, Choice

class ChoiceSerializer(serializers.ModelSerializer):
    votes_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = Choice
        fields = ['id', 'choice_text', 'votes_count']


class QuestionSerializer(serializers.ModelSerializer):
    choices = ChoiceSerializer(many=True)

    class Meta:
        model = Question
        fields = ['id', 'question_text', 'choices']


class PollSerializer(serializers.ModelSerializer):
    questions = QuestionSerializer(many=True)
    # Add a write-only, optional field for confirmation of vote reset.
    confirm_reset = serializers.BooleanField(write_only=True, required=False)

    class Meta:
        model = Poll
        fields = ['id', 'poll_title', 'description', 'pub_date', 'end_date', 'questions', 'confirm_reset']


    def create(self, validated_data):
        questions_data = validated_data.pop('questions', [])
        poll = Poll.objects.create(**validated_data)
        for question_data in questions_data:
            choices_data = question_data.pop('choices', [])
            question = Question.objects.create(poll=poll, **question_data)
            for choice_data in choices_data:
                Choice.objects.create(question=question, **choice_data)
        return poll

    def update(self, instance, validated_data):
        """
        Overrides the default update method with a user confirmation check.
        If votes exist and the user has not confirmed, a ValidationError is raised.
        """
        # First, check if the poll has any votes before processing the update.
        has_votes = any(
            question.choice_set.filter(votes__gt=0).exists()
            for question in instance.question_set.all()
        )
        
        # Pop the confirmation flag from the data so it doesn't get saved to the model.
        confirm_reset = validated_data.pop('confirm_reset', False)

        # If votes exist and the user has not confirmed the reset, raise an error.
        if has_votes and not confirm_reset:
            raise serializers.ValidationError(
                {"error": "This poll has votes. To update its content, you must confirm that all"
                "votes will be reset by including 'confirm_reset': true in your request."}
            )

        instance.poll_title = validated_data.get('poll_title', instance.poll_title)
        instance.description = validated_data.get('description', instance.description)
        instance.pub_date = validated_data.get('pub_date', instance.pub_date)
        instance.end_date = validated_data.get('end_date', instance.end_date)
        instance.save()
        
        
        questions_data = validated_data.pop('questions', [])
        questions_to_keep = []
        
        for question_data in questions_data:
            question_id = question_data.get('id', None)
            
            if question_id:
                try:
                    question = Question.objects.get(id=question_id, poll=instance)
                    question.question_text = question_data.get('question_text', question.question_text)
                    question.save()
                    questions_to_keep.append(question.id)
                    
                    choices_data = question_data.pop('choices', [])
                    choices_to_keep = []
                    for choice_data in choices_data:
                        choice_id = choice_data.get('id', None)
                        
                        if choice_id:
                            try:
                                choice = Choice.objects.get(id=choice_id, question=question)
                                choice.choice_text = choice_data.get('choice_text', choice.choice_text)
                                choice.save()
                                choices_to_keep.append(choice.id)
                            except Choice.DoesNotExist:
                                Choice.objects.create(question=question, **choice_data)
                                
                        else:
                            Choice.objects.create(question=question, **choice_data)

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

        Question.objects.filter(poll=instance).exclude(id__in=questions_to_keep).delete()

        # If confirmation was provided and votes existed, reset the votes.
        if has_votes and confirm_reset:
            for question in instance.question_set.all():
                for choice in question.choice_set.all():
                    choice.votes = 0
                    choice.save()

        return instance