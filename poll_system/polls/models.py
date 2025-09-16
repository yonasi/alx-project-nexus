from django.db import models
from django.contrib.auth.models import User


class Poll(models.Model):
    title = models.CharField(max_length=200)
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(User, on_delete=models.CASCADE)
    is_active = models.BooleanField(default=True)


    def __str__(self):
        return self.title


class Question(models.Model):
    poll = models.ForeignKey(Poll, on_delete=models.CASCADE, related_name='questions')
    text = models.CharField(max_length=600)


    def __str__(self):
        return self.text


class Choice(models.Model):
    question = models.ForeignKey(Question, on_delete=models.CASCADE, related_name='choices')
    text = models.CharField(max_length=300)
    vote_count = models.IntegerField(default=0)


    def __str__(self):
        return self.text


class Vote(models.Model):
    question = models.ForeignKey(Question, on_delete=models.CASCADE, related_name='votes')
    choice = models.ForeignKey(Choice, on_delete=models.CASCADE)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)


    class Meta:
        unique_together = ('question', 'user')  # Preventing multiple choices for a user