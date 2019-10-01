#!/usr/bin/env python3
#
# Copyright 2016 Red Hat, Inc.
#
# Authors:
#     Fam Zheng <famz@redhat.com>
#
# This work is licensed under the MIT License.  Please see the LICENSE file or
# http://opensource.org/licenses/MIT.


import os
import json
import datetime
import re
from django.conf import settings
from django.db import models
from django.db.models import Q
from django.contrib.auth.models import User, Group
from mbox import MboxMessage
from event import emit_event, declare_event
from django.contrib import admin

class Project(models.Model):
    name = models.CharField(max_length=1024, db_index=True, unique=True)
    mailing_list = models.CharField(max_length=4096, blank=True)
    url = models.CharField(max_length=4096, blank=True)
    git = models.CharField(max_length=4096, blank=True)
    description = models.TextField(blank=True)
    logo = models.ImageField(blank=True, upload_to="logo")
    display_order = models.IntegerField(default=0)
    def __str__(self):
        return self.name

    @classmethod
    def has_project(self, project):
        return self.objects.filter(name=project).exists()

    def get_property(self, prop, default=None):
        a = ProjectProperty.objects.filter(project=self, name=prop).first()
        if a:
            return json.loads(a.value)
        else:
            return default

    def get_properties(self):
        r = {}
        for m in ProjectProperty.objects.filter(project=self):
            r[m.name] = json.loads(m.value)
        return r

    def set_property(self, prop, value):
        if value == None:
            ProjectProperty.objects.filter(project=self, name=prop).delete()
            return
        pp, created = ProjectProperty.objects.get_or_create(project=self,
                                                            name=prop)
        pp.value = json.dumps(value)
        pp.save()

    def total_series_count(self):
        return Message.objects.series_heads(project_name=self.name).count()

    def maintained_by(self, user):
        if user.is_superuser:
            return True
        if user.username in self.get_property("maintainers", []):
            return True
        return False

class ProjectProperty(models.Model):
    project = models.ForeignKey('Project', on_delete=models.CASCADE)
    name = models.CharField(max_length=1024, db_index=True)
    value = models.TextField(blank=True)

    class Meta:
        unique_together = ('project', 'name',)

declare_event("SeriesComplete", project="project object",
              series="series instance that is marked complete")

declare_event("MessageAdded", message="message object that is added")

class MessageManager(models.Manager):

    class DuplicateMessageError(Exception):
        pass

    def series_heads(self, project_name=None):
        q = super(MessageManager, self).get_queryset()\
                .filter(is_series_head=True)
        if project_name:
            q = q.filter(project__name=project_name)
        return q

    def find_series(self, message_id, project_name=None):
        return self.series_heads(project_name).filter(message_id=message_id).first()

    def patches(self):
        return super(MessageManager, self).get_queryset().\
                filter(is_patch=True)

    def update_series(self, msg):
        """Update the series' record to which @msg is replying"""
        s = msg.get_series_head()
        if not s:
            return
        if not s.last_reply_date or s.last_reply_date < msg.date:
            s.last_reply_date = msg.date
            s.save()
        cur, total = s.get_num()
        if cur == total and s.is_patch:
            s.set_complete()
            return
        # TODO: Handle no cover letter case
        find = set(range(1, total + 1))
        for p in s.get_patches():
            assert p.is_patch
            cur, total = p.get_num()
            if cur in find:
                find.remove(cur)
        if not find:
            s.set_complete()

    def delete_subthread(self, msg):
        for r in msg.get_replies():
            self.delete_subthread(r)
        msg.delete()

    def add_message_from_mbox(self, mbox, user, project_name=None):

        def find_message_projects(m):
            q = []
            for name, addr in m.get_to() + m.get_cc():
                q += Project.objects.filter(mailing_list__contains=addr)
            if not q:
                raise Exception("Cannot find project for message: %s" % m)
            return q

        m = MboxMessage(mbox)
        msgid = m.get_message_id()
        if project_name:
            projects = [Project.object.get(name=project_name)]
        else:
            projects = find_message_projects(m)
        for p in projects:
            msg = Message(message_id=msgid,
                          in_reply_to=m.get_in_reply_to() or "",
                          date=m.get_date(),
                          subject=m.get_subject(),
                          stripped_subject=m.get_subject(strip_tags=True),
                          version=m.get_version(),
                          sender=json.dumps(m.get_from()),
                          receivers=json.dumps(m.get_to() + m.get_cc()),
                          prefixes=json.dumps(m.get_prefixes()),
                          is_series_head=m.is_series_head(),
                          is_patch=m.is_patch(),
                          patch_num=m.get_num()[0])
            msg.project = p
            if self.filter(message_id=msgid, project__name=p.name).first():
                raise self.DuplicateMessageError(msgid)
            msg.save_mbox(mbox)
            msg.save()
            emit_event("MessageAdded", message=msg)
            self.update_series(msg)
        return projects

