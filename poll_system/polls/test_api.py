# This file contains API tests for the poll management endpoints, specifically
# focusing on nested data creation, updates, and the vote reset logic.

import pytest
from rest_framework.test import APITestCase
from rest_framework import status
from django.urls import reverse
from django.utils import timezone
import time

from polls.models import Poll, Question, Choice

@pytest.fixture
def poll_data():
    """
    Fixture to provide sample nested data for creating a new poll.
    """
    return {
        "poll_title": "Favorite Programming Language",
        "description": "Vote for your most-used language!",
        "questions": [
            {
                "question_text": "Which language do you prefer?",
                "choices": [
                    {"choice_text": "Python"},
                    {"choice_text": "JavaScript"},
                    {"choice_text": "Rust"},
                ]
            }
        ]
    }

@pytest.fixture
def existing_poll_with_votes(db):
    """
    Fixture to create an existing poll with questions, choices, and votes.
    This is used to test the update with vote reset confirmation.
    """
    poll = Poll.objects.create(
        poll_title="Favorite Pet",
        description="Vote for your favorite pet!",
        pub_date=timezone.now()
    )
    question = Question.objects.create(
        poll=poll,
        question_text="Which pet do you like best?"
    )
    # The first choice will have votes, the others will not.
    Choice.objects.create(question=question, choice_text="Dog", votes=5)
    Choice.objects.create(question=question, choice_text="Cat", votes=0)
    Choice.objects.create(question=question, choice_text="Fish", votes=0)
    return poll


class PollManagementTests(APITestCase):
    """
    Test suite for the Poll management API endpoints.
    """
    def test_create_poll_with_nested_data(self, poll_data):
        """
        Test that a new poll can be created successfully with nested questions and choices.
        """
        url = reverse('poll-list')
        response = self.client.post(url, poll_data, format='json')

        # Assert that the creation was successful (HTTP 201 CREATED)
        assert response.status_code == status.HTTP_201_CREATED
        
        # Assert that the objects were created in the database
        assert Poll.objects.count() == 1
        assert Question.objects.count() == 1
        assert Choice.objects.count() == 3

        # Assert that the returned data matches the expected structure
        assert response.data['poll_title'] == "Favorite Programming Language"
        assert len(response.data['questions']) == 1
        assert len(response.data['questions'][0]['choices']) == 3

    def test_update_poll_with_nested_data(self, existing_poll_with_votes):
        """
        Test that an existing poll's nested data can be updated correctly
        (assumes no votes for this test).
        """
        # Create a clean poll without votes for this test
        poll = Poll.objects.create(
            poll_title="Test Update Poll",
            description="Initial description",
            pub_date=timezone.now()
        )
        question = Question.objects.create(
            poll=poll,
            question_text="What's your favorite color?"
        )
        choice_one = Choice.objects.create(question=question, choice_text="Red")
        
        # Data for the update: change poll title, update an existing choice, and add a new choice.
        updated_data = {
            "poll_title": "Updated Poll Title",
            "questions": [
                {
                    "id": question.id,
                    "question_text": "What's your favorite color?",
                    "choices": [
                        {"id": choice_one.id, "choice_text": "Crimson"},  # Update existing choice
                        {"choice_text": "Blue"},  # Add new choice
                    ]
                }
            ]
        }
        url = reverse('poll-detail', args=[poll.id])
        response = self.client.put(url, updated_data, format='json')
        
        assert response.status_code == status.HTTP_200_OK
        
        # Assert that the poll title was updated
        poll.refresh_from_db()
        assert poll.poll_title == "Updated Poll Title"
        
        # Assert that the choice was updated
        choice_one.refresh_from_db()
        assert choice_one.choice_text == "Crimson"
        
        # Assert that a new choice was added
        assert Choice.objects.count() == 2

    def test_update_poll_with_votes_without_confirmation_fails(self, existing_poll_with_votes):
        """
        Test that updating a poll with votes fails if `confirm_reset` is not provided.
        """
        poll = existing_poll_with_votes
        url = reverse('poll-detail', args=[poll.id])

        # Prepare data with a change, but no confirmation flag
        updated_data = {
            "poll_title": "Updated Poll Title",
        }
        response = self.client.patch(url, updated_data, format='json')

        # Assert that the request was a bad request (HTTP 400)
        assert response.status_code == status.HTTP_400_BAD_REQUEST

        # Assert the error message is what we expect
        assert "To update its content, you must confirm that all votes will be reset" in response.data['error']

        # Assert that the votes were NOT reset
        choice = Choice.objects.get(choice_text="Dog")
        assert choice.votes == 5

    def test_update_poll_with_votes_with_confirmation_succeeds(self, existing_poll_with_votes):
        """
        Test that updating a poll with votes succeeds when `confirm_reset` is provided,
        and that the votes are reset.
        """
        poll = existing_poll_with_votes
        url = reverse('poll-detail', args=[poll.id])
        
        # Prepare data with a change and the confirmation flag
        updated_data = {
            "poll_title": "Updated Poll Title",
            "confirm_reset": True,
        }
        response = self.client.patch(url, updated_data, format='json')

        # Assert that the request was successful
        assert response.status_code == status.HTTP_200_OK

        # Assert that the votes were correctly reset to 0
        choice = Choice.objects.get(choice_text="Dog")
        assert choice.votes == 0

    def test_delete_poll_removes_nested_objects(self, existing_poll_with_votes):
        """
        Test that deleting a poll also deletes all its associated questions and choices
        due to CASCADE on delete.
        """
        poll = existing_poll_with_votes
        question_id = poll.questions.first().id
        choice_ids = list(poll.questions.first().choices.values_list('id', flat=True))
        
        url = reverse('poll-detail', args=[poll.id])
        response = self.client.delete(url)
        
        assert response.status_code == status.HTTP_204_NO_CONTENT
        
        # Assert the poll and its related objects are gone from the database
        assert not Poll.objects.filter(id=poll.id).exists()
        assert not Question.objects.filter(id=question_id).exists()
        for choice_id in choice_ids:
            assert not Choice.objects.filter(id=choice_id).exists()

    def test_updated_at_field_is_updated_on_save(self, db):
        """
        Test that the `updated_at` field is correctly updated on subsequent saves.
        """
        poll = Poll.objects.create(poll_title="Test Updated At")
        original_updated_at = poll.updated_at
        
        # Wait a small amount of time to ensure a different timestamp
        time.sleep(0.1)
        
        # Update and save the poll instance
        poll.poll_title = "New Title"
        poll.save()
        
        # Assert that the `updated_at` field has been updated
        assert poll.updated_at > original_updated_at
        
        # Assert that the `created_at` field has not changed
        assert poll.created_at == original_updated_at
