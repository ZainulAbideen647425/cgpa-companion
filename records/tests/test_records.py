from decimal import Decimal as D

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from records.models import CourseEntry, Semester
from records.services import build_overview, plan_target


def make(user, sem_name, courses, position=None):
    sem = Semester.objects.create(user=user, name=sem_name, position=position or Semester.objects.filter(user=user).count() + 1)
    for code, name, cr, grade in courses:
        CourseEntry.objects.create(semester=sem, code=code, name=name, credit_hours=cr, grade=grade)
    return sem


class ServiceTests(TestCase):
    def setUp(self):
        self.u = User.objects.create_user('a', password='pw')

    def test_semester_gpa_and_weighted_cgpa(self):
        make(self.u, 'S1', [('', 'a', 3, 'A')])                       # 9.0 over 3
        make(self.u, 'S2', [('', 'b', 1, 'F'), ('', 'c', 6, 'S')])    # 60/7
        o = build_overview(self.u)
        self.assertEqual(o['rows'][0].result.gpa, D(9))
        self.assertEqual(o['cumulative'].gpa, D(87) / D(10))
        self.assertEqual(o['rows'][0].cgpa_after.gpa, D(9))

    def test_ungraded_courses_are_excluded(self):
        make(self.u, 'S1', [('', 'a', 3, 'A'), ('', 'b', 3, '')])
        o = build_overview(self.u)
        self.assertEqual(o['cumulative'].counted_credits, D(3))

    def test_empty_user_has_zero_cgpa_and_no_chart(self):
        o = build_overview(self.u)
        self.assertEqual(o['cumulative'].gpa, D(0))
        self.assertFalse(o['chart']['has_data'])

    def test_fractional_credit_hours(self):
        make(self.u, 'S1', [('', 'lab', D('1.5'), 'A'), ('', 'th', 3, 'B')])
        self.assertEqual(build_overview(self.u)['cumulative'].counted_credits, D('4.5'))

    def test_only_own_semesters_counted(self):
        other = User.objects.create_user('b', password='pw')
        make(other, 'S1', [('', 'x', 3, 'F')])
        make(self.u, 'S1', [('', 'a', 3, 'A')])
        self.assertEqual(build_overview(self.u)['cumulative'].gpa, D(9))

    def test_chart_points_are_inside_the_plot(self):
        make(self.u, 'S1', [('', 'a', 3, 'A')])
        make(self.u, 'S2', [('', 'b', 3, 'C')])
        ch = build_overview(self.u)['chart']
        self.assertTrue(ch['multi'])
        for d in ch['dots']:
            self.assertTrue(0 <= d['x'] <= ch['width'] and 0 <= d['y'] <= ch['height'])

    def test_planner_reachable(self):
        make(self.u, 'S1', [('', 'a', 3, 'B')])                       # 8.0 over 3
        p = plan_target(self.u, D('9'), D('3'))                        # (9*6-24)/3 = 10
        self.assertEqual(p['status'], 'reachable')
        self.assertEqual(p['needed'], D('10.00'))

    def test_planner_unreachable_and_secured(self):
        make(self.u, 'S1', [('', 'a', 3, 'B')])
        self.assertEqual(plan_target(self.u, D('9.9'), D('3'))['status'], 'unreachable')
        self.assertEqual(plan_target(self.u, D('1'), D('3'))['status'], 'secured')


