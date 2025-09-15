from django.contrib import admin
from .models import Poll, Question, Choice, Vote

admin.site.register(Poll)
admin.site.register(Question)
admin.site.register(Choice)
admin.site.register(Vote)