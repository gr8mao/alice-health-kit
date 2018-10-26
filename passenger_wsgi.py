# -*- coding: utf-8 -*-
import sys

sys.path.append('/home/g/gr8maort/alice.maxbelov.ru/AliceHealthKit/')
sys.path.append('/home/g/gr8maort/.local/lib/python3.4/site-packages')

from AliceHealthKit import app as application
from werkzeug.debug import DebuggedApplication

application.wsgi_app = DebuggedApplication(application.wsgi_app, True)
application.debug = False
