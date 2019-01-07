# tmpWorkAround module is designed to hold only temporary function that serves as a workaround
# for defective behavior with UCS blade, so that unrelated tests are not failed due to certain
# defects. Once defect is fixed, respective function(s) should become unavailable or becomes
# empty with return PASS only so that they become transparent. Functions in this module should 
# not serve any other core purposes.

import pexpect
import time
import re
import os
import sys
import string 
import inspect
import telnetlib
import getpass
from saLibrary import *

PYTHON_ROOT_DIR = os.environ.get('CURRENT_TREE')

# temporary function for messing with bmc sol.

def tmpBmcSshChange(pSp):
    bmcUser = None
    bmcPw = None
    lBmcSsh = None

    '''
    bmcUser = getGlobal('CONFIG_BMC_LOGIN_USER')
    bmcPw = getGlobal('CONFIG_BMC_LOGIN_PW')
    lBmcSsh = sshLogin(pSp.bmcSsh.args[3], bmcUser, bmcPw)

    printDbg("2.===========================\nlBmcSsh from tpmBmcSshChange: ")
    print lBmcSsh
    printDbg("---------------------------")
    stat = cli_with_ret(lBmcSsh, "echo try 2", "", "efiShell", 1)
    printDbg("stat\n--------------\n: " + str(stat) + "\n----------------")
    '''

    printDbg("delaying for 1200 sec/20 min-s")
    tmpDelay(14400)

    '''    
    printDbg("closing pSp.bmcSsh...")
    pSp.bmcSsh.close()
    '''
    return SUCCESS

# introduces aritificial delay when needed without impacting code too much.
# default is 1 min

def tmpDelay(pDelaySec = 60):
    if pDelaySec == None:
        printErr("tmpDelay is None defaulting to 60 sec")
    else:
        printDbg("delaying for " + str(pDelaySec) + " seconds.")
        time.sleep(pDelaySec)
        printDbg("done with the delay, resuming.")
    return SUCCESS

# toggles boot policy to legacy and back to UEFI. Work around for BLUE SCREEN OF F6.
# 
# pPwType    - type of password to be fetched

def tmpReConfigBootPol(pSp, pUcsmSsh, pDisableFunction = 0):

    if pDisableFunction:
        return EXIT_ERR    

    debug = 1
    bootModes = ("legacy","UEFI")        

    # toggle boot-policy to legacy and then uefi.

    for bootMode in bootModes:
        cli_with_ret(pUcsmSsh, "scope org", pFi.hostName)
        time.sleep(1)
        cli_with_ret(pUcsmSsh, "scope boot-policy " + pSpspName, pFi.hostName)
        time.sleep(1)
        cli_with_ret(pUcsmSsh, "set reboot-on-update yes", pFi.hostName)
        time.sleep(1)
        cli_with_ret(pUcsmSsh, "set boot-mode " + bootMode, pFi.hostName)
        time.sleep(1)
        cli_with_ret(pUcsmSsh, "commit", pFi.hostName)
        time.sleep(1)

    stat = pSpwaitConfigComplete(pUcsmSsh)

    if stat == EXIT_ERR:
        printErr("Timed out waiting for boot-policy restore configuration")
        return EXIT_ERR

    return SUCCESS


