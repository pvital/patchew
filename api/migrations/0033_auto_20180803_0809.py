# -*- coding: utf-8 -*-
# Generated by Django 1.11.13 on 2018-08-03 08:09
from __future__ import unicode_literals

from django.db import migrations
import jsonfield.encoder
import jsonfield.fields


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0032_fix_git_results'),
    ]

    operations = [
        migrations.AlterField(
            model_name='result',
            name='data',
            field=jsonfield.fields.JSONField(default={}, dump_kwargs={'cls': jsonfield.encoder.JSONEncoder, 'separators': (',', ':')}, load_kwargs={}),
        ),
    ]
