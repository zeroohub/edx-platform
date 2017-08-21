from __future__ import print_function

import datetime
import logging
import pytz
from django.contrib.sites.models import Site

from celery import task
from django.core.management.base import BaseCommand
from django.conf import settings
from django.core.urlresolvers import reverse

from openedx.core.djangoapps.schedules.models import Schedule, ScheduleConfig

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
    def __init__(self, site, current_date):
        self.site = site
        self.current_date = current_date.replace(hour=0, minute=0, second=0)

    def send(self, week):
        if not ScheduleConfig.current(self.site).enqueue_recurring_generic:
            return

        target_date = self.current_date - datetime.timedelta(days=week * 7)
        for hour in range(24):
            target_hour = target_date + datetime.timedelta(hours=hour)
            _schedule_hour.apply_async((self.site.id, week, target_hour), retry=False)


@task(ignore_result=True, routing_key=settings.ACE_ROUTING_KEY)
def _schedule_hour(site_id, week, target_hour):
    msg_type = RecurringNudge(week)

    for (user, language, context) in _schedules_for_hour(target_hour):
        msg = msg_type.personalize(
            Recipient(
                user.username,
                user.email,
            ),
            language,
            context,
        )
        _schedule_send.apply_async((site_id, msg), retry=False)


@task(ignore_result=True, routing_key=settings.ACE_ROUTING_KEY)
def _schedule_send(site_id, msg):
    site = Site.objects.get(pk=site_id)
    if not ScheduleConfig.current(site).deliver_recurring_generic:
        return

    ace.send(msg)


def _schedules_for_hour(target_hour):
    schedules = Schedule.objects.select_related(
        'enrollment__user__profile',
        'enrollment__course',
    ).filter(
        start__gte=target_hour,
        start__lt=target_hour + datetime.timedelta(minutes=60),
    )

    if "read_replica" in settings.DATABASES:
        schedules = schedules.using("read_replica")

    for schedule in schedules:
        enrollment = schedule.enrollment
        user = enrollment.user

        course_id_str = str(enrollment.course_id)
        course = enrollment.course

        # TODO: this produces a URL that contains the literal "+" character in the course key, which breaks sailthru
        course_root = reverse('course_root', kwargs={'course_id': course_id_str})

        def absolute_url(relative_path):
            return u'{}{}'.format(settings.LMS_ROOT_URL, relative_path)

        template_context = {
            'student_name': user.profile.name,
            'course_name': course.display_name,
            'course_url': absolute_url(course_root),

            # This is used by the bulk email optout policy
            'course_id': course_id_str,
        }

        yield (user, course.language, template_context)


class Command(BaseCommand):

    def add_arguments(self, parser):
        parser.add_argument('--date', default=datetime.datetime.utcnow().date().isoformat())
        parser.add_argument('site_domain_name')

    def handle(self, *args, **options):
        current_date = datetime.datetime(
            *[int(x) for x in options['date'].split('-')],
            tzinfo=pytz.UTC
        )
        site = Site.objects.get(domain__iexact=options['site_domain_name'])
        resolver = ScheduleStartResolver(site, current_date)
        for week in (1, 2):
            resolver.send(week)
