from django.test import TestCase
from rest_framework.test import APIClient
from django.contrib.auth.models import User
from .models import Poll, Question, Choice, Vote
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework import status

class PollAPITestCase(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(username='testuser', password='testpass')
        # Obtain JWT token
        self.token = RefreshToken.for_user(self.user).access_token
        # Log in the client with the token
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.token}')
        self.poll = Poll.objects.create(title='Test Poll', created_by=self.user)
        self.question = Question.objects.create(poll=self.poll, text='Test Question')
        self.choice = Choice.objects.create(question=self.question, text='Option 1')

    def test_list_polls(self):
        response = self.client.get('/api/v1/polls/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['title'], 'Test Poll')

    def test_create_poll(self):
        data = {'title': 'New Poll', 'is_active': True}
        response = self.client.post('/api/v1/polls/', data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Poll.objects.count(), 2)
        self.assertEqual(Poll.objects.last().title, 'New Poll')

    def test_retrieve_poll(self):
        response = self.client.get(f'/api/v1/polls/{self.poll.id}/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['title'], 'Test Poll')
        self.assertEqual(len(response.data['questions']), 1)

    def test_vote_poll(self):
        data = {'choice_id': self.choice.id}
        response = self.client.post(f'/api/v1/polls/{self.poll.id}/vote/', data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Choice.objects.get(id=self.choice.id).vote_count, 1)
        self.assertEqual(Vote.objects.count(), 1)

    def test_vote_unauthorized(self):
        self.client.credentials()  # Remove token
        data = {'choice_id': self.choice.id}
        response = self.client.post(f'/api/v1/polls/{self.poll.id}/vote/', data, format='json')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_vote_invalid_choice(self):
        data = {'choice_id': 999}  # Non-existent choice
        response = self.client.post(f'/api/v1/polls/{self.poll.id}/vote/', data, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)