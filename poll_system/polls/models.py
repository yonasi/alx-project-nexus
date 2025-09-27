from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from django.db.models import Count


class Poll(models.Model):
    """
    Model for a Poll, including ownership, activity status, and timestamps.
    """
    title = models.CharField(max_length=200)
    description = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    end_date = models.DateTimeField('date ended', null=True, blank=True)
    created_by = models.ForeignKey(User, on_delete=models.CASCADE)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.title


class Question(models.Model):
    """
    A question belonging to a poll.
    """
    poll = models.ForeignKey(Poll, on_delete=models.CASCADE, related_name='questions')
    text = models.CharField(max_length=600)

    def __str__(self):
        return self.text


class Choice(models.Model):
    """
    A choice for a question.
    """
    question = models.ForeignKey(Question, on_delete=models.CASCADE, related_name='choices')
    text = models.CharField(max_length=300)

    
    def __str__(self):
        return self.text
    

    @property
    def vote_count(self):
        return self.votes.count()


class Vote(models.Model):
    """
    Tracks a single vote by a user for a choice on a question.
    The unique_together constraint ensures a user can only vote once per question.
    """
    question = models.ForeignKey(Question, on_delete=models.CASCADE)
    choice = models.ForeignKey(Choice, on_delete=models.CASCADE, related_name='votes')
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('question', 'user')
