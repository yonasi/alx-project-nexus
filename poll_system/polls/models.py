from django.db import models
from django.utils import timezone

class Poll(models.Model):
    """
    Model for a Poll. A poll can have multiple questions.
    """
    poll_title = models.CharField(max_length=200)
    description = models.TextField(null=True, blank=True)
    pub_date = models.DateTimeField('date published', default=timezone.now)
    end_date = models.DateTimeField('date ended', null=True, blank=True)

    # for tracking data changes.
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.poll_title

class Question(models.Model):
    """
    Model for a Question within a Poll. A question must belong to a poll.
    """
    # Using related_name for reverse relation from Poll to its Questions.
    poll = models.ForeignKey(Poll, on_delete=models.CASCADE, related_name='questions')
    question_text = models.CharField(max_length=200)

    # for tracking data changes.
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.question_text

class Choice(models.Model):
    """
    Model for a Choice within a Question. A choice must belong to a question.
    """
    # Using related_name for reverse relation from Question to its Choices.
    question = models.ForeignKey(Question, on_delete=models.CASCADE, related_name='choices')
    choice_text = models.CharField(max_length=200)
    votes = models.IntegerField(default=0)

    # for tracking data changes.
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.choice_text