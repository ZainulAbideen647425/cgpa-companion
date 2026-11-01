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
        for name in ('cgpa_calculator', 'result'):
            r = self.client.get(reverse(name))
            self.assertEqual(r.status_code, 302)
            self.assertIn('/login/', r['Location'])


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
