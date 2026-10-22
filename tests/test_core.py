import unittest
from job_auto.core import classify, pay_check, country_for

class MatchingTests(unittest.TestCase):
    def test_terms(self):
        self.assertEqual(classify('Software Intern Summer 2027', 'Python SQL')[2], 'confirmed')
        self.assertIsNone(classify('Software Intern Summer 2026', 'Python'))
        self.assertIsNone(classify('Senior Software Engineer', 'Summer 2027'))
        self.assertEqual(classify('Software Intern', 'Founded in 2027')[2], 'unconfirmed')
    def test_high_school_roles_excluded(self):
        for title, description in [
            ('High School Internship, Software Engineering (Summer 2027)', ''),
            ('High-school Software Intern Summer 2027', ''),
            ('Software Intern Summer 2027', 'This role is intended for high school students.'),
            ('Software Intern Summer 2027', 'You must be currently enrolled in a secondary school.'),
            ('Software Intern Summer 2027', 'Applicants must be a high school senior.'),
        ]:
            with self.subTest(title=title, description=description):
                self.assertIsNone(classify(title, description))

    def test_university_roles_retained(self):
        for description in [
            "Currently pursuing a bachelor's degree in Computer Science.",
            'University or college students. High school diploma required.',
            'Undergraduate internship. We also run high school outreach programmes.',
        ]:
            self.assertIsNotNone(classify('Software Intern Summer 2027', description))

    def test_pay(self):
        self.assertTrue(pay_check('CAD $25 - $40 per hour', 'Canada')['eligible'])
        self.assertFalse(pay_check('$24–$50/hour', 'Canada')['eligible'])
        self.assertFalse(pay_check('$80000 per year', 'Canada')['eligible'])
        self.assertFalse(pay_check('$30/hour', None)['eligible'])
        self.assertFalse(pay_check('USD $30/hour', 'Canada')['eligible'])
        self.assertTrue(pay_check('$30 per hour', 'US')['eligible'])
    def test_country(self):
        self.assertEqual(country_for('Toronto, Ontario'), 'Canada')
        self.assertIsNone(country_for('Remote'))

class StorageTests(unittest.TestCase):
    def test_refresh_deduplicates_and_preserves_status(self):
        import tempfile
        from pathlib import Path
        from unittest.mock import patch
        from job_auto import core
        job = dict(id='test:1', title='Software Intern Summer 2027', company='test', location='Toronto, Canada', url='https://example.com/job', description='Python SQL CAD $25 - $40 per hour', published='2026-10-21')
        with tempfile.TemporaryDirectory() as directory, patch.object(core, 'DATA', Path(directory)), patch.object(core, 'fetch', return_value=iter([job])):
            core.refresh()
            with core.db() as c:
                c.execute("UPDATE jobs SET status='saved'")
            with patch.object(core, 'fetch', side_effect=lambda source: iter([job])):
                core.refresh()
            rows = core.jobs()
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]['status'], 'saved')
            self.assertTrue(rows[0]['queue_eligible'])

    def test_old_high_school_records_hidden(self):
        import tempfile
        from pathlib import Path
        from unittest.mock import patch
        from job_auto import core
        with tempfile.TemporaryDirectory() as directory, patch.object(core, 'DATA', Path(directory)):
            with core.db() as c:
                c.execute("INSERT INTO jobs(id,title,description) VALUES(?,?,?)",
                          ('old-school', 'High School Internship Summer 2027', 'Python'))
            self.assertEqual(core.jobs(), [])
            with core.db() as c:
                self.assertEqual(c.execute('SELECT COUNT(*) FROM jobs').fetchone()[0], 1)

if __name__ == '__main__':
    unittest.main()
