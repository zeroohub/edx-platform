"""
Signal handler for enabling/disabling self-generated certificates based on the course-pacing.
"""
import logging

from django.db.models.signals import post_save
from django.dispatch import receiver

from certificates.models import (
    CertificateGenerationCourseSetting,
    CertificateWhitelist,
    CertificateStatuses,
    GeneratedCertificate
)
from certificates.tasks import generate_certificate
from courseware import courses
from lms.djangoapps.grades.new.course_grade_factory import CourseGradeFactory
from openedx.core.djangoapps.certificates.config import waffle
from openedx.core.djangoapps.signals.signals import COURSE_GRADE_NOW_PASSED, LEARNER_NOW_VERIFIED
from student.models import CourseEnrollment


log = logging.getLogger(__name__)


@receiver(post_save, sender=CertificateWhitelist, dispatch_uid="append_certificate_whitelist")
def _listen_for_certificate_whitelist_append(sender, instance, **kwargs):  # pylint: disable=unused-argument
    switches = waffle.waffle()
    # No flags enabled
    if (
        not switches.is_enabled(waffle.SELF_PACED_ONLY) and
        not switches.is_enabled(waffle.INSTRUCTOR_PACED_ONLY)
    ):
        return

    if courses.get_course_by_id(instance.course_id, depth=0).self_paced:
        if not switches.is_enabled(waffle.SELF_PACED_ONLY):
            return
    else:
        if not switches.is_enabled(waffle.INSTRUCTOR_PACED_ONLY):
            return

    fire_ungenerated_certificate_task(instance.user, instance.course_id)
    log.info(u'Certificate generation task initiated for {user} : {course} via whitelist'.format(
        user=instance.user.id,
        course=instance.course_id
    ))


@receiver(COURSE_GRADE_NOW_PASSED, dispatch_uid="new_passing_learner")
def _listen_for_passing_grade(sender, user, course_id, **kwargs):  # pylint: disable=unused-argument
    """
    Listen for a learner passing a course, send cert generation task,
    downstream signal from COURSE_GRADE_CHANGED
    """
    # No flags enabled
    if (
        not waffle.waffle().is_enabled(waffle.SELF_PACED_ONLY) and
        not waffle.waffle().is_enabled(waffle.INSTRUCTOR_PACED_ONLY)
    ):
        return

    if courses.get_course_by_id(course_id, depth=0).self_paced:
        if not waffle.waffle().is_enabled(waffle.SELF_PACED_ONLY):
            return
    else:
        if not waffle.waffle().is_enabled(waffle.INSTRUCTOR_PACED_ONLY):
            return

    if fire_ungenerated_certificate_task(user, course_id):
        log.info(u'Certificate generation task initiated for {user} : {course} via passing grade'.format(
            user=user.id,
            course=course_id
        ))


@receiver(LEARNER_NOW_VERIFIED, dispatch_uid="learner_track_changed")
def _listen_for_track_change(sender, user, **kwargs):  # pylint: disable=unused-argument
    """
    Catches a track change signal, determines user status,
    calls fire_ungenerated_certificate_task for passing grades
    """
    if (
        not waffle.waffle().is_enabled(waffle.SELF_PACED_ONLY) and
        not waffle.waffle().is_enabled(waffle.INSTRUCTOR_PACED_ONLY)
    ):
        return
    user_enrollments = CourseEnrollment.enrollments_for_user(user=user)
    grade_factory = CourseGradeFactory()
    for enrollment in user_enrollments:
        if grade_factory.read(user=user, course=enrollment.course).passed:
            if fire_ungenerated_certificate_task(user, enrollment.course.id):
                log.info(u'Certificate generation task initiated for {user} : {course} via track change'.format(
                    user=user.id,
                    course=enrollment.course.id
                ))


def fire_ungenerated_certificate_task(user, course_key):
    """
    Helper function to fire un-generated certificate tasks
    There's an additional query (repeated in the GeneratedCertificate model) that is repeated here,
    in an attempt to reduce traffic to the queue to verified learners only.

    If the learner is verified and their cert has the 'unverified' status,
    we regenerate the cert.g
    """
    enrollment_mode, __ = CourseEnrollment.enrollment_mode_for_user(user, course_key)
    mode_is_verified = enrollment_mode in GeneratedCertificate.VERIFIED_CERTS_MODES
    cert = GeneratedCertificate.certificate_for_student(user, course_key)
    if mode_is_verified and (cert is None or cert.status == 'unverified'):
        generate_certificate.apply_async(kwargs={
            'student': unicode(user.id),
            'course_key': unicode(course_key),
        })
        return True
