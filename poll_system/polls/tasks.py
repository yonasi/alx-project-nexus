from celery import shared_task
from django.contrib.auth.models import User
from django.db import IntegrityError, transaction
# Import F for performing atomic database operations
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
        # Explicitly cast IDs to integers for robust lookup
        q_id = int(question_id)
        c_id = int(choice_id)
        u_id = int(user_id)
        
        with transaction.atomic():
            #Fetch necessary objects using the sanitized IDs
            question = Question.objects.get(id=q_id)
            choice = Choice.objects.get(id=c_id, question=question)
            user = User.objects.get(id=u_id)
            
            # Create the Vote object (IntegrityError handles duplicates)
            Vote.objects.create(question=question, choice=choice, user=user)
            
            # tomically increment the denormalized vote counter.
            Choice.objects.filter(id=c_id).update(votes_count=F('votes_count') + 1)
            
            logger.info(f"Vote recorded and count updated: user {u_id}, choice {c_id}, question {q_id}")
            return {'message': 'Vote recorded successfully'}
        
    except (Question.DoesNotExist, Choice.DoesNotExist, User.DoesNotExist) as e:
        logger.error(f"Vote creation failed (Object Missing, ID check needed): {str(e)} - Args: QID={question_id}, CID={choice_id}, UID={user_id}")
        return {'error': f"Vote processing failed: {str(e)}"}
        
    except IntegrityError as e:
        # Handles the unique_together constraint failure
        logger.error(f"Vote creation failed (Duplicate Vote): {str(e)}")
        return {'error': 'User already voted on this question'}
