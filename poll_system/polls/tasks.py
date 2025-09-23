from celery import shared_task
from .models import Choice, Vote, Question
from django.contrib.auth.models import User
from django.db import IntegrityError


@shared_task
def process_vote(question_id, choice_id, user_id):
    try:
        question = Question.objects.get(id=question_id)
        choice = Choice.objects.get(id=choice_id)
        user = User.objects.get(id=user_id)
        if choice.question != question:
            return {'error': 'Choice does not belong to the question'}
        Vote.objects.create(question=question, choice=choice, user=user)
        choice.vote_count += 1
        choice.save()
        return {'message': 'Vote recorded'}
    except IntegrityError:
        return {'error': 'User already voted on this question'}