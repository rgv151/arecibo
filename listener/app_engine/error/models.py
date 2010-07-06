from django.core.urlresolvers import reverse

from datetime import datetime

from google.appengine.ext import db
from google.appengine.api import datastore_errors
from google.appengine.api.labs import taskqueue

from appengine_django.models import BaseModel
from error.signals import group_created
from projects.models import ProjectURL

import os

class Group(BaseModel):
    """ A grouping of errors """
    uid = db.StringProperty()
    timestamp = db.DateTimeProperty()
    project_url = db.ReferenceProperty(ProjectURL, required=False)
    count = db.IntegerProperty(default=0)
        
    def sample(self):
        try:
            return Error.all().filter("group = ", self).order("-timestamp")[0]
        except IndexError:
            return None
    
    @property
    def id(self):
        return str(self.key())
        
    def save(self, *args, **kw):
        created = not hasattr(self, "id")
        if created:
            self.timestamp = datetime.now()
        self.put()
        if created:
            group_created.send(sender=self.__class__, instance=self)

class Error(BaseModel):
    # time error was received by this server
    timestamp = db.DateTimeProperty()
    timestamp_date = db.DateProperty()
    
    ip = db.StringProperty()
    user_agent = db.StringProperty()
    user_agent_short = db.StringProperty()
    user_agent_parsed = db.BooleanProperty(default=False)
    operating_system = db.StringProperty()
    
    priority = db.IntegerProperty()
    status = db.StringProperty()
    
    raw = db.StringProperty()
    domain = db.StringProperty()
    server = db.StringProperty()
    query = db.StringProperty()
    protocol = db.StringProperty()
    
    uid = db.StringProperty()
    type = db.StringProperty()
    msg = db.TextProperty()
    traceback = db.TextProperty()
    
    errors = db.TextProperty()
    
    # time error was recorded on the client server
    error_timestamp = db.DateTimeProperty()
    request = db.TextProperty()
    username = db.StringProperty()
    
    group = db.ReferenceProperty(Group)
    
    read = db.BooleanProperty(default=False)
    
    create_signal_sent = db.BooleanProperty(default=False)
    
    def _short(self, field, length):
        value = getattr(self, field)
        if len(value) > length:
            return "%s.." % value[:length-2]
        return value
    
    def url_short(self): return self._short("url", 20)
    def type_short(self): return self._short("type", 20)
    def query_short(self): return self._short("query", 20)
    def title_short(self): return self._short("title", 20)
    
    def get_absolute_url(self):
        return reverse("error-view", args=[self.id,])
    
    def get_similar(self, limit=5):
        try:
            return Error.all().filter("group = ", self.group).filter("__key__ !=", self.key())[:limit]
        except datastore_errors.Error:
            return []
    
    def delete(self):
        try:
            if self.group:
                self.group.count = self.group.count - 1
                if self.group.count < 1:
                    self.group.delete()
        except datastore_errors.Error:
            pass
        super(Error, self).delete()
                    
    @property
    def id(self):
        return str(self.key())
    
    @property
    def title(self):
        """ Try to give a nice title to describe the error """
        strng = ""
        if self.type:
            strng = self.type
            if self.server:
                if self.status:
                    strng = "%s" % (strng)
                if not strng:
                    strng = "Error"
                strng = "%s on %s" % (strng, self.server)
        elif self.status:
            strng = self.status
            if self.server:
                strng = "%s on server %s" % (strng, self.server)
        elif self.raw:
            strng = self.raw
        else:
            strng = self.nice_date()
        if self.uid:
            strng = "%s" % (strng)
        return strng
    
    @property
    def description(self):
        return self.msg or ""
    
    def save(self, *args, **kw):
        created = not hasattr(self, "id")
        self.put()
        if created and not "dont_send_signals" in kw:
            if os.environ.get('SERVER_SOFTWARE', '').startswith('Dev'):
                # send the signal, otherwise we have to clicking buttons
                # to process the queue
                from error.views import send_signal
                send_signal(None, self.id)
            else:
                # enqueue the send notification
                # if development
                taskqueue.add(url=reverse("error-created", args=[self.id,]))
