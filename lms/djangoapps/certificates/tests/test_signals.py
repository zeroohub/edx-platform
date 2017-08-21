"""
Unit tests for enabling self-generated certificates for self-paced courses
and disabling for instructor-paced courses.
"""
import mock

from certificates import api as certs_api
from certificates.models import \
    CertificateGenerationConfiguration, \
    CertificateWhitelist, \
    GeneratedCertificate, \
    CertificateStatuses
from openedx.core.djangoapps.signals.handlers import _listen_for_course_pacing_changed
from lms.djangoapps.grades.new.course_grade_factory import CourseGradeFactory
from lms.djangoapps.grades.tests.utils import mock_passing_grade
from lms.djangoapps.verify_student.models import SoftwareSecurePhotoVerification
from openedx.core.djangoapps.certificates.config import waffle
from openedx.core.djangoapps.self_paced.models import SelfPacedConfiguration
from student.tests.factories import CourseEnrollmentFactory, UserFactory
from xmodule.modulestore.tests.django_utils import ModuleStoreTestCase
from xmodule.modulestore.tests.factories import CourseFactory


class SelfGeneratedCertsSignalTest(ModuleStoreTestCase):
    """
    Tests for enabling/disabling self-generated certificates according to course-pacing.
    """

    def setUp(self):
        super(SelfGeneratedCertsSignalTest, self).setUp()
        SelfPacedConfiguration(enabled=True).save()
        self.course = CourseFactory.create(self_paced=True)
        # Enable the feature
        CertificateGenerationConfiguration.objects.create(enabled=True)

    def test_cert_generation_flag_on_pacing_toggle(self):
        """
        Verify that signal enables or disables self-generated certificates
        according to course-pacing.
        """
        #self-generation of cert disables by default
        self.assertFalse(certs_api.cert_generation_enabled(self.course.id))

        _listen_for_course_pacing_changed('store', self.course.id, self.course.self_paced)
        #verify that self-generation of cert is enabled for self-paced course
        self.assertTrue(certs_api.cert_generation_enabled(self.course.id))

        self.course.self_paced = False
        self.store.update_item(self.course, self.user.id)

        _listen_for_course_pacing_changed('store', self.course.id, self.course.self_paced)
        # verify that self-generation of cert is disabled for instructor-paced course
        self.assertFalse(certs_api.cert_generation_enabled(self.course.id))


class WhitelistGeneratedCertificatesTest(ModuleStoreTestCase):
    """
    Tests for whitelisted student auto-certificate generation
    """
    def setUp(self):
        super(WhitelistGeneratedCertificatesTest, self).setUp()
        self.course = CourseFactory.create(self_paced=True)
        self.user = UserFactory.create()
        CourseEnrollmentFactory(
            user=self.user,
            course_id=self.course.id,
            is_active=True,
            mode="verified",
        )
        self.ip_course = CourseFactory.create(self_paced=False)
        CourseEnrollmentFactory(
            user=self.user,
            course_id=self.ip_course.id,
            is_active=True,
            mode="verified",
        )

    def test_cert_generation_on_whitelist_append_self_paced(self):
        """
        Verify that signal is sent, received, and fires task
        based on 'SELF_PACED_ONLY' flag
        """
        with mock.patch(
            'lms.djangoapps.certificates.signals.generate_certificate.apply_async',
            return_value=None
        ) as mock_generate_certificate_apply_async:
            with waffle.waffle().override(waffle.SELF_PACED_ONLY, active=False):
                CertificateWhitelist.objects.create(
                    user=self.user,
                    course_id=self.course.id
                )
                mock_generate_certificate_apply_async.assert_not_called()
            with waffle.waffle().override(waffle.SELF_PACED_ONLY, active=True):
                CertificateWhitelist.objects.create(
                    user=self.user,
                    course_id=self.course.id
                )
                mock_generate_certificate_apply_async.assert_called_with(kwargs={
                    'student': unicode(self.user.id),
                    'course_key': unicode(self.course.id),
                })

    def test_cert_generation_on_whitelist_append_instructor_paced(self):
        """
        Verify that signal is sent, received, and fires task
        based on 'INSTRUCTOR_PACED_ONLY' flag
        """
        with mock.patch(
                'lms.djangoapps.certificates.signals.generate_certificate.apply_async',
                return_value=None
        ) as mock_generate_certificate_apply_async:
            with waffle.waffle().override(waffle.INSTRUCTOR_PACED_ONLY, active=False):
                CertificateWhitelist.objects.create(
                    user=self.user,
                    course_id=self.ip_course.id
                )
                mock_generate_certificate_apply_async.assert_not_called()
            with waffle.waffle().override(waffle.INSTRUCTOR_PACED_ONLY, active=True):
                CertificateWhitelist.objects.create(
                    user=self.user,
                    course_id=self.ip_course.id
                )
                mock_generate_certificate_apply_async.assert_called_with(kwargs={
                    'student': unicode(self.user.id),
                    'course_key': unicode(self.ip_course.id),
                })


