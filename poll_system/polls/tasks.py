from celery import shared_task
from .models import Vote, Question
from django.contrib.auth.models import User
from django.db import IntegrityError


@shared_task
def process_vote(question_id, choice_id, user_id):
    """
    Asynchronously creates a Vote object.
    """
    try:
        Vote.objects.create(question_id=question_id, choice_id=choice_id, user_id=user_id)
        return {'message': 'Vote recorded'}
    except IntegrityError:
        return {'error': 'User already voted on this question'}
    except Exception as e:
        return {'error': str(e)}
