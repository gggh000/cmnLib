# UCS.PY - module for all aspects of UCS objects, including UCSM, FI and blade declarations
# classes and its members and constant are defined here. 

# import statements. 

import time
from security import *
from saLibrary import *
import saLibrary
import re

from tmpWorkAround import *

#   Use this function to send batch of UCSM function commands to save coding space.
#   It is possible that the connection drops during the execution of any of the command
#   streams, in which case, it will return EXIT_ERR immediately. 
#   req: None
#   input:  pSp - service profile instance.
#           pAddrStart - starting address of search in hex string format "HHHH"
#           pAddrEnd - ending address of search in hex string format "HHHH"
#           pPattern - pattern to search. Look pConvert for more info.
#           pConvert    - 0 (default): do not convert, the input is hex string to be matched in the format: "30 31 32" for string 012
#                       - 1: convert: input is string value i.e. "123" and has to be converted to "30 31 32"
#           pIncrement - increment size during search, should be multiple of 16.

#   output: Address in which the pPattern is found if found. Address is aligned to 16 bytes in hex string format "HHHH" 
#           EXIT_ERR - on any error condition or address is not found.

def memFindString(pSp, pAddrStart, pAddrEnd, pPattern, pConvert = 0, pIncrement = "16"):
    debug = 0
    stat = 0

    statList = []

    # Validate the input arguments.
    
    if validateFcnInput([pSp, pAddrStart, pAddrEnd, pPattern, pConvert, pIncrement]) == EXIT_ERR:
        printErr("one or more of input is None.")
        return EXIT_ERR

    try:
        int(pIncrement, 16)
        int(pAddrStart, 16)
        int(pAddrEnd, 16)
    except TypeError:
        printErr("input error")
        return EXIT_ERR

    if int(pIncrement, 16) & 15 != 0:
        printErr("pIncrement should be multiple of 16: " + str(pIncrement))
        return EXIT_ERR

    # Convert to supported format.

    if pConvert:
        for i in range(0, len(a)):
            pPattern += str(ord(a[i])) + " "
        pPattern = pPattern.strip()

    printDbg("input value: " + str(pPattern))

    if not re.search(" ", pPattern):
        printErr("Input string does not look right, needs to be in format: 'XX XX XX...XX' or the search to succeed.")
        return EXIT_ERR

    memPtrCurr = pAddrStart
    
    # Start the search now.

    memPtrCurr = int(pAddrStart, 16)

    while memPtrCurr < int(pAddrEnd, 16):
        printVar(str(hex(memPtrCurr)))
        stat = cli_with_ret(pSp.bmcSsh, "mem " + str(hex(memPtrCurr)).split('x')[-1] + " 10", "", "efiShell")

        printDbg("stat: " + str(stat))

        if re.search(pPattern, stat):
            printDbg("Found the pattern " + str(pPattern) + " at " + str(memPtrCurr))
            return memPtrCurr

        memPtrCurr += int(pIncrement, 16)

    printErr("Unable to find the pattern " + str(pPattern) + " in range: " + str(pAddrStart) + ":" + str(pAddrEnd))
    return EXIT_ERR