class PassingGradeCertsTest(ModuleStoreTestCase):
    """
    Tests for certificate generation task firing on passing grade receipt
    """
    def setUp(self):
        super(PassingGradeCertsTest, self).setUp()
        self.course = CourseFactory.create(
            self_paced=True,
        )
        self.user = UserFactory.create()
        self.enrollment = CourseEnrollmentFactory(
            user=self.user,
            course_id=self.course.id,
            is_active=True,
            mode="verified",
        )
        self.ip_course = CourseFactory.create(self_paced=False)
        self.ip_enrollment = CourseEnrollmentFactory(
            user=self.user,
            course_id=self.ip_course.id,
            is_active=True,
            mode="verified",
        )
        attempt = SoftwareSecurePhotoVerification.objects.create(
            user=self.user,
            status='submitted'
        )
        attempt.approve()

    def test_cert_generation_on_passing_self_paced(self):
        with mock.patch(
            'lms.djangoapps.certificates.signals.generate_certificate.apply_async',
            return_value=None
        ) as mock_generate_certificate_apply_async:
            with waffle.waffle().override(waffle.SELF_PACED_ONLY, active=True):
                grade_factory = CourseGradeFactory()
                # Not passing
                grade_factory.update(self.user, self.course)
                mock_generate_certificate_apply_async.assert_not_called()
                # Certs fired after passing
                with mock_passing_grade():
                    grade_factory.update(self.user, self.course)
                    mock_generate_certificate_apply_async.assert_called_with(kwargs={
                        'student': unicode(self.user.id),
                        'course_key': unicode(self.course.id),
                    })

    def test_cert_generation_on_passing_instructor_paced(self):
        with mock.patch(
            'lms.djangoapps.certificates.signals.generate_certificate.apply_async',
            return_value=None
        ) as mock_generate_certificate_apply_async:
            with waffle.waffle().override(waffle.INSTRUCTOR_PACED_ONLY, active=True):
                grade_factory = CourseGradeFactory()
                # Not passing
                grade_factory.update(self.user, self.ip_course)
                mock_generate_certificate_apply_async.assert_not_called()
                # Certs fired after passing
                with mock_passing_grade():
                    grade_factory.update(self.user, self.ip_course)
                    mock_generate_certificate_apply_async.assert_called_with(kwargs={
                        'student': unicode(self.user.id),
                        'course_key': unicode(self.ip_course.id),
                    })

    def test_cert_already_generated(self):
        with mock.patch(
                'lms.djangoapps.certificates.signals.generate_certificate.apply_async',
                return_value=None
        ) as mock_generate_certificate_apply_async:
            grade_factory = CourseGradeFactory()
            # Create the certificate
            GeneratedCertificate.eligible_certificates.create(
                user=self.user,
                course_id=self.course.id,
                status=CertificateStatuses.downloadable
            )
            # Certs are not re-fired after passing
            with mock_passing_grade():
                grade_factory.update(self.user, self.course)
                mock_generate_certificate_apply_async.assert_not_called()


class LearnerTrackChangeCertsTest(ModuleStoreTestCase):
    """
    Tests for certificate generation task firing on learner verification
    """
    def setUp(self):
        super(LearnerTrackChangeCertsTest, self).setUp()
        self.course_one = CourseFactory.create(self_paced=True)
        self.user_one = UserFactory.create()
        self.enrollment_one = CourseEnrollmentFactory(
            user=self.user_one,
            course_id=self.course_one.id,
            is_active=True,
            mode='verified',
        )
        self.user_two = UserFactory.create()
        self.course_two = CourseFactory.create(self_paced=False)
        self.enrollment_two = CourseEnrollmentFactory(
            user=self.user_two,
            course_id=self.course_two.id,
            is_active=True,
            mode='verified'
        )
        with mock_passing_grade():
            grade_factory = CourseGradeFactory()
            grade_factory.update(self.user_one, self.course_one)
            grade_factory.update(self.user_two, self.course_two)

    def test_cert_generation_on_photo_verification_self_paced(self):
        with mock.patch(
            'lms.djangoapps.certificates.signals.generate_certificate.apply_async',
            return_value=None
        ) as mock_generate_certificate_apply_async:
            with waffle.waffle().override(waffle.SELF_PACED_ONLY, active=True):
                mock_generate_certificate_apply_async.assert_not_called()
                attempt = SoftwareSecurePhotoVerification.objects.create(
                    user=self.user_one,
                    status='submitted'
                )
                attempt.approve()
                mock_generate_certificate_apply_async.assert_called_with(kwargs={
                    'student': unicode(self.user_one.id),
                    'course_key': unicode(self.course_one.id),
                })

    def test_cert_generation_on_photo_verification_instructor_paced(self):
        with mock.patch(
            'lms.djangoapps.certificates.signals.generate_certificate.apply_async',
            return_value=None
        ) as mock_generate_certificate_apply_async:
            with waffle.waffle().override(waffle.INSTRUCTOR_PACED_ONLY, active=True):
                mock_generate_certificate_apply_async.assert_not_called()
                attempt = SoftwareSecurePhotoVerification.objects.create(
                    user=self.user_two,
                    status='submitted'
                )
                attempt.approve()
                mock_generate_certificate_apply_async.assert_called_with(kwargs={
                    'student': unicode(self.user_two.id),
                    'course_key': unicode(self.course_two.id),
                })
