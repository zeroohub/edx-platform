from __future__ import print_function

import datetime
import logging
import pytz

from celery import task
from django.core.management.base import BaseCommand
from django.conf import settings
from django.core.urlresolvers import reverse

from openedx.core.djangoapps.schedules.models import Schedule

from edx_ace.message import MessageType
from edx_ace.recipient_resolver import RecipientResolver
from edx_ace import ace
from edx_ace.recipient import Recipient


LOG = logging.getLogger(__name__)


class RecurringNudge(MessageType):
    def __init__(self, week, *args, **kwargs):
        super(RecurringNudge, self).__init__(*args, **kwargs)
        self.name = "recurringnudge_week{}".format(week)


class ScheduleStartResolver(RecipientResolver):
    def __init__(self, current_date):
        self.current_date = current_date.replace(hour=0, minute=0, second=0)

    def send(self, week):
        target_date = self.current_date - datetime.timedelta(days=week * 7)
        for hour in range(24):
            for minute in range(60):
                target_minute = target_date + datetime.timedelta(hours=hour) + datetime.timedelta(minutes=minute)
                _schedule_minute.delay(week, target_minute)


@task
def _schedule_minute(week, target_time):
    msg_type = RecurringNudge(week)

    for (user, language, context) in _schedules_for_minute(target_time):
        msg = msg_type.personalize(
            Recipient(
                user.username,
                user.email,
            ),
            language,
            context,
        )
        _schedule_send.delay(msg)


@task
def _schedule_send(msg):
    try:
        ace.send(msg)
    except Exception as exc:
        LOG.exception('Unable to send message')
        raise


def _schedules_for_minute(target_time):
    schedules = Schedule.objects.select_related(
        'enrollment__user__profile',
        'enrollment__course',
    ).filter(
        start__gte=target_time,
        start__lt=target_time + datetime.timedelta(seconds=60),
    )

    for schedule in schedules:
        enrollment = schedule.enrollment
        user = enrollment.user

        course_id_str = str(enrollment.course_id)
        course = enrollment.course

        course_root = reverse('course_root', kwargs={'course_id': course_id_str})

        def absolute_url(relative_path):
            return u'{}{}'.format(settings.LMS_ROOT_URL, relative_path)

        template_context = {
            'student_name': user.profile.name,
            'course_name': course.display_name,
            'course_url': absolute_url(course_root),
        }

        yield (user, course.language, template_context)


class Command(BaseCommand):

    def add_arguments(self, parser):
        parser.add_argument('--date', default=datetime.datetime.utcnow().date().isoformat())

    def handle(self, *args, **options):
        current_date = datetime.datetime(
            *[int(x) for x in options['date'].split('-')],
            tzinfo=pytz.UTC
        )
        resolver = ScheduleStartResolver(current_date)
        for week in (1, 2, 3, 4):
            resolver.send(week)
