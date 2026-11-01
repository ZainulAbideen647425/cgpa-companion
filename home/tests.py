from io import StringIO

from django.contrib.auth.models import User
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse

from .models import Subject


class AuthFlowTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('alice', password='pw12345!')

    def test_login_redirects_to_calculator(self):
        r = self.client.post(reverse('login'), {'username': 'alice', 'password': 'pw12345!'})
        self.assertRedirects(r, reverse('cgpa_calculator'))

    def test_login_honours_safe_next_only(self):
        r = self.client.post(reverse('login') + '?next=/result/', {'username': 'alice', 'password': 'pw12345!'})
        self.assertRedirects(r, '/result/')
        self.client.logout()
        r = self.client.post(reverse('login') + '?next=https://evil.example/', {'username': 'alice', 'password': 'pw12345!'})
        self.assertRedirects(r, reverse('cgpa_calculator'))

    def test_wrong_password_and_unknown_user(self):
        r = self.client.post(reverse('login'), {'username': 'alice', 'password': 'bad'})
        self.assertRedirects(r, '/login/', fetch_redirect_response=False)
        r = self.client.post(reverse('login'), {'username': 'nobody', 'password': 'x'})
        self.assertRedirects(r, '/login/', fetch_redirect_response=False)

    def test_register_creates_user(self):
        r = self.client.post(reverse('register'), {'username': 'bob', 'password': 'pw12345!'})
        self.assertEqual(r.status_code, 302)
        self.assertTrue(User.objects.get(username='bob').check_password('pw12345!'))

    def test_pages_require_login(self):
        r = self.client.get(reverse('result'))
        self.assertEqual(r.status_code, 302)
        self.assertIn('/login/', r['Location'])

    def test_root_is_landing_for_visitors_and_dashboard_for_users(self):
        r = self.client.get('/')
        self.assertContains(r, 'Create a free account')
        self.assertNotContains(r, 'Total credits')
        self.assertEqual(self.client.post('/', {'name': 'x', 'credit': 1, 'grade': 'A'}).status_code, 302)
        self.assertEqual(Subject.objects.count(), 0)
        self.client.login(username='alice', password='pw12345!')
        self.assertContains(self.client.get('/'), 'Total credits')


class SubjectCrudTests(TestCase):
    def setUp(self):
        self.alice = User.objects.create_user('alice', password='pw')
        self.bob = User.objects.create_user('bob', password='pw')
        self.client.login(username='alice', password='pw')

    def test_add_subject_is_owned_by_user(self):
        self.client.post(reverse('cgpa_calculator'), {'name': 'Math', 'credit': 3, 'grade': 'A'})
        s = Subject.objects.get()
        self.assertEqual(s.user, self.alice)

    def test_cgpa_matches_legacy_formula(self):
        for n, cr, g in [('a', 3, 'S'), ('b', 3, 'A'), ('c', 2, 'B')]:
            Subject.objects.create(user=self.alice, name=n, credit=cr, grade=g)
        r = self.client.get(reverse('result'))
        self.assertEqual(str(r.context['cgpa']), '9.13')   # 9.125 rounded half-up to 2 dp
        self.assertEqual(r.context['total_credits'], 8)

    def test_empty_cgpa_is_zero(self):
        r = self.client.get(reverse('cgpa_calculator'))
        self.assertEqual(float(r.context['cgpa']), 0.0)

    def test_users_cannot_see_each_others_subjects(self):
        Subject.objects.create(user=self.bob, name='Secret', credit=3, grade='A')
        r = self.client.get(reverse('cgpa_calculator'))
        self.assertEqual(list(r.context['subjects']), [])

    def test_users_cannot_edit_or_delete_others_subjects(self):
        s = Subject.objects.create(user=self.bob, name='Secret', credit=3, grade='A')
        self.assertEqual(self.client.get(reverse('edit_subject', args=[s.id])).status_code, 404)
        self.assertEqual(self.client.post(reverse('edit_subject', args=[s.id]),
                                          {'name': 'x', 'credit': 1, 'grade': 'F'}).status_code, 404)
        self.assertEqual(self.client.get(reverse('delete_subject', args=[s.id])).status_code, 404)
        self.assertTrue(Subject.objects.filter(id=s.id).exists())

    def test_edit_and_delete_own_subject(self):
        s = Subject.objects.create(user=self.alice, name='Old', credit=3, grade='A')
        self.client.post(reverse('edit_subject', args=[s.id]), {'name': 'New', 'credit': 4, 'grade': 'B'})
        s.refresh_from_db()
        self.assertEqual((s.name, s.credit, s.grade), ('New', 4, 'B'))
        self.client.get(reverse('delete_subject', args=[s.id]))
        self.assertFalse(Subject.objects.filter(id=s.id).exists())


class LegacyAssignCommandTests(TestCase):
    def test_assigns_only_orphans(self):
        alice = User.objects.create_user('alice', password='pw')
        bob = User.objects.create_user('bob', password='pw')
        Subject.objects.create(user=None, name='old', credit=3, grade='A')
        Subject.objects.create(user=bob, name='bobs', credit=3, grade='A')
        call_command('assign_legacy_subjects', username='alice', stdout=StringIO())
        self.assertEqual(Subject.objects.get(name='old').user, alice)
        self.assertEqual(Subject.objects.get(name='bobs').user, bob)

    def test_dry_run_changes_nothing(self):
        User.objects.create_user('alice', password='pw')
        Subject.objects.create(user=None, name='old', credit=3, grade='A')
        call_command('assign_legacy_subjects', username='alice', dry_run=True, stdout=StringIO())
        self.assertIsNone(Subject.objects.get(name='old').user)


class UiSmokeTests(TestCase):
    """Templates render, extend the base layout and load the stylesheet."""

    def setUp(self):
        self.user = User.objects.create_user('alice', password='pw')

    def test_auth_pages_render(self):
        for name in ('login', 'register'):
            r = self.client.get(reverse(name))
            self.assertContains(r, 'css/app.css')
            self.assertContains(r, 'csrfmiddlewaretoken')

    def test_dashboard_shows_summary_and_empty_state(self):
        self.client.login(username='alice', password='pw')
        r = self.client.get(reverse('cgpa_calculator'))
        self.assertContains(r, 'No subjects yet')
        self.assertContains(r, 'Total credits')

    def test_dashboard_lists_subjects_with_confirm_delete(self):
        self.client.login(username='alice', password='pw')
        Subject.objects.create(user=self.user, name='Algorithms', credit=3, grade='A')
        r = self.client.get(reverse('cgpa_calculator'))
        self.assertContains(r, 'Algorithms')
        self.assertContains(r, 'data-confirm')
        self.assertContains(r, 'href="/delete/')

    def test_subject_name_is_escaped(self):
        self.client.login(username='alice', password='pw')
        Subject.objects.create(user=self.user, name='<script>x</script>', credit=3, grade='A')
        r = self.client.get(reverse('cgpa_calculator'))
        self.assertNotContains(r, '<script>x</script>')

    def test_result_page_and_edit_page_render(self):
        self.client.login(username='alice', password='pw')
        s = Subject.objects.create(user=self.user, name='Algorithms', credit=3, grade='A')
        self.assertContains(self.client.get(reverse('result')), 'Print / Save as PDF')
        self.assertContains(self.client.get(reverse('edit_subject', args=[s.id])), 'Save changes')

    def test_error_messages_use_error_style(self):
        r = self.client.post(reverse('login'), {'username': 'alice', 'password': 'bad'}, follow=True)
        self.assertContains(r, 'alert-error')
        self.assertNotContains(r, 'alert-success')
