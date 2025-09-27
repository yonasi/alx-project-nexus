import pytest
from rest_framework.test import APIClient
from django.contrib.auth.models import User
from polls.models import Poll, Question, Choice, Vote
from django.urls import reverse
from django.core.cache import cache
from celery import current_app

# Set Celery to run tasks synchronously during testing
@pytest.fixture(scope='session', autouse=True)
def celery_config():
    current_app.task_always_eager = True
    current_app.task_eager_propagates = True

@pytest.fixture(autouse=True)
def clear_cache_between_tests():
    """Ensure cache is clean before each test run."""
    cache.clear()

@pytest.fixture
def api_client():
    return APIClient()

@pytest.fixture
def create_user():
    def _create_user(username, password='testpassword', email='test@example.com'):
        return User.objects.create_user(username=username, password=password, email=email)
    return _create_user

@pytest.fixture
def auth_client(api_client, create_user):
    user = create_user('testuser')
    response = api_client.post(reverse('token_obtain_pair'), {
        'username': 'testuser',
        'password': 'testpassword'
    })
    token = response.data['access']
    api_client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
    api_client.user = user  # Attach user object for convenience
    return api_client

@pytest.fixture
def poll_data():
    """Sample nested data for creating a poll."""
    return {
        "title": "Favorite Framework Poll",
        "description": "Choose your favorite web framework.",
        "is_active": True,
        "questions": [
            {
                "text": "Which framework do you prefer?",
                "choices": [
                    {"text": "Django"},
                    {"text": "Flask"},
                ]
            }
        ]
    }

@pytest.fixture
def setup_voted_poll(create_user):
    """Creates a poll, a question, two choices, and records one vote."""
    user1 = create_user('voter1', password='voterpassword')
    poll = Poll.objects.create(title="Test Vote Poll", created_by=user1)
    question = Question.objects.create(poll=poll, text="Q1")
    choice1 = Choice.objects.create(question=question, text="C1", votes_count=0)
    choice2 = Choice.objects.create(question=question, text="C2", votes_count=0)
    
    # Record vote and manually trigger the counter update (as it happens in Celery task)
    Vote.objects.create(user=user1, question=question, choice=choice1)
    choice1.votes_count += 1
    choice1.save()
    
    return {
        'poll': poll, 
        'question': question, 
        'choice1': choice1, 
        'choice2': choice2, 
        'user1': user1
    }


@pytest.mark.django_db
def test_user_registration(api_client):
    url = reverse('register')
    data = {'username': 'newuser', 'password': 'securepassword', 'email': 'a@b.com'}
    response = api_client.post(url, data, format='json')
    assert response.status_code == 201
    assert User.objects.count() == 1

@pytest.mark.django_db
def test_token_obtain_pair(api_client, create_user):
    create_user('loginuser')
    url = reverse('token_obtain_pair')
    response = api_client.post(url, {'username': 'loginuser', 'password': 'testpassword'})
    assert response.status_code == 200
    assert 'access' in response.data


@pytest.mark.django_db
def test_poll_create_nested_success(auth_client, poll_data):
    url = reverse('poll-list')
    response = auth_client.post(url, poll_data, format='json')
    
    assert response.status_code == 201
    assert Poll.objects.count() == 1
    
    poll = Poll.objects.first()
    assert poll.title == "Favorite Framework Poll"
    assert poll.questions.count() == 1
    assert poll.questions.first().choices.count() == 2


@pytest.mark.django_db
def test_poll_stats_endpoint(auth_client, setup_voted_poll):
    poll = setup_voted_poll['poll']
    
    # Add a second vote to choice2
    user2 = setup_voted_poll['choice1'].question.poll.created_by
    if user2.username == 'testuser':
        user2 = create_user('voter2', password='voterpassword') # Ensure user is different
    
    # Use the vote action which queues the task (now synchronous)
    vote_url = reverse('poll-vote', kwargs={'pk': poll.pk})
    auth_client.user = user2 # Authenticate as user2
    auth_client.post(vote_url, {'choice_id': setup_voted_poll['choice2'].id}, format='json')

    # Manually re-fetch the choice data after the (synchronous) task runs
    setup_voted_poll['choice2'].refresh_from_db()

    stats_url = reverse('poll-stats', kwargs={'pk': poll.pk})
    response = auth_client.get(stats_url)
    
    assert response.status_code == 200
    data = response.data
    
    # Check overall total
    assert data['total_votes'] == 2
    
    # Check nested structure (one question)
    assert len(data['questions']) == 1
    question_data = data['questions'][0]
    assert question_data['question_id'] == setup_voted_poll['question'].id
    assert question_data['total_question_votes'] == 2
    
    # Check choice distribution and percentages
    choices = {c['choice_id']: c for c in question_data['choices']}
    
    # Choice 1: 1 vote (50%)
    c1_data = choices[setup_voted_poll['choice1'].id]
    assert c1_data['votes_count'] == 1
    assert c1_data['percentage'] == 50.0
    
    # Choice 2: 1 vote (50%)
    c2_data = choices[setup_voted_poll['choice2'].id]
    assert c2_data['votes_count'] == 1
    assert c2_data['percentage'] == 50.0



@pytest.mark.django_db
def test_poll_update_fails_without_reset_confirmation(auth_client, setup_voted_poll):
    poll = setup_voted_poll['poll']
    url = reverse('poll-detail', kwargs={'pk': poll.pk})
    
    # Data to update (new title, but no reset_votes flag)
    update_data = {
        "title": "New Title",
        "questions": [
            {
                "id": setup_voted_poll['question'].id,
                "text": "New Question Text",
                "choices": [
                    {"id": setup_voted_poll['choice1'].id, "text": "New C1"},
                    {"text": "New Added Choice"} # Adding a choice requires reset
                ]
            }
        ]
    }
    
    response = auth_client.put(url, update_data, format='json')
    
    # Must fail with a 400 validation error
    assert response.status_code == 400
    assert 'warning' in response.data
    assert "This poll has recorded votes." in response.data['warning']
    
    # Verify no changes were made to the poll or votes
    poll.refresh_from_db()
    assert poll.title != "New Title"
    assert Vote.objects.count() == 1


@pytest.mark.django_db
def test_poll_update_succeeds_with_vote_reset(auth_client, setup_voted_poll):
    poll = setup_voted_poll['poll']
    question = setup_voted_poll['question']
    choice1 = setup_voted_poll['choice1']
    url = reverse('poll-detail', kwargs={'pk': poll.pk})
    
    # Data to update with reset confirmation
    update_data = {
        "title": "Reset Confirmed Poll",
        "reset_votes": True, # CRITICAL: The confirmation flag
        "questions": [
            {
                "id": question.id,
                "text": "The Updated Question",
                "choices": [
                    {"id": choice1.id, "text": "New Text for C1"},
                    {"text": "Totally New Choice 3"}
                ]
            }
        ]
    }
    
    response = auth_client.put(url, update_data, format='json')
    
    assert response.status_code == 200
    
    # Verify votes are reset
    assert Vote.objects.count() == 0
    choice1.refresh_from_db()
    assert choice1.votes_count == 0
    
    # Verify poll was updated and nested data changes
    poll.refresh_from_db()
    assert poll.title == "Reset Confirmed Poll"
    
    # Verify choices were updated/added
    assert question.choices.count() == 2 # C2 was deleted, C1 updated, C3 created
    assert Choice.objects.get(id=choice1.id).text == "New Text for C1"
    assert Choice.objects.filter(text="Totally New Choice 3").exists()
