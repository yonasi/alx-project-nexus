from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase
from django.contrib.auth.models import User
from .models import Poll, Question, Choice, Vote

class PollAPITests(APITestCase):
    """
    Test suite for the Polls API endpoints.
    """
    def setUp(self):
        """
        Set up the test data for all tests.
        """
        self.user = User.objects.create_user(username='testuser', password='testpassword')
        self.poll = Poll.objects.create(
            title='Test Poll',
            created_by=self.user,
            is_active=True
        )
        self.question = Question.objects.create(
            poll=self.poll,
            text='What is your favorite color?'
        )
        self.choice1 = Choice.objects.create(
            question=self.question,
            text='Red'
        )
        self.choice2 = Choice.objects.create(
            question=self.question,
            text='Blue'
        )
        self.vote_url = reverse('poll-vote', kwargs={'pk': self.poll.id})
        self.poll_url = reverse('poll-list')
        self.poll_detail_url = reverse('poll-detail', kwargs={'pk': self.poll.id})
        self.client.force_authenticate(user=self.user)

    def test_create_poll_successfully(self):
        """
        Ensure we can create a new poll with nested questions and choices.
        """
        data = {
            'title': 'New Poll',
            'questions': [{
                'text': 'What is the capital of France?',
                'choices': [{'text': 'Paris'}, {'text': 'London'}]
            }]
        }
        response = self.client.post(self.poll_url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Poll.objects.count(), 2)
        self.assertEqual(Question.objects.count(), 2)
        self.assertEqual(Choice.objects.count(), 4)

    def test_update_poll_with_existing_votes_without_confirmation(self):
        """
        Ensure updating a poll with existing votes fails without confirmation.
        """
        # Create a vote on the poll to test the confirmation logic
        Vote.objects.create(
            user=self.user,
            question=self.question,
            choice=self.choice1
        )
        
        data = {'title': 'Updated Poll Title'}
        response = self.client.patch(self.poll_detail_url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('confirm_reset', response.data['error'])

    def test_update_poll_with_existing_votes_with_confirmation(self):
        """
        Ensure updating a poll with existing votes succeeds with confirmation.
        """
        # Create a vote on the poll
        Vote.objects.create(
            user=self.user,
            question=self.question,
            choice=self.choice1
        )
        
        data = {
            'title': 'Updated Poll Title',
            'confirm_reset': True,
            'questions': [{
                'text': 'A new question?',
                'choices': [{'text': 'Yes'}, {'text': 'No'}]
            }]
        }
        response = self.client.patch(self.poll_detail_url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Assert that the vote has been deleted
        self.assertEqual(Vote.objects.count(), 0)

    def test_vote_successfully(self):
        """
        Ensure a vote can be submitted successfully.
        """
        data = {'choice': self.choice1.id, 'question': self.question.id}
        response = self.client.post(self.vote_url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)
        self.assertEqual(Vote.objects.count(), 1)
        self.assertEqual(Vote.objects.first().choice, self.choice1)

    def test_vote_twice_on_same_question_fails(self):
        """
        Ensure a user cannot vote twice on the same question.
        """
        # First vote (successful)
        data = {'choice': self.choice1.id, 'question': self.question.id}
        self.client.post(self.vote_url, data, format='json')
        
        # Second vote (should fail)
        response = self.client.post(self.vote_url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
        self.assertIn('You have already voted', response.data['error'])

    def test_vote_on_nonexistent_choice_fails(self):
        """
        Ensure voting on a non-existent choice fails.
        """
        data = {'choice': 999, 'question': self.question.id}
        response = self.client.post(self.vote_url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_unauthenticated_vote_fails(self):
        """
        Ensure unauthenticated users cannot vote.
        """
        self.client.force_authenticate(user=None)
        data = {'choice': self.choice1.id, 'question': self.question.id}
        response = self.client.post(self.vote_url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
