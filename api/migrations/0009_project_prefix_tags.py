# -*- coding: utf-8 -*-
# Generated by Django 1.9.12 on 2017-03-08 11:02
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0008_auto_20160816_0151'),
    ]

    operations = [
        migrations.AddField(
            model_name='project',
            name='prefix_tags',
            field=models.CharField(blank=True, max_length=1024),
        ),
    ]