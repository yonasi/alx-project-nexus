from django.test import TestCase
from rest_framework.test import APIClient
from django.contrib.auth.models import User
from rest_framework_simplejwt.tokens import RefreshToken
from polls.models import Poll, Question, Choice, Vote
from rest_framework import status
import time

class PollAPITestCase(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(username='testuser', password='testpass')
        self.token = RefreshToken.for_user(self.user).access_token
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.token}')
        self.poll = Poll.objects.create(title='Test Poll', created_by=self.user)
        self.question = Question.objects.create(poll=self.poll, text='Test Question')
        self.choice1 = Choice.objects.create(question=self.question, text='Option 1')
        self.choice2 = Choice.objects.create(question=self.question, text='Option 2')
        # Create a vote for testing stats
        Vote.objects.create(question=self.question, choice=self.choice1, user=self.user)

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
        data = {'choice_id': self.choice2.id}
        response = self.client.post(f'/api/v1/polls/{self.poll.id}/vote/', data, format='json')
        self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)
        time.sleep(2)  # Wait for Celery task
        self.assertEqual(Choice.objects.get(id=self.choice2.id).vote_count, 1)
        self.assertEqual(Vote.objects.count(), 2)
        self.assertEqual(Vote.objects.filter(choice=self.choice2, user=self.user).count(), 1)

    def test_vote_unauthorized(self):
        self.client.credentials()
        data = {'choice_id': self.choice1.id}
        response = self.client.post(f'/api/v1/polls/{self.poll.id}/vote/', data, format='json')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_vote_invalid_choice(self):
        data = {'choice_id': 999}
        response = self.client.post(f'/api/v1/polls/{self.poll.id}/vote/', data, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_register_user(self):
        data = {
            'username': 'newuser',
            'email': 'newuser@example.com',
            'password': 'newpass123'
        }
        response = self.client.post('/api/v1/register/', data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(User.objects.count(), 2)
        self.assertEqual(response.data['username'], 'newuser')

    def test_register_duplicate_username(self):
        data = {
            'username': 'testuser',
            'email': 'another@example.com',
            'password': 'newpass123'
        }
        response = self.client.post('/api/v1/register/', data, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('username', response.data)

    def test_change_password(self):
        data = {
            'old_password': 'testpass',
            'new_password': 'newtestpass123'
        }
        response = self.client.post('/api/v1/change-password/', data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password('newtestpass123'))

    def test_change_password_invalid_old_password(self):
        data = {
            'old_password': 'wrongpass',
            'new_password': 'newtestpass123'
        }
        response = self.client.post('/api/v1/change-password/', data, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('error', response.data)

    def test_stats_endpoint(self):
        response = self.client.get(f'/api/v1/polls/{self.poll.id}/stats/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['total_votes'], 1)
        self.assertEqual(response.data['top_choice'], 'Option 1')
        self.assertEqual(response.data['vote_distribution'], {'Option 1': 1, 'Option 2': 0})