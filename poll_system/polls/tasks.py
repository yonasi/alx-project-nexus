from celery import shared_task
from django.contrib.auth.models import User
from django.db import IntegrityError, transaction
from django.db.models import F 
from .models import Vote, Question, Choice
import logging

logger = logging.getLogger(__name__)

@shared_task
def process_vote(question_id, choice_id, user_id):
    """
    Asynchronously creates a Vote object and atomically updates the Choice's vote count.
    """
    try:
        with transaction.atomic():
            # Fetch necessary objects
            question = Question.objects.get(id=question_id)
            choice = Choice.objects.get(id=choice_id, question=question)
            user = User.objects.get(id=user_id)
            
            #  Create the Vote object (IntegrityError handles duplicates)
            Vote.objects.create(question=question, choice=choice, user=user)
            
            # Atomically increment the denormalized vote counter.
            Choice.objects.filter(id=choice_id).update(votes_count=F('votes_count') + 1)
            
            logger.info(f"Vote recorded and count updated: user {user_id}, choice {choice_id}, question {question_id}")
            return {'message': 'Vote recorded successfully'}
        
    except (Question.DoesNotExist, Choice.DoesNotExist, User.DoesNotExist) as e:
        logger.error(f"Vote creation failed (Object Missing): {str(e)}")
        return {'error': f"Vote processing failed: {str(e)}"}
        
    except IntegrityError as e:
        # Handles the unique_together constraint failure
        logger.error(f"Vote creation failed (Duplicate Vote): {str(e)}")
        return {'error': 'User already voted on this question'}