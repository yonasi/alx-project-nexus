from django.contrib import admin
from .models import Poll, Question, Choice, Vote

@admin.register(Poll)
class PollAdmin(admin.ModelAdmin):
    list_display = ('title', 'created_at', 'is_active')
    list_filter = ('is_active', 'created_at')
    search_fields = ('title',)


@admin.register(Question)
class QuestionAdmin(admin.ModelAdmin):
    list_display = ('text', 'poll')
    search_fields = ('text',)


@admin.register(Choice)
class ChoiceAdmin(admin.ModelAdmin):
    list_display = ('text', 'question', 'vote_count')
    list_filter = ('question',)


@admin.register(Vote)
class VoteAdmin(admin.ModelAdmin):
    list_display = ('choice', 'user', 'created_at')