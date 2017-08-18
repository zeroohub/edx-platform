# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('student', '0011_userprofile_profession'),
    ]

    operations = [
        migrations.AddField(
            model_name='userprofile',
            name='specialty',
            field=models.TextField(null=True, blank=True),
        ),
    ]