def HeaderFieldModel(**args):
    return models.CharField(max_length=4096, **args)

class Message(models.Model):
    """ Patch email message """

    project = models.ForeignKey('Project', on_delete=models.CASCADE)
    message_id = HeaderFieldModel(db_index=True)
    in_reply_to = HeaderFieldModel(blank=True, db_index=True)
    date = models.DateTimeField(db_index=True)
    last_reply_date = models.DateTimeField(db_index=True, null=True)
    subject = HeaderFieldModel()
    stripped_subject = HeaderFieldModel(db_index=True)
    version = models.PositiveSmallIntegerField(default=0)
    sender = HeaderFieldModel(db_index=True)
    receivers = models.TextField()
    # JSON encoded list
    prefixes = models.TextField(blank=True)
    is_series_head = models.BooleanField()
    is_complete = models.BooleanField(default=False)
    is_patch = models.BooleanField()
    patch_num = models.PositiveSmallIntegerField(null=True, blank=True)

    objects = MessageManager()

    def save_mbox(self, mbox):
        f = open(self.get_mbox_path(), "wb")
        f.write(mbox.encode("utf-8"))
        f.close()

    def get_mbox_obj(self):
        self.get_mbox()
        return self._mbox_obj

    def get_mbox(self):
        if hasattr(self, "mbox"):
            return self.mbox
        f = open(self.get_mbox_path(), "r", encoding="utf-8")
        self.mbox = f.read()
        self._mbox_obj = MboxMessage(self.mbox)
        f.close()
        return self.mbox

    def get_mbox_path(self):
        return os.path.join(settings.MBOX_DIR, self.message_id)

    def get_prefixes(self):
        return json.loads(self.prefixes)

    def get_num(self):
        assert self.is_patch or self.is_series_head
        cur, total = 1, 1
        for tag in self.get_prefixes():
            if '/' in tag:
                n, m = tag.split('/')
                try:
                    cur, total = int(n), int(m)
                    break
                except:
                    pass
        return cur, total

    def get_reply(self, message_id):
        r = Message.objects.get(project=self.project, message_id=message_id)
        assert r.in_reply_to == self.message_id
        return r

    def get_replies(self):
        return Message.objects.filter(project=self.project,
                                      in_reply_to=self.message_id).\
                                      order_by('patch_num')

    def get_in_reply_to_message(self):
        if not self.in_reply_to:
            return None
        return Message.objects.filter(project_id=self.project_id,
                                      message_id=self.in_reply_to).first()

    def get_series_head(self):
        s = self
        while s:
            if s.is_series_head:
                return s
            s = s.get_in_reply_to_message()
        return None

    def get_patches(self):
        if not self.is_series_head:
            raise Exception("Can not get patches for a non-series message")
        c, n = self.get_num()
        if c == n and self.is_patch:
            return [self]
        return Message.objects.patches().filter(project=self.project,
                                                in_reply_to=self.message_id)\
                             .order_by('patch_num')

    def get_property(self, prop, default=None):
        mp = MessageProperty.objects.filter(message=self, name=prop).first()
        if mp:
            return json.loads(mp.value)
        else:
            return default

    def get_properties(self):
        r = {}
        for m in MessageProperty.objects.filter(message=self):
            r[m.name] = json.loads(m.value)
        return r

    def set_property(self, prop, value):
        if value == None:
            MessageProperty.objects.filter(message=self, name=prop).delete()
            return
        mp, created = MessageProperty.objects.get_or_create(message=self,
                                                            name=prop)
        mp.value = json.dumps(value)
        mp.save()

    def get_sender(self):
        return json.loads(self.sender)

    def get_receivers(self):
        return json.loads(self.receivers)

    def get_sender_addr(self):
        return self.get_sender()[1]

    def get_sender_name(self):
        return self.get_sender()[0]

    def _get_age(self, date):
        def _seconds_to_human(sec):
            unit = 'second'
            if sec > 60:
                sec /= 60
                unit = 'minute'
                if sec > 60:
                    sec /= 60
                    unit = 'hour'
                    if sec > 24:
                        sec /= 24
                        unit = 'day'
                        if sec > 7:
                            sec /= 7
                            unit = 'week'
            if sec >= 2:
                unit += 's'
            return "%s %s" % (int(sec), unit)

        age = int((datetime.datetime.utcnow() - date).total_seconds())
        if age < 0:
            return "now"
        return _seconds_to_human(age)

    def get_age(self):
        return self._get_age(self.date)

    def get_asctime(self):
        d = self.date
        wday = d.weekday()+1;
        return '%s %s %d %d:%02d:%02d %s' % (
                "MonTueWedThuFriSatSun"[wday*3-3:wday*3],
                "JanFebMarAprMayJunJulAugSepOctNovDec"[d.month*3-3:d.month*3],
                d.day, d.hour, d.minute, d.second, d.year)

    def get_last_reply_age(self):
        return self._get_age(self.last_reply_date)

    def get_body(self):
        return self.get_mbox_obj().get_body()

    def get_preview(self, maxchar=1000):
        return self.get_mbox_obj().get_preview()

    def get_diff_stat(self):
        body = self.get_body()
        if not self.is_series_head:
            return None
        state = ""
        cur = []
        patterns = [r"\S*\s*\|\s*[0-9]* \+*-*$",
                    r"\S* => \S*\s*|\s*[0-9]* \+*-*$",
                    r"[0-9]* files changed",
                    r"1 file changed",
                    r"(create|delete) mode [0-7]*",
                    r"rename ",
                   ]
        ret = []
        for l in self.get_body().splitlines():
            l = l.strip()
            match = False
            for p in patterns:
                if re.match(p, l):
                    match = True
                    break
            if match:
                cur.append(l)
            else:
                if cur:
                    ret = cur
                cur = []
        if cur:
            ret = cur
        return "\n".join(ret)

    def get_alternative_revisions(self):
        assert self.is_series_head
        return Message.objects.series_heads().filter(stripped_subject=self.stripped_subject)

    def set_complete(self):
        if self.is_complete:
            return
        self.is_complete = True
        self.save()
        emit_event("SeriesComplete", project=self.project, series=self)

    def __str__(self):
        return self.subject

    class Meta:
        unique_together = ('project', 'message_id',)

class MessageProperty(models.Model):
    message = models.ForeignKey('Message', on_delete=models.CASCADE)
    name = models.CharField(max_length=256)
    # JSON encoded value
    value = models.TextField(blank=True)

    def __str__(self):
        if len(self.value) > 30:
            val_prev = self.value[:30] + "..."
        else:
            val_prev = self.value
        return "%s: %s = %s" % (self.message.subject, self.name, val_prev)

    class Meta:
        unique_together = ('message', 'name',)
        verbose_name_plural = "Message Properties"

class Module(models.Model):
    """ Module information """
    name = models.CharField(max_length=128, unique=True)
    enabled = models.BooleanField(default=True)
    config = models.TextField(blank=True)

    def __str__(self):
        return self.name
