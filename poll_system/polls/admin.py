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
    # Ensure denormalized field is read-only in inline forms
    readonly_fields = ('votes_count',)
    show_change_link = True

@admin.register(Poll)
class PollAdmin(admin.ModelAdmin):
    list_display = ('title', 'created_by', 'created_at', 'is_active', 'end_date')
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
    # Use the efficient, denormalized model field 'votes_count' directly
    list_display = ('text', 'question', 'votes_count')
    list_filter = ('question',)
    # Ensure the denormalized field cannot be accidentally modified
    readonly_fields = ('votes_count',) 
    
@admin.register(Vote)
class VoteAdmin(admin.ModelAdmin):
    list_display = ('choice', 'question', 'user', 'created_at')
    list_filter = ('created_at', 'user')
    search_fields = ('user__username', 'choice__text')