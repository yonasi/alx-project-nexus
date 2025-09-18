from django.contrib import admin
from .models import Poll, Question, Choice, Vote

# Inline for Questions in Poll admin
class QuestionInline(admin.TabularInline):
    model = Question
    extra = 1  # Number of empty question forms to display
    show_change_link = True

# Inline for Choices in Question admin
class ChoiceInline(admin.TabularInline):
    model = Choice
    extra = 2  
    show_change_link = True

@admin.register(Poll)
class PollAdmin(admin.ModelAdmin):
    list_display = ('title', 'created_by', 'created_at', 'is_active')
    list_filter = ('is_active', 'created_at')
    search_fields = ('title',)
    inlines = [QuestionInline]  # Display questions under each poll

@admin.register(Question)
class QuestionAdmin(admin.ModelAdmin):
    list_display = ('text', 'poll')
    search_fields = ('text',)
    inlines = [ChoiceInline]  # Display choices under each question

@admin.register(Choice)
class ChoiceAdmin(admin.ModelAdmin):
    list_display = ('text', 'question', 'vote_count')
    list_filter = ('question',)

@admin.register(Vote)
class VoteAdmin(admin.ModelAdmin):
    list_display = ('choice', 'user', 'created_at')