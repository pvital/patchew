# -*- coding: utf-8 -*-
# Generated by Django 1.9.13 on 2017-06-27 12:10
from __future__ import unicode_literals

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0009_project_prefix_tags'),
    ]

    operations = [
        migrations.AlterField(
            model_name='messageproperty',
            name='message',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='properties', to='api.Message'),
        ),
        migrations.AlterField(
            model_name='project',
            name='description',
            field=models.TextField(blank=True, help_text='Description of the project'),
        ),
        migrations.AlterField(
            model_name='project',
            name='display_order',
            field=models.IntegerField(default=0, help_text='Order number of the project\n                                        to display, higher number first'),
        ),
        migrations.AlterField(
            model_name='project',
            name='git',
            field=models.CharField(blank=True, help_text='The git repo of the project. If a\n                           branch other than "master" is desired, add it to the\n                           end after a whitespace', max_length=4096),
        ),
        migrations.AlterField(
            model_name='project',
            name='logo',
            field=models.ImageField(blank=True, help_text='Project logo', upload_to='logo'),
        ),
        migrations.AlterField(
            model_name='project',
            name='mailing_list',
            field=models.CharField(blank=True, help_text='The mailing list of the project.\n                                   Will be used to verify if a message belongs\n                                   to this project', max_length=4096),
        ),
        migrations.AlterField(
            model_name='project',
            name='name',
            field=models.CharField(db_index=True, help_text='The name of the project', max_length=1024, unique=True),
        ),
        migrations.AlterField(
            model_name='project',
            name='prefix_tags',
            field=models.CharField(blank=True, help_text="Whitespace separated tags that\n                                   are required to be present messages' prefix.\n                                   Tags led by '/' are treated with python regex match.\n                                   ", max_length=1024),
        ),
        migrations.AlterField(
            model_name='project',
            name='url',
            field=models.CharField(blank=True, help_text='The URL of the project page', max_length=4096),
        ),
    ]
