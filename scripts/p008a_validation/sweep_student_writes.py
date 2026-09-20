"""CLI runner for the student-path sweep.

The analysis lives in ``seminary.seminary.tests.student_write_sweep`` so the
contract test and this runner cannot drift apart.

    bench --site <site> console
    >>> from seminary.seminary.tests.student_write_sweep import report; report()
"""

from seminary.seminary.tests.student_write_sweep import report


def main():
    return report()