class ViewTests(TestCase):
    def setUp(self):
        self.a = User.objects.create_user('alice', password='pw')
        self.b = User.objects.create_user('bob', password='pw')
        self.client.login(username='alice', password='pw')

    def test_login_required(self):
        self.client.logout()
        for name in ('semester_list', 'planner'):
            r = self.client.get(reverse(name))
            self.assertEqual(r.status_code, 302)
            self.assertIn('/login/', r['Location'])

    def test_create_semester_rejects_duplicates_case_insensitively(self):
        self.client.post(reverse('semester_list'), {'name': 'Fall 2025'})
        r = self.client.post(reverse('semester_list'), {'name': 'fall 2025'})
        self.assertContains(r, 'already have a semester')
        self.assertEqual(Semester.objects.filter(user=self.a).count(), 1)

    def test_two_users_can_use_the_same_semester_name(self):
        make(self.b, 'Fall 2025', [])
        self.client.post(reverse('semester_list'), {'name': 'Fall 2025'})
        self.assertEqual(Semester.objects.filter(name='Fall 2025').count(), 2)

    def test_positions_increase(self):
        for n in ('S1', 'S2', 'S3'):
            self.client.post(reverse('semester_list'), {'name': n})
        self.assertEqual(list(Semester.objects.filter(user=self.a).values_list('position', flat=True)), [1, 2, 3])

    def test_add_edit_delete_course(self):
        sem = make(self.a, 'S1', [])
        url = reverse('semester_detail', args=[sem.pk])
        self.client.post(url, {'name': 'Algo', 'code': 'CS1', 'credit_hours': '3', 'grade': 'A'})
        c = CourseEntry.objects.get()
        self.assertContains(self.client.get(url), 'Algo')
        self.client.post(reverse('course_edit', args=[c.pk]), {'name': 'Algo 2', 'code': 'CS1', 'credit_hours': '4', 'grade': 'B'})
        c.refresh_from_db()
        self.assertEqual((c.name, c.credit_hours, c.grade), ('Algo 2', D('4.0'), 'B'))
        self.client.post(reverse('course_delete', args=[c.pk]))
        self.assertFalse(CourseEntry.objects.exists())

    def test_invalid_grade_and_credit_rejected(self):
        sem = make(self.a, 'S1', [])
        url = reverse('semester_detail', args=[sem.pk])
        self.client.post(url, {'name': 'x', 'credit_hours': '3', 'grade': 'Z'})
        self.client.post(url, {'name': 'x', 'credit_hours': '-1', 'grade': 'A'})
        self.client.post(url, {'name': 'x', 'credit_hours': '99', 'grade': 'A'})
        self.assertFalse(CourseEntry.objects.exists())

    def test_deletes_require_post(self):
        sem = make(self.a, 'S1', [('', 'a', 3, 'A')])
        c = sem.courses.get()
        self.assertEqual(self.client.get(reverse('course_delete', args=[c.pk])).status_code, 405)
        self.assertEqual(self.client.get(reverse('semester_delete', args=[sem.pk])).status_code, 405)
        self.assertTrue(CourseEntry.objects.exists())

    def test_cannot_touch_other_users_data(self):
        sem = make(self.b, 'Secret', [('', 'a', 3, 'A')])
        c = sem.courses.get()
        self.assertEqual(self.client.get(reverse('semester_detail', args=[sem.pk])).status_code, 404)
        self.assertEqual(self.client.post(reverse('semester_detail', args=[sem.pk]),
                                          {'name': 'x', 'credit_hours': '3', 'grade': 'A'}).status_code, 404)
        self.assertEqual(self.client.post(reverse('semester_delete', args=[sem.pk])).status_code, 404)
        self.assertEqual(self.client.get(reverse('course_edit', args=[c.pk])).status_code, 404)
        self.assertEqual(self.client.post(reverse('course_delete', args=[c.pk])).status_code, 404)
        self.assertEqual((Semester.objects.count(), CourseEntry.objects.count()), (1, 1))
        self.assertNotContains(self.client.get(reverse('semester_list')), 'Secret')

    def test_delete_semester_cascades(self):
        sem = make(self.a, 'S1', [('', 'a', 3, 'A')])
        self.client.post(reverse('semester_delete', args=[sem.pk]))
        self.assertEqual((Semester.objects.count(), CourseEntry.objects.count()), (0, 0))

    def test_history_page_shows_gpa_and_chart(self):
        make(self.a, 'S1', [('', 'a', 3, 'A')])
        make(self.a, 'S2', [('', 'b', 3, 'B')])
        r = self.client.get(reverse('semester_list'))
        self.assertContains(r, '<svg')
        self.assertContains(r, '8.50')

    def test_planner_page(self):
        make(self.a, 'S1', [('', 'a', 3, 'B')])
        r = self.client.get(reverse('planner'), {'target': '9', 'credits': '3'})
        self.assertContains(r, '10.00')
        r = self.client.get(reverse('planner'), {'target': '9.9', 'credits': '3'})
        self.assertContains(r, 'Not reachable')
        r = self.client.get(reverse('planner'), {'target': 'abc', 'credits': '3'})
        self.assertEqual(r.status_code, 200)
        self.assertNotContains(r, 'Not reachable')

    def test_names_are_escaped(self):
        make(self.a, '<b>x</b>', [('', '<i>y</i>', 3, 'A')])
        sem = Semester.objects.get()
        self.assertNotContains(self.client.get(reverse('semester_list')), '<b>x</b>')
        self.assertNotContains(self.client.get(reverse('semester_detail', args=[sem.pk])), '<i>y</i>')
