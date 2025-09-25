from django.test import TestCase
from rest_framework.test import APIClient
from django.contrib.auth.models import User
from .models import Poll, Question, Choice
from rest_framework_simplejwt.tokens import RefreshToken

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
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 1)

    def test_create_poll(self):
        data = {'title': 'New Poll', 'is_active': True}
        response = self.client.post('/api/v1/polls/', data, format='json')  # Fixed 'response' to 'format'
        self.assertEqual(response.status_code, 201)
        self.assertEqual(Poll.objects.count(), 2)