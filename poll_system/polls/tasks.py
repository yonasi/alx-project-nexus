from celery import shared_task
from django.contrib.auth.models import User
from polls.models import Vote, Question, Choice
from django.db import IntegrityError
import logging

logger = logging.getLogger(__name__)

@shared_task
def process_vote(question_id, choice_id, user_id):
    """
    Asynchronously creates a Vote object.
    """
    try:
        question = Question.objects.get(id=question_id)
        choice = Choice.objects.get(id=choice_id, question=question)
        user = User.objects.get(id=user_id)
        Vote.objects.create(question=question, choice=choice, user=user)
        logger.info(f"Vote created: user {user_id}, choice {choice_id}, question {question_id}")
        return {'message': 'Vote recorded'}
    except (Question.DoesNotExist, Choice.DoesNotExist, User.DoesNotExist) as e:
        logger.error(f"Vote creation failed: {str(e)}")
        return {'error': str(e)}
    except IntegrityError as e:
        logger.error(f"Vote creation failed (duplicate vote): {str(e)}")
        return {'error': 'User already voted on this question'}