import pexpect
import time
import re
import os
import sys
import string 
import subprocess
from time import gmtime, strftime
#from ucs import *

expectTermination= ".*#.*"
sam = None
global ip
bmcIp = None
bladeSpName = None
argIp = None
argBladePos = None
fp = None
UNIFIED_LOG = 0
TIMEOUT_PREREQ_DISPLAY = 30




