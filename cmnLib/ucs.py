#############################################################################
#
#   HEADER: ucs.py
#   SUMMARY: module for all aspects of UCS objects, including UCSM, FI and blade declarations
#   classes and its members and constant are defined here. 

# import statements. 

import time
from security import *
from saLibrary import *
import saLibrary
import re
import thread
import time 

from tmpWorkAround import *
global postComplete
global textCaptured

#   File protocols used file copy service API-s.

fileProtocols = [\
'FILE_PROTOCOL_SCP',\
'FILE_PROTOCOL_TFTP',\
]

#   Firmware protocl used to download images into FI-s.

fwDwProtocols = [\
'FW_DW_PROTOCOL_SCP',\
'FW_DW_PROTOCOL_TFTP',\
]

# Set default values used by file copy service API-s.

#DEFAULT_DEBUG_PLUGIN_FILE_NAME = "ucs-dplug.5.2.3.N2.2.26.24.gbin"
DEFAULT_DEBUG_PLUGIN_FILE_NAME = "ucs-dplug.5.0.3.N2.3.22.85.gbin"
DEFAULT_DEBUG_PLUGIN_PROTOCOL = 'FILE_PROTOCOL_TFTP'

DEFAULT_DEBUG_PLUGIN_SRC_IP = "10.193.225.132"
DEFAULT_DEBUG_PLUGIN_DST_IP = DEFAULT_DEBUG_PLUGIN_SRC_IP

DEFAULT_FILE_COPY_PROTOCOL = DEFAULT_DEBUG_PLUGIN_PROTOCOL
DEFAULT_FILE_COPY_SRC_IP = DEFAULT_DEBUG_PLUGIN_SRC_IP

CONFIG_BOOT_EFI_SHELL_BP_F2 = 1
CONFIG_BOOT_EFI_SHELL_BP = 2
CONFIG_BOOT_EFI_SHELL_F2 = 3
CONFIG_BOOT_EFI_SHELL_F2_BP = 4
CONFIG_BOOT_EFI_SHELL_MISC = 10

#   From version string passed on to this function, it determines the major, minor, Mr and buildNo
#   and constructs the version string that are suitable for update and activate cli command.
#   input:  
#   - pComponentString - B-bundle file name for now is supported. 
#   output: 
#   - version string that is determined from ucs component file name, compatible with cli update command.
#   EXIT_ERR - on any error condition.

def getUpdateVersionString(pComponentString):
    debug = 0
    spotFixBuild = None
    tokensNonSpot = None
    tokensSpot = None
    startIndexVer = None

    verMajor = ""
    verMinor = ""
    verMr = ""
    verBuildNo = ""

    printDbg("Entered: bundlestring: " + str(pComponentString), debug)

    if validateFcnInput([pComponentString]) == EXIT_ERR:
        return EXIT_ERR

    # Identify the type of component. The supported types are IOM, b-series bundle, 
    # FI (ks,system) and UCSM manager. All other types are not supported.
    # Here the number of expected tokens after split is pre-set to be compared against
    # actual result to identify the image.

    startIndexVer = 0

    if re.search("2200|2100", pComponentString):
        printDbg("IOM image:", debug)
        tokensNonSpot = 6
    elif re.search("b-series", pComponentString):
        printDbg("b-bundle:", debug)
        tokensNonSpot = 7
    elif re.search("ucs-manager", pComponentString):
        printDbg("ucs-manager:", debug)
        tokensNonSpot = 6
    elif re.search("kickstart|system", pComponentString):    
        printDbg("kickstart|system:", debug)
        tokensNonSpot = 9
        printDbg("Setting startIndexVer to: 4", debug)
        startIndexVer = 4
    else:
        printErr("Unsupported image string: " + str(pComponentString))
        return EXIT_ERR

    # Number of tokens resulting from split is one less.

    tokensSpot = tokensNonSpot - 1
    bundleVersion = pComponentString.strip().split(".")

    if debug:
        printDbg("bundleVersion: ")
        print bundleVersion

    lUpdateVer = None

    # If number of token after split is 9, this is FI image name. 

    if tokensNonSpot == 9:
        try:
            fiVer1 = bundleVersion[1]
            fiVer2 = bundleVersion[2]
            fiVer3 = bundleVersion[3]
            fiVer4 = bundleVersion[4]
        except IndexError:
            printErr("Unable to parse the versions")
            return EXIT_ERR

    # Identify spot release or non-spot release.

    if len(bundleVersion) == tokensSpot:
        printDbg("Spotfix release is found.", debug)
        spotFixBuild = 1

        try:
            verMajor = bundleVersion[startIndexVer+1]
            verMinor = bundleVersion[startIndexVer+2]
            verMr = ""
            verBuildNo = bundleVersion[startIndexVer+3]
        except IndexError:
            printErr("Error parsing the bundle version: " + str(bundleVersion))
            return EXIT_ERR

    elif len(bundleVersion) == tokensNonSpot:
        printDbg("Non-spotfix (FCS or pre-FCS) build is found.", debug)
        spotFixBuild = 0

        try:
            verMajor = bundleVersion[startIndexVer+1]
            verMinor = bundleVersion[startIndexVer+2]
            verMr = bundleVersion[startIndexVer+3]
            verBuildNo = bundleVersion[startIndexVer+4]

            if tokensNonSpot == 9:
                verBuildNo = bundleVersion[startIndexVer+3]
                verMr = ""
                    
        except IndexError:
            printErr("Error parsing the bundle version: " + str(bundleVersion))
            return EXIT_ERR
    else:
        printErr("Can not determine whether it is spot/non-spot version. Likely to fail.")
        return EXIT_ERR

    # Now start constructing string version suitable for actual update/activate command.
    # Each component has different versions.

    printDbg("verMajor:     " + str(verMajor), debug)
    printDbg("verMinor:     " + str(verMinor), debug)
    printDbg("verMr:        " + str(verMr), debug)
    printDbg("verBuildNo:   " + str(verBuildNo), debug)

    if tokensNonSpot == 4:
        printDbg("Constructing update version string for UCSM", debug)

        if spotFixBuild:
            lUpdateVer = verMajor + "." + verMinor + "(" + verBuildNo + ")"
        else:
            lUpdateVer = verMajor + "." + verMinor + "(" + verMr + "." + verBuildNo + ")"
    elif tokensNonSpot == 6 or tokensNonSpot == 7:
        printDbg("Constructing update version string for IOM or B-bundle.", debug)

        if spotFixBuild:
            lUpdateVer = verMajor + "." + verMinor + "(" + verBuildNo + ")"
        else:
            lUpdateVer = verMajor + "." + verMinor + "(" + verMr + "." + verBuildNo + ")"
    elif tokensNonSpot == 9:
        printDbg("Constructing update version string for system/kickstart", debug)

        if spotFixBuild:
            lUpdateVer = fiVer1 + "." + fiVer2 + "(" + fiVer3 + ")" + fiVer4 + "(" + verMajor + "." + verMinor + ")"
        else:
            lUpdateVer = fiVer1 + "." + fiVer2 + "(" + fiVer3 + ")" + fiVer4 + "(" + verMajor + "." + verMinor + "." + verBuildNo + ")"
    
    printDbg("Update version string constructed: " + str(lUpdateVer))
    return lUpdateVer

#   Helper functions to monitor ssh console for pMessage to appear on it
#   When text is captured or timeout is reached. It will set the global
#   variable textCaptured to 1. Before running it will set the textCaptured flag
#   to make sure it is zero.
#   input:  
#   - pBlade - blade instance object.
#   - pBmsSsh - bmc console.
#   - pMessage - message to be monitored for
#   - pTimeOut - timeout value.
#   output: 
#   - SUCCESS - on success.
#   - EXIT_ERR - on any error condition.

def threadHelpCheckMonitor(pBlade, pBmcSsh, pMessage, pTimeOut = 600):
    debug = 0
    global textCaptured

    if validateFcnInput([pBlade, pBmcSsh, pMessage, pTimeOut]) == EXIT_ERR:
        printErr("Invalid parameters.")
        return EXIT_ERR

    textCaptured = 0

    printDbg("Setting textCaptured to 0", debug)
    textCaptured = 0

    start = time.time()
    pExpectList = [pexpect.TIMEOUT, pexpect.EOF] + pMessage

    printDbg("pExpectList: ", debug)
    
    if debug:
        print pExpectList

    while 1:
        index1 = pBmcSsh.expect(pExpectList, re.DOTALL)

        printDbg("index1: " + str(index1), debug)

        if index1 == 0:
            end = time.time()
            printDbg(str(end - start) + " seconds passed.")

            if (end - start) > int(pTimeOut):
                printWarn("Timeout is reached waiting for text!")
                return EXIT_ERR

        elif index1 == 1:
            printDbg("EOF: Is console active? ")
            return EXIT_ERR
        elif index1 == 2 or index == 3 or index == 4:
            printDbg("Text is captured. Give few more seconds to settle.")
            time.sleep(10)
            textCaptured = 1
            return SUCCESS
        else:
            printWarn("Unknown index.")
            return EXIT_ERR            

    '''
#   Helper function for bootEfiShell, it repeatedly sends F6 in order trigger boot device selection
#   menu. Once it receives the notification by seeing postComplete is set, it will end itself.

def threadHelpCheckPostComplete(pBlade, sshBmcD, pIntKey):
    debug = 0
    global postComplete
    elapsedTime = 0

    CONFIG_POST_COMPLETE_WAIT_INTERVAL = getGlobal('CONFIG_POST_COMPLETE_WAIT_INTERVAL')
    CONFIG_POST_COMPLETE_WAIT_TIMEOUT = getGlobal('CONFIG_POST_COMPLETE_WAIT_TIMEOUT')

    if CONFIG_POST_COMPLETE_WAIT_INTERVAL == None or CONFIG_POST_COMPLETE_WAIT_TIMEOUT == None:
        printErr("Unable to fetch CONFIG_POST_COMPLETE_WAIT_INTERVAL/TIMEOUT value(s)")
        return EXIT_ERR

    while 1:
        printDbg("Waiting for BIOS POST completion...Elapsed time (sec): " + str(elapsedTime))
        time.sleep(CONFIG_POST_COMPLETE_WAIT_INTERVAL)
        elapsedTime  += CONFIG_POST_COMPLETE_WAIT_INTERVAL
        postCompleteStat = bmcGpioRead(pBlade, sshBmcD,  "/proc/nuova/gpio/fm_bios_post_cmplt")

        if postCompleteStat == EXIT_ERR:
            printErr("Can not understand gpio read.")
    
        if postCompleteStat == 0:
            continue
        elif postCompleteStat == 1:
            printDbg("Telling the main process to stop sending F6")
            postComplete = 1
            break
            return SUCCESS
        else:
            printErr("Invalid GPIO status: " + str(postComplete))

        if elapsedTime > CONFIG_POST_COMPLETE_WAIT_TIMEOUT:
            printErr("Timeout waiting for POST completion. Either failed to read GPIO status or POST failed.")
            return EXIT_ERR

    return SUCCESS
    '''

#   Use this function to copy a file to FI.
#   req: 
#   - None
#   input:  
#   - pFi - fabric IP (ucsm IP)
#   - pFileName  - file name to copy.
#   - pCopyDebugPlugin - if set, will copy debug plugin. (not implemented fully).
#   output: 
#   - SUCCESS - on success.
#   - EXIT_ERR - on any error condition.

def copyFileToFi(pFi, pFileName, pTftpServerIp, pCopyDebugPlugin=1):
    stat = None
    debug = 1

    # Determine the tftp server address. Will try to obtain the value from global config file: config.txt
    # if not defined there, will use hard-coded value defined in this function as a last resort.

    lTftpServerIpDefault = "10.193.225.132"
    lTftpServerIp = None

    if pTftpServerIp == None:
        printDbg("tftp server is None, will use default tftp server from config.txt.")
        lTftpServerIp = getGlobal('CONFIG_TFTP_SERVER_IP_DEFAULT')
    
        if lTftpServerIp == None:
            printWarn("Unable to obtain default TFTP server IP default. Will use local, hard coded value: "\
                 + str(lTftpServerIpDefault))
        else:
            printDbg("default server IP from global config: " + str(lTftpServerIp), debug)
    else:
        lTftpServerIp = pTftpServerIp
        printDbg("Will use passed tftp: " + str(pTftpServerIp))

    # Determine the fabric interconnect debug plugin file name. Will try to obtain the value from global config file: config.txt
    # if not defined there, will use hard-coded value defined in this function as a last resort.

    ucsDebugPluginFileName = str(getGlobal('CONFIG_UCSM_DEBUG_PLUGIN_FILENAME'))

    if ucsDebugPluginFileName == None:
        printWarn("Unable to find ucsDebugPluginFileName value from config.txt, \
            using hardcoded value: " + str(ucsDebugPluginFileName))
        ucsDebugPluginFileName = "ucs-dplug.5.2.3.N2.2.26.24.gbin"        
        ucsDebugPluginFileName = "ucs-dplug.5.2.3.N2.2.26.24.gbin"        

    # Login to FI and copy the BIOS and debug plugin file:

    ucsmSsh = sshLogin(pFi.mgmtIp, pFi.user, pFi.password)

    if ucsmSsh == None:
        printErr("unable to establish add'l session to UCSM.")
        return EXIT_ERR

    # Connect to local-mgmt.

    printDbg("connecting to local-mgmt")
    output1 = cli_with_ret(ucsmSsh, "connect local-mgmt", "")

    printDbg("output1:", debug)
    printDbg(output1)

    commandHints = [\
    "Copying UCS FI debug plugin " + str(ucsDebugPluginFileName) + " to /workspace" ,\
    "Copying file " + pFileName + " to /workspace" ,\

    "Copying UCS FI debug plugin to volatile:a",\
    "Loading UCS FI debug plugin from volatile:a",\
    "ls /bootflash/ to see UCS FI debug environment is entered.",\

    "copying /bootflash/" + pFileName + " to /bootflash",\

    "exit",\
    "exit",\
    ]

    commandSets = [\
    "cp tftp://" + lTftpServerIpDefault + "/" + ucsDebugPluginFileName + " /" + ucsDebugPluginFileName,\
    "cp tftp://" + lTftpServerIp + "/" + pFileName + " /" + pFileName,\

    "cp " + ucsDebugPluginFileName + " volatile:a",\
    "load volatile:a",\
    "ls /bootflash/",

    "cp /workspace/" + str(pFileName) + " /bootflash/",\
    ]

    errorTriggers = [\
    "File not found|timeout",\
    "File not found|timeout",\

    "cannot stat",\
    "Image doesn't exist|Digital signature verification failed",\
    "bytes total",\

    "cannot stat",\

    "Invalid Command",\
    "command not found"
    ]

    errorMessages = [\
    "UCS FI debug plugin " + ucsDebugPluginFileName + " does not exist on TFTP server " + lTftpServerIpDefault + " or TFTP " +\
    pFileName + " does not exist on TFTP server " + lTftpServerIp + " or TFTP timeout due to wrong TFTP server."\

    "UCS FI debug plugin " + ucsDebugPluginFileName + " is not on /workspace."
    "UCS FI debug plugin load from volatile:a failed.",\
    "ls /bootflash returns local-mgmt scope returns. Failed to enter debug plugin",\

    "For some reason, file " + pFileName + "is not on /workspace",\

    "Failed to exit from debug-plugin",\
    "Failed to exit from local-mgmt"
    ]

    time.sleep(3)

    # Process all commands above.

    for i in range(0, len(commandSets)):
        printBarDouble()
        printDbg(commandHints[i])
        time.sleep(3)
        printDbg("FI command: " + str(commandSets[i]))
        output1 = cli_with_ret(ucsmSsh, commandSets[i], "")
        
        printBarSingle()
        printDbg("5. index: " + str(i))
        printDbg("Looking for error pattern: " + str(errorTriggers[i]) + "...")
        printDbg("Will throw error message if failure: " + str(errorMessages[i]))
        printDbg("output1: \n" + str(output1) + "\n")

        if re.search(errorTriggers[i], output1):
            printErr(errorMessages[i])
            ucsmSsh.close()
            return EXIT_ERR

    printInfoToFile("All commands were processed OK.")

    ucsmSsh.close()
    return SUCCESS

#   Use this function to copy a file or subset of file to blade BMC.
#   Note this will copy the files internally from fabric interconnect address 127.5.254.1
#   It has not been tested well with HA fabric.
#   File(s) must be copied beforehand to Fabric interconnect /bootflash location before invoking 
#   this function.
#
#   input:  
#   - pFi - fabric IP (ucsm IP)
#   - pBlade - blade object whose bmc to be copied to.
#   - pFileName  - if <type 'str'>): file name to copy for single file.
#                - if <type 'list'> string array: file names to copy for multiple files.
#                - if list type, the entries must be string type. Otherwise result is unpredictable or error condition.
#   output: 
#   - SUCCESS - on success.
#   - EXIT_ERR - on any error condition.

def copyFileToBmc(pFi, pFileName):
    debug = 0
    CONFIG_BMC_TFTP_WAIT_INTERVAL = 15
    CONFIG_BMC_TFTP_WAIT_RETRY = 30
    ucsTftpServer = "127.5.254.1"

    # Get RH1 password here early now.

    rh1TargetPw = getPw("CEC")
    rh1TargetUser = getGlobal('CONFIG_RH1_SERVER_UNAME')
    rh1TargetPwShow = str(getUnEncPw(rh1TargetPw))

    if rh1TargetUser == None or rh1TargetPw == None:
        printErr("user/password retrieve error: /user: " + str(rh1TargetUser) )
        quit()

    # Connect to bmc.

    sshBmcD = pFi.mSp.mBlade.bmcDbgLogin(pFi, rh1TargetPw)

    if sshBmcD:
        printDbg("Successfully logged in to BMC debug console.")
    else:
        printDbg("BMC debug log in attempt failed.")
        return EXIT_ERR

    # Construct the commands for tftp-ing the files.

    if type(pFileName) == str:
        bmcCommand1 = ['nohup tftp -g -r ' + pFileName + " " + ucsTftpServer + " &"]
        pFileName = [pFileName]
    elif type(pFileName) == list:
        bmcCommand1 = []

        for i in pFileName:
            if type(i) != str:
                printErr("list member is not a string! " + str(type(i)))
                return EXIT_ERR

            bmcCommand1.append('nohup tftp -g -r ' + str(i) + " " + ucsTftpServer + " &")
    else:
        printErr("Unknown type: " + str(type(pFileName)))
        return EXIT_ERR

    # Start Tftp transfer of files now.
    # Because when the wait time is longer, cli_with_ret is not handling it correctly the command line.
    # Therefore, we use "tftp .. &" followed by command "ps | grep tftp" to see if long copy is finished.

    counter = 0

    for i in range(0, len(bmcCommand1)):
        printBarDouble()
        printDbg("length of command: " + str(len(bmcCommand1[i])), debug)
        printDbg("BMC command: " + str(bmcCommand1[i]))
        time.sleep(5)
        
        #ret1 = cli_with_ret(sshBmcD, bmcCommand1[i], "#", "linuxShell", 10)
        ret1 = pFi.mSp.mBlade.bmcSendCommand(sshBmcD, bmcCommand1[i])

        if re.search("File not found|No such file or directory", ret1):
            printErr("TFTP error: Error executing " + str(bmcCommand1[i]))
            return EXIT_ERR

        printDbg("ret1: \n" + str(ret1) + "\n")

        printDbg("Started tftp-ing the file...")
        printDbg("Waiting for TFTP to finish...")

        waitTimeTotal = 0

        # Start wait polling until file is finished tftp-ing.

        for j in range(0, CONFIG_BMC_TFTP_WAIT_RETRY):
            #ret1 = cli_with_ret(sshBmcD, "ps | grep tftp", "#", "linuxShell", 10)
            ret1 = pFi.mSp.mBlade.bmcSendCommand(sshBmcD, "ps | grep tftp")
    
            if re.search(pFileName[i], ret1):
                time.sleep(CONFIG_BMC_TFTP_WAIT_INTERVAL)
                waitTimeTotal += CONFIG_BMC_TFTP_WAIT_INTERVAL
                printDbg("tftp transfer of file name: " + str(pFileName[i]) + ". Wait time so far: " + str(waitTimeTotal) + " sec-s. Extending for another " \
                    + str(CONFIG_BMC_TFTP_WAIT_INTERVAL))
                printDbg("ret1: \n" + str(ret1) + "\n", debug)
            else:
                printDbg("tftp transfer is done.")
                break

            if i >= CONFIG_BMC_TFTP_WAIT_RETRY:
                printErr("Waited for more than " + str(CONFIG_BMC_TFTP_WAIT_INTERVAL * CONFIG_BMC_TFTP_WAIT_RETRY)\
                    + " sec-s for file being TFTP-d and not finished.")
                sshBmcD.close()
                return EXIT_ERR

        counter += 1
    sshBmcD.close()
    return SUCCESS

#   Sends a batch of UCSM function commands to save coding space.
#   It is possible that the connection drops during the execution of any of the command
#   streams, in which case, it will return EXIT_ERR immediately. 
#   req: 
#   - None
#   input:  
#   - pArrCommands - list of commands to send to UCSM cli.
#   - pBatchRet - if set to 1, then return will contain the list of every command's return value.
#   output: 
#   - output of last command if pBatchRet = 0 (default)
#     output of every command in list type if pBatchRet = 1.
#     EXIT_ERR - on any error condition 

def sendUcsmBatchCmd(pFi, pArrCommands, pBatchRet = 0):
    debug = 0
    stat = 0

    statList = []

    # Validate the input arguments.

    if pArrCommands == None:
        printErr("no command(s)")
        return EXIT_ERR

    # Send commands to ucsm.
    
    for i in pArrCommands:
        stat = cli_with_ret(pFi.ucsmSsh, i, pFi.hostName)
        time.sleep(2)

        # if error issuing command, return immediately.        

        if stat == EXIT_ERR:
            printErr("returned EXIT_ERR, EOL or some error?")
            return EXIT_ERR

        time.sleep(1)
        statList.append(stat)

    # Return either output of every command or last command based on pBatchRet.

    if pBatchRet == 1:
        return statList    
    elif pBatchRet == 0:
        return stat
    else:
        printErr("pBatchRet contains value other than 1 or 0. This is not recommended.")
        return EXIT_ERR

#   Determines the name of blade specific configuration file based on test bed ip
#   and location. In order to do so, it also needs to login to FI and determine the model
#   of the blade. The name of the file is used in opening or cloning the configuration file
#   by other API utilities in this module and other modules.
#   req:    
#   - None.
#   input:  
#   - pIp - UCSM IP.
#   - pLocation - blade location.
#   return: 
#   - name of config file to open if found
#     EXIT_ERR - if file is not found on the system or any other error.

def getConfigFileName(pIp, pLocation):
    debug = 1
    ucsmSsh = None
    user = None
    password = None
    bladePid = None
    bladeConfigFileName = None
    lFi = None

    # Create FI instance to use its resources.

    lFi = fi(pIp, pLocation)

    if lFi == None:
        printErr("Unable to initialize FI.")
        return EXIT_ERR

    # Login to UCSM to determine the blade PID.

    stat = cli_with_ret(lFi.ucsmSsh, "scope server " + pLocation, lFi.hostName)
    time.sleep(1)

    if re.search("Error:", str(stat)):
        printErr("Blade does not exist in " + str(pIp) + " " + str(pLocation))
        return EXIT_ERR

    stat = cli_with_ret(lFi.ucsmSsh, "show inventory | grep \"Equipped PID\" ", lFi.hostName)

    if stat:
        bladePid = stat.split()[-1]

    if bladePid == None:
        printErr("could not determine the blade PID.")
        return EXIT_ERR

    # Validate the PID value.

    if re.search("UCSB|N20|BASE", bladePid):
        printDbg("Valid PID found. " + str(bladePid), debug)

        # Construct blade config file name.

        bladeConfigFileName =  "config." + str(pIp) + "." + \
            str(re.sub("/",".", pLocation)) + "." + str(bladePid)

        printDbg("Blade specific configuration file name formed: " + str(bladeConfigFileName), debug)
        return bladeConfigFileName
    else:
        printErr("Unknown blade model." + str(bladePid))
        return EXIT_ERR

#   Constructs run-time file a.k.a global tmp log file.
#   It is created under PYTHON_ROOT_DIR/log path. The name of the file reflects
#   the currently running process to make it unique within concurrently running
#   scripts.
#   input:      
#   - pUcsmIp - UCSM test bed ip.
#   - pLocation - blade location.
#   return:     
#   - if file is created and configFile name is written to it.
#     EXIT_ERR if any error occurred.

def setConfigFileRuntime(pUcsmIp, pLocation):

    if validateFcnInput([pUcsmIp, pLocation]) == EXIT_ERR:
        printDbg("Invalid inputs.")
        return EXIT_ERR

    # Construct run time global tmp log file name.
    # Create it and write the name of blade specific config file name to it so that
    # non-driver tool can use it.

    configFile = getConfigFileName(pUcsmIp, pLocation)

    if configFile == EXIT_ERR:
        printErr("Failed to construct the blade specific config file name.")
        return EXIT_ERR

    tmpGlobalFileName = PYTHON_ROOT_DIR + "/log/tmp.global." + str(os.getpid()) + ".log"
    tmpGlobalFp = open(tmpGlobalFileName, 'a')
    tmpGlobalFp.write("configFile=" + configFile + "\n")
    tmpGlobalFp.close()
    return SUCCESS

'''
#   Validates location of blade string to be in x/y format
#   The chassis number up to 8 is supported. If chassis No. is higher than 
#   this function needs to be enhanced.
#   pReq:       
#   - None.
#   pLoc        
#   - blade location info.
#   return      
#   - EXIT_ERROR if format is not correct.
#     SUCCESS if format matches x/y.

def validateBladeLoc(pBladeLoc):
    if pBladeLoc == None:
        printErr("pBladeLoc is None.")
        return EXIT_ERR

    bladeLoc = pBladeLoc.split('/')

    try:
        if int(bladeLoc[0]) > 9 or int(bladeLoc[0]) < 1  or int(bladeLoc[1]) > 8 or int(bladeLoc[1]) < 1:
            printErr("1. location is not in x/y format or wrong chassis or blade No.")
            return EXIT_ERR
    except IndexError:
        printErr("Error parsing location")
        return EXIT_ERR

    return SUCCESS
'''

#   UCS boot-policy class implementation.
#   All aspects of boot-policy properties and methods should be implemented in this class.

class bp:
    bootMode = None
    secureBootState = None
    bpName = None

#   Iniitialization function called when the instance of this class is created as an object.

    def __init__(self, pBpName = None):
        printDbg("bp:__init__.")

        if pBpName:
            self.bpName = pBpName
        else:
            printWarn("Did not set the boot-policy name!")

        debug = 0

        printDbg("initialied", debug)

    # Set boot order numbers from boot-policy in pFi.
    # req:      
    # - None.
    # input:    
    # - pFi - FI instance.
    # output:   
    # - list of boot orders in integer format.
    #   EXIT_ERR - if for any failure including failure to set, fail to verify or timeout.

    def getBootOrderNumbers(self, pFi):
        debug = 0
        bootOrderNumbers = None
        bootOrderNumbersSplit = None
        bootOrderNumbersSplitInt = None
        bootOrderNumbersInt = []

        if validateFcnInput([pFi]) == EXIT_ERR:
            printErr("Input validation error")
            return EXIT_ERR

        # Get boot order entries from boot-policy.

        stat = sendUcsmBatchCmd(pFi, ['scope org','scope boot-policy ' + str(self.bpName),\
            'show expand | grep Order:'])

        if stat == None:
            printErr("Error with retrieving boot order numbers")
            return EXIT_ERR        

        # Split into list members.

        bootOrderNumbersSplit = stat.split("Order:")

        printDbg("boot order numbers: ", debug)
        
        if debug:
            print bootOrderNumbersSplit

        if len(bootOrderNumbersSplit) == 0:
            printErr("No boot order numbers found.")        
            return EXIT_ERR        

        for i in range(0, len(bootOrderNumbersSplit)):
            try:
                bootOrderNumbersInt.append(int(bootOrderNumbersSplit[i].strip()))
                printDbg("Added " + str(int(bootOrderNumbersSplit[i].strip())), debug)
                printDbg("bootOrderNumbersInt: ", debug)

                if debug:
                    printSeq(bootOrderNumbersInt)

            except Exception as Exception1:
                printWarnMinor("Can not convert " + str(i) + "th element to integer from boot order numbers.")
                print(Exception1)

        printDbg("Returning boot order: ", debug)
        
        if debug:
            printSeq(bootOrderNumbersInt)

        return bootOrderNumbersInt

    # Set boot mode to either uefi or legacy.
    # req:      None.
    # input:    
    # - pFi - FI instance.
    # - pBlade - blade instance.
    # - pMode - boot mode to set.
    # - pWait - wait until blade configuration is completed as a result of boot mode change.
    # - pVerify - verify boot mode is set.
    # output:   
    # - SUCCESS - if boot-mode is successfully set
    #   EXIT_ERR - if for any failure including failure to set, fail to verify or timeout.

    def setBootMode(self, pFi, pSp, pBlade, pMode, pWait = 1, pVerify = 0):
        pMode = pMode.lower()

        debug = 0
        stat = None

        # Validate function inputs.

        if validateFcnInput([pFi, pBlade, pSp, pMode]) == EXIT_ERR:
            printErr("Input validation error")
            return EXIT_ERR

        # Verify valid inputs for pMode.

        if pMode.lower() != 'legacy' and pMode.lower() != 'uefi':
            printErr("Invalid boot mode requested")
            return EXIT_ERR

        if self.bpName == None:
            printErr("bpName is not set.")
            return EXIT_ERR

        # Set the desired boot mode in boot-policy.

        if pWait:
            stat = sendUcsmBatchCmd(pFi, ['scope org','scope boot-policy ' + str(self.bpName),\
                'set reboot-on-update yes', 'set boot-mode ' + str(pMode), 'commit'])
        else:
            stat = sendUcsmBatchCmd(pFi, ['scope org','scope boot-policy ' + str(self.bpName),\
                'set boot-mode ' + str(pMode), 'commit'])

        if stat == EXIT_ERR:
            printErr("Error sending UCSM commands.")
            return EXIT_ERR

        # Idle until recofniguration of service-profile is finished if pWaut is not None.

        if pWait:
            if pSp.waitConfigComplete(pFi.ucsmSsh) == EXIT_ERR:
                printErr("Timed out waiting for configuration to complete.")
                return EXIT_ERR

        # Verify the boot-policy is set accordingly if pVerify is set.

        if pVerify:
            printWarn("Verification is not implemented.")

        printDbg("No verification needed.")
        return SUCCESS

    # Get boot mode currently set in the boot-policy.
    # req:      
    # - None.
    # input:    
    # - pFi - FI instance.
    # output:   
    # - "Uefi" string - if boot-mode is in uefi mode.
    #   "Legacy" string - if boot-mode is in legacy mode.
    #   EXIT_ERR - on any error condition.

    def getBootMode(self, pFi):
        debug = 0

        printDbg("Entered.", debug)

        # Validate function inputs.

        if validateFcnInput([pFi, self.bpName]) == EXIT_ERR:
            printErr("Error with required parameters.")
            return EXIT_ERR

        printDbg("Sending batch command to grep bootMode", debug)

        # Get the boot mode status from UCS boot-policy.

        stat = sendUcsmBatchCmd(pFi, ['scope org', 'scope boot-policy ' + str(self.bpName) ,\
            'show expand | grep "Boot Mode"'])

        printDbg("stat: " + str(stat))

        if stat == EXIT_ERR:
            printErr("Error sending UCSM commands.")
            return EXIT_ERR

        try:
            lBootMode = stat.split()[-1].strip()
        except IndexError:
            printErr("Error determining the boot-mode")
            return EXIT_ERR

        printDbg("Boot Mode found: " + str(lBootMode), debug)    

        if lBootMode == "Uefi":
            self.BootMode = 1
        elif lBootMode == "Legacy":
            self.BootMode = 0
        else:
            printErr("Invalid boot mode or error determining boot mode.")
            return EXIT_ERR

        return lBootMode

    # Get secure boot mode status from boot-policy.
    # req:      
    # - None.
    # input:    
    # - pFi - FI instance.
    # output:   
    # - "SecureBoot" string if in secure boot mode.
    # - "Uefi" string if in uefi mode.
    #   EXIT_ERR - if any error condition.

    def getSecureBoot(self, pFi):
        debug = 0

        # Validate inputs and pre-existing conditions.

        if validateFcnInput([pUcsmSsh, pSp]) == EXIT_ERR:
            printErr("invalid inputs.")
            return EXIT_ERR

        if self.bpName == None:
            printErr("bpName is not set.")
            return EXIT_ERR

        # Send the ucs command to determine the secure boot status from boot-policy.

        stat = sendUcsmBatchCmd(pFi, ['scope org' ,'scope boot-policy ' + str(self.bpName),\
            'show expand | grep "Secure Boot:"'])

        if stat == EXIT_ERR:
            printErr("Error executing UCSM commands.")
            return EXIT_ERR

        # Prepare return values. 

        if re.search("Yes", stat):
            self.secureBootState = "SecureBoot"
        elif re.search("No", stat):
            self.secureBootState = "Uefi"
        else:
            printErr("Unknown secure boot state. ")
            self.secureBootState = None
            return EXIT_ERR

        return self.secureBootState
        
    # Set secure boot mode in the boot-policy.
    # req:      None.
    # input:    
    # - pFi - FI instance.
    # - pSp - SP instance.
    # - pBlade - blade instance.
    # - pState - 'yes' to enabled, 'no' to disable.
    # output:   
    # - SUCCESS - if secure boot mode is successfully set
    #   EXIT_ERR - if for any failure including failure to set, fail to verify or timeout.
    # Note:     if blade is set in legacy mode, then it will automatically set to uefi mode before setting 
    # secure boot.
    # Note:     if boot-security object is not set yet, it will automatically be created.

    def setSecureBoot(self, pFi, pSp, pBlade, pState, pWait = 1, pVerify = 0):
        debug = 0
        stat = None

        # Validate function inputs.

        if validateFcnInput([pFi, pState]) == EXIT_ERR:
            printErr("Invalid inputs.")
            return EXIT_ERR

        # Validate pState values.

        pState = pState.lower()

        if pState == 'yes' or pState == 'no':
            printDbg("pState request is valid.", debug)
        else:
            printErr("Invalid secure boot state requested: " + str(pState))

        if self.bpName == None:
            printErr("bpName is not set.")
            return EXIT_ERR

        # Send set of commands to start setting the boot security mode.

        stat = sendUcsmBatchCmd(pFi, ['scope org', 'scope boot-policy ' + str(self.bpName), \
            'set reboot-on-update yes', 'commit', 'show boot-security | grep "Boot Security:"'])

        if stat == EXIT_ERR:
            printErr("Error sending UCSM commands.")
            return EXIT_ERR

        # Based on the previous output, either scope into or create boot security object.

        if re.search("Boot Security:", stat):
            stat = sendUcsmBatchCmd(pFi, ['scope boot-security', 'set secure-boot ' + str(pState), \
            'commit'])
        else:
            stat = sendUcsmBatchCmd(pFi, ['create boot-security', 'set secure-boot ' + str(pState), \
            'commit'])

        if stat == EXIT_ERR:
            printErr("Error sending UCSM commands.")
            return EXIT_ERR

        # Wait completaion of reconfiguration and verify the state if pWait and pVerify is set to 1
        # respectively.

        if pWait:
            if pSp.waitConfigComplete(pFi.ucsmSsh) == EXIT_ERR:
                printErr("Timed out waiting for configuration to complete.")
                return EXIT_ERR

        if pVerify:
            printWarnMinor("Verification is not implemented at this time.")
            printErr("Secure boot mode is not set correctly")
            return EXIT_ERR
        else:
            return SUCCESS

    # Set boot policy's various properties in bp instance object.
    # input:    
    # - pFi - FI instance.
    # - pWait 1: - wait until configuration is finished after setting.
    #         0: - do not need to wait till configuration is completed.
    # return:   
    # - SUCCESS - if refresh is successful.
    #   EXIT_ERR - if any error encountered.

    def refreshBp(self, pFi, pWait = 0):
        debug = 0

        # Validate inputs.

        if validateFcnInput([pFi]) == EXIT_ERR:
            printErr("invalid inputs.")
            return EXIT_ERR

        if pFi.mSp.spName:
            self.bpName = pFi.mSp.spName 
        else:
            printWarn("Unable to set bpName from service-profile.")
            return EXIT_ERR

            '''
            # Determine the bp's name.
        
            stat = sendUcsmBatchCmd(pFi, ['scope org', 'scope service-profile ' + str(pFi.mSp.spName),\
                'show boot-policy | egrep \"Uefi|Legacy\"'])
        
            printDbg("stat:\n" + str(stat), debug)
        
            if stat == EXIT_ERR:
                printErr("Error sending UCSM command")
                return EXIT_ERR
            
            if not re.search("Uefi|Legacy", stat):
                printErr("1. Unable to determine the spName.")
                return EXIT_ERR
        
            try:
                self.bpName = stat.split()[0].strip()
            except IndexError:
                printErr("2. Error determining the bpName.")
                return EXIT_ERR
        
            if self.bpName:
                printDbg("bpName is found: " + str(self.bpName), debug)
                return SUCCESS
            else:
                printErr("bpName is None.")
                return EXIT_ERR
            '''
        '''
        # Determine bp boot mode and secure boot mode and set the properties accordingly.
        if self.isUefi(pFi) == EXIT_ERR:
            return EXIT_ERR

        if self.isSecureBoot(pFi) == EXIT_ERR:
            return EXIT_ERR
        '''

        return SUCCESS

class blade:
    classString = "blade class instance info:"
    debug = 0

    location = None
    chassisNo = None
    slotNo = None
    spName = None
    ucsmMgmtIp = None
    ucsmHostName = None
    bmcDbgIp = None
    debugCli = None    
    bmcDbgSsh = None
    pid = None
    fiHostName  = None
    efiShellBootUpTimesKey = None
    tpmPid = None
    serialNo = None
    bmcSsh = None

    mgmtIp = None
    mgmtUsername = 'admin'
    mgmtPassword = 'Nbv12345'
    versionBios = None

#   Iniitialization function called when the instance of this class is created as an object.

    def __init__(self, pLocation = None, pSpName = None):        
        debug = 0
        printDbg("blade:__init__ param-s: (pLocation)", debug)
        print pLocation

        if pLocation:
            self.setLocation(pLocation)
        else:
            printDbg("Did not set location. Blade property such as bios version can not be determined.")

        if pSpName:
            self.spName = pSpName
        else:
            printDbg("Did not set the blade spName. May need to set through refreshBlade().")

    # Return sp infomation in a dictionary format.
    # req:      
    # - None.
    # input:    
    # - None.
    # return:   
    # - class sp instantiation object
    #   EXIT_ERR if tpm is not found or any other error. 

    def getSpInfo(self, pUcsmSsh):
        debug = 0
        mSp = None

        mSp = sp(self.spName)
        mSp.fiHostName = fi.hostName
    
        if mSp:
            printDbg("sp info:")
            printDic(mSp)
        else:
            printErr("Unable to instantiate sp object")
            return EXIT_ERR
        
        if mSp.refreshSp(pUcsmSsh) == EXIT_ERR:
            printDic(mSp)
            printErr("can not set blade location. quitting")
            return EXIT_ERR

        return sp

    #   Determine whether TPM (either 1.2 or 2.0 exists on the system).
    # req:    
    # - None.
    # input:  
    # - pUcsmSsh - ucsm sol connection
    # - pBmcSsh - bmc sol connection
    # - pBlade - blade instance
    # return: 
    # - dictionary containing tpm information.
    # - EXIT_ERR if TPM is not found or any other error.
    
    def isTpmPresent(self, pUcsmSsh):
    
        # Verify tpm presence.
    
        tpm = self.getTpmInfo(pUcsmSsh)
    
        if not tpm:
            printErr("error gathering tpm information")
            return EXIT_ERR

        tpmModelList = ["UCSX-TPM2-001", "UCSX-TPM1-001", "UCSX-TPM2-002", "UCSX-TPM1-002"]
        try:

            for i in tpmModelList:
                if tpm['Model'].strip() == i:
                    printInfoToFile("tpmInfo: ")
                    #fprintSeq(tpm) # fprint has bug when type is dict: fix it!
                    printSeq(tpm)
                    return tpm
            else:
                printErr("TPM device does not exist.")
                return EXIT_ERR
        except KeyError:
                printErr("failed to obtain model field, can not determine TPM revision: ")
                return EXIT_ERR
    
    # return tpm infomation in a dictionary format.
    # input:    
    # - pFi - SSH connection to Fabric Interconnect CLI. 
    # return:   
    # - dictionary containing tpm information.
    #   EXIT_ERR if tpm is not found or any other error. 

    def getTpmInfo(self, pFi):
        tpmInfo = {}
        debug = 0

        stat = sendUcsmBatchCmd(pFi, ['"scope server " + self.location', "scope tpm 1",\
            'show detail'])

        items = ['Model', 'Revision', 'Serial', 'Ownership', 'Enabled']
    
        for item in items:
            if re.search(item + ":", stat):
                printDbg("found " + str(item), debug)

                for i in stat.split('\n'):

                    if re.search(item + ":", i):
                        printDbg("Updating item: " + str(item) + " with " + str(i).strip().split(":")[-1].strip(), debug)
                        tpmInfo[item] = str(i).strip().split(":")[-1].strip()        
            else:
                printDbg("did not find " + str(item), debug)
    
        if len(tpmInfo):
            printSeq(tpmInfo)
            return tpmInfo
        else:
            printErr("Did not locate any tpm information from this blade.")
            return EXIT_ERR

	# This function might be redundant. Check and delete if so.
    # Given ssh handle to ucsm, set the management IP.
    # input:
    # - pUcsmSsh - ssh handle to UCSM.
    # - pFI - instance.
    # - pBladeLocation - blade location info.
    # return:
    # - EXIT_ERR if fails to sets the bmc management IP.
    #           - SUCCESS if sets the bmc management ip successfully.
    
    def setMgmtIp(self, pUcsmSsh, pFi, pBladeLocation):
        debug = 0

        if self.mgmtIp:
            printDbg("management ip is already set.") 

        if pUcsmSsh == None:
            printErr("UCSM ssh is not initialized.")
            return EXIT_ERR

        printDbg("Entered:")
        lFilterString = '255.'

        out1 = cli_with_ret(pUcsmSsh, "scope server " + pBladeLocation, self.fiHostName)
        time.sleep(1)
        out1 = cli_with_ret(pUcsmSsh, "scope cimc", self.fiHostName)
        time.sleep(1)

        out1 = cli_with_ret(pUcsmSsh, "show mgmt-if | grep " + lFilterString, self.fiHostName)
    
        printDbg("show mgmt-if output: " + str(out1), debug)
        out1 = str(out1).strip()
        self.mgmtIp = out1.split(' ')[0].strip()

        if self.mgmtIp.strip() == "" or self.mgmtIp.strip() == None:
            printErr("bmc management IP not found")
            return EXIT_ERR
        else:
            printDbg("BMC management IP found: "  + self.mgmtIp)
            return SUCCESS

    # Poll in idle state until the blade fsm status and blade status are all clear.
    # Blade fsm status is checked by "scope server x/y and show fsm status" and waits untill all 3 progress indicator
    # reached 100%. This normally allows it to wait until some pending operation i.e. cmos clear, firmware update etc.,
    # Also secondly, the blade status is checked by "scope server x/y and show status" command and waits until
    # pending operation is complete and status becomes "OK" or "degraded". This causes wait until discovery/association or 
    # re-configuration change due to bios policy is done"
    # input:
    # - pUcsmSsh - ssh connection to UCSM.
    # - pSecWaitLimit - number of sec. to wait (default 900) until blade is in ready state.
    # - pSecInterval - interval in seconds to display the status while waiting for blade to become in ready state.
    # return:
    # - SUCCESS - if blade is in ready state within timeout (pSecWaitLimit).
    #   EXIT_ERR - if blade is not in ready state within timeout. 

    def waitTillBladeReady(self, pUcsmSsh, pSecWaitLimit = 900, pSecInterval = 15):
        debug = 0
        counter = 0

        while 1:
            ret1 = cli_with_ret(pUcsmSsh, "show fsm status | grep Progress", self.fiHostName)
            time.sleep(1)
            printDbg("ret1: \n================\n" + str(ret1) + "\n=================\n", debug)
            ret2 = ret1.strip().split('\n')
            printDbg("ret2: \n================\n" + str(ret2) + "\n=================\n", debug)
    
            ret1a = cli_with_ret(pUcsmSsh, "show status | grep " + self.location, self.fiHostName)
            printDbg("ret1a: \n================\n" + str(ret1a) + "\n=================\n", debug)
            ret2a = ret1a.strip().split()[3].strip()
            printDbg("ret2a: \n================\n" + str(ret2a) + "\n=================\n", debug)
    
            if re.search(".*Progress.*100", ret2[0]):
                printDbg("fsm1 progress is clear.")
    
                if re.search(".*Progress.*100", ret2[1]):
                    printDbg("fsm2 progress is clear.")
    
                    if re.search(".*Progress.*100", ret2[2]):
                        printDbg("fsm3 progress is clear.")
    
                        if re.search("Ok|Degraded|Power|Inoperable|Thermal", ret2a.strip()):
                            printDbg("blade status is clear. \nBlade is free of any pending activity now...")
    
                            if ret2a == "Degraded|Inoperable|Thermal":
                                printWarn("Blade is in degraded/inoperable/thermal mode. Check the blade!")
                            break
                    else:
                        printDbg("fsm3 progress is NOT clear.")
                        printDbg("waiting for pending activity to complete. sleep " + str(pSecInterval) + " sec. Retry " + str(counter))
                        time.sleep(pSecInterval)
                        counter += 1
                else:
                    printDbg("fsm2 progress is NOT clear.")
                    printDbg("waiting for pending activity to complete. sleep " + str(pSecInterval) + " sec. Retry " + str(counter))
                    time.sleep(pSecInterval)
                    counter += 1
            else:
                printDbg("fsm1 progress is NOT clear.")
                printDbg("waiting for pending activity to complete. sleep " + str(pSecInterval) + " sec. Retry " + str(counter))
                time.sleep(pSecInterval)
                counter += 1
    
                if counter > (pSecWaitLimit /  pSecInterval):
                    printErr("cmos-reset can not be completed in " + str(pSecWaitLimit/60) + " minutes. Giving up.")
                    return EXIT_ERR
        return SUCCESS

    # This function will return status of certain items of smbiostable 204 table.
    # Prior to calling this function, blade must be in efi shell.
    # input:
    # - pBmcSsh   - handle to bmc sol ssh connection.
    # - pStatName - entities for which the status is to be returned.
    #           Allowed values - return values are:    #
    #           tpmPresence - 1 if tpm present, 0 if not.
    #           tpmState    - 1 if tpm is on, 0 if off.
    #           tpmActive   - 1 if activated, 0 if not.
    #           tpmOwned    - 1 if owned, 0 if not.
    #           txtState    - 1 if txt enabled, 0 if not.
    #           ... further enhancement also possible
    #
    # return: 
    # - see pStatName above.
    #   EXIT_ERR if any error occurred.

    def getSmbios204Stat(self, pBmcSsh, pStatName):
        debug = 0
        stat = None
        rx08String = None
        rx00String = None

        tpmStatesSupported = ['tpmPresence','tpmState','tpmActive','tpmOwne', 'txtState']

        if not pStateName in tpmStatesSupported:
            printErr("pStateName is not supported: " + str(pStateName))
            return EXIT_ERR

        printDbg("pStatName: " + str(pStatName), debug)

        efiShellOutput = cli_with_ret(pBmcSsh, "smbiosview -t 204", "", "efiShell")
        
        if efiShellOutput == EXIT_ERR:
            printErr("Unable to get efi shell output.")
            return EXIT_ERR
            
        m = re.search("00000000:.*-.*", efiShellOutput)
    
        if m:
            m1 = str(m.group(0))
            m1 = re.sub("00000000: ", "", m1)
            m1 = re.sub("  .*", "", m1).strip()
            printDbg("smbiosview -t 204 output: \n" + str(m1) + "\n", debug)
    
            try:
                tokens = m1.split('-')
                printDbg("tokens: ", debug)
                printSeq(tokens)

                rx00String = tokens[0].strip()
                rx08String = tokens[1].strip()
                printDbg("Rx08h - Rx0fh String: " + str(rx08String), debug)
                printDbg("Rx00h - Rx07h String: " + str(rx00String), debug)

                rx00Tokens = rx00String.split()
                rx08Tokens = rx08String.split()
                printDbg("Rx00 tokens: ", debug)
                printSeq(rx00Tokens)
                printDbg("Rx08 tokens: ", debug)
                printSeq(rx08Tokens)

                if pStatName == "tpmPresence":           
                    stat = (int(rx08String.split()[0].strip(), 16) & 0x01) >> 00
                elif pStatName == "tpmState":            
                    stat = (int(rx08String.split()[0].strip(), 16) & 0x02) >> 01
                elif pStatName == "tpmActive":            
                    stat = (int(rx08String.split()[0].strip(), 16) & 0x04) >> 02
                elif pStatName == "tpmOwned":            
                    stat = (int(rx08String.split()[0].strip(), 16) & 0x08) >> 03
                elif pStatName == "txtState":            
                    stat = (int(rx08String.split()[2].strip(), 16) & 0x01) >> 00
                else:
                    printErr("unsupported stat name: " + str(pStatName))
                    return EXIT_ERR    

            except ValueError:
                printErr("Unable to parse the smbios status string")
                return EXIT_ERR

            try:    
                printDbg("final stat: " + str(stat))
                int(stat)
                return int(stat)
            except ValueError:
                printErr("Unable to parse the smbios stat for " + str(pStatName))
                return EXIT_ERR

    # This will return the single line from dmpsetup output specified by input. 
    # Note that this will not execute dmpsetup command instead scan through ucsm token list file.
    # input:    
    # - pTokenUcsm - name of ucsm token.
    # - pSubTokenUcsm - name of sub ucsm token.
    # output:   
    # - dmpsetup line for pTokenUcsm/pSubTokenUcsm.
    # - EXIT_ERR - if any error encountered including corresponding line can not be found 
    #           in the ucsm token file.
    # Note: this function is likely be obsolete starting from M5 series proj.

    def ucsmToDmpSetupToken(self, pBiosToken, pBiosTokenL2):
        debug = 0
        debugL2 = 0
        counter = 0

        printDbg("entered.")

        if validateFcnInput([pBiosToken, pBiosTokenL2]) == EXIT_ERR:
            printErr("Error with input.")

        printDbg("reading ucsm.token.list file", debug)

        # open the token list file.

        fpUcsmToken = open(PYTHON_ROOT_DIR + "api/ucsm.token.list.txt", 'r')

        if not fpUcsmToken:
            printErr("unable to open ucsm token list file")
            return EXIT_ERR
        else:
            printDbg("Open success, fpUcsmToken: " + str(fpUcsmToken), debug)

        while 1:
            line = fpUcsmToken.readline()

            if counter == 0:
                counter += 1
                continue

            if line:
                printDbg(str(counter) + ". line: " + str(line), debugL2)

                if debugL2:
                    printSeq(line.split('|'))

                try:
                    lineTokens = line.split('|')
                    if len(lineTokens) < 4:
                        printWarn("invalid line or end of file before finding a token match")
                        break

                    if pBiosToken == lineTokens[1].strip() and pBiosTokenL2 == lineTokens[2].strip():
                        printDbg("found the token name from token list file: " + pBiosToken, debug)
                        lDmpsetupName = lineTokens[0].strip()

                        printDbg("found the token name from token list file: " + pBiosToken, debug)
                        lDmpsetupName = lineTokens[0].strip()
                        return lDmpsetupName

                except IndexError:
                    printErr("error parsing, unknown index while searching for token name, token verification failed...")
                    break
                except AttributeError:
                    printErr("error parsing, none type has no strip attribute while searching for token...")
                    break
            else:
                printDbg("line is empty. EOF. done reading ucsm token file. Can not find the token...")
                break

            counter += 1

        printDbg("read " + str(counter) + " lines. Unable to find the matching line.", debug)
        fpUcsmToken.close()
        return EXIT_ERR

    # This function will attempt to set the pid field of the instance of class based on slot info.
    # input:
    # - pUcsmSsh  - handle to UCSM ssh connection.
    # - pFi - testbed object.
    # return:    
    # - SUCCESS - if PID is set correctly. 
    # - EXIT_ERR - on any error condition.

    def setPid(self, pUcsmSsh, pFi = None):
        ret = None
        debug = 0

        ret = cli_with_ret(pUcsmSsh, "scope server " + self.location, self.fiHostName)
        time.sleep(1)
        printDbg("ret1: " + str(ret), debug)

        ret = cli_with_ret(pUcsmSsh, "show inventory | grep 'Acknowledged PID'", self.fiHostName)
        time.sleep(1)
        printDbg("ret2: " + str(ret), debug)

        try:
            self.pid = ret.split()[-1]
            printDbg("PID is set to " + self.pid, debug)
            return SUCCESS
        except IndexError:
            printErr("Error setting PID.")
            return EXIT_ERR

    # This function will attempt to assign the BMC DHCP IP.
    # At least one IOM must be connected to SOL and also connected to corp-net ethernet network
    # in order for it to work.
    # input:
    # - pFi       
    # - testbed
    # - pForce - 1: if telnet connection to IOM is denied, it will clear the line from serial server and will re-attempt
    #            0: if telnet connection to IOM is denied, it will return with EXIT_ERR 
    # - pInternal - 1: will attempt login to cmc from bmc
    #             - 0: will attempt loing to cmc externally through serial server
    # return:
    # - SUCCESS if DHCP IP is assigned, EXIT_ERR if failed.

    def bmcDbgGetDhcpIp(self, pFi, pForce=0, pInternal=0):
        debug = 0
        ret1 = None
        bmcDbgSsh = None

        bmcDbgSsh = self.bmcDbgLogin(pFi)

        if bmcDbgSsh == EXIT_ERR:
            printErr("unable to login to bmc debug console.")
            return EXIT_ERR

        # Check if bmc has IP already assigned first

        ret1 = cli_bmc_dbg(bmcDbgSsh, "ifconfig | grep 10\.193\.")
        time.sleep(1)
        printDbg("ret1: \n---\n " + str(ret1) + "\n---\n", debug)

        if re.search("[0-9]*\.[0-9]*\.[0-9]*\.[0-9]* ", ret1):
            print "This BMC debug login console already has 10.193.x.x IP address assigned"
            print "IP address: " + str(ret1.strip().split()[1].split(':')[1])

            if bmcDbgSsh:
                return ret1.strip().split()[1].split(':')[1]
        else:
            print "BMC does not have IP assigned, attempting to assign. "

        for tryNo in range (0, 1):
            printDbg("tryNo: " + str(tryNo), debug)

            if bmcDbgSsh == EXIT_ERR:
                printErr("BMC debug login failed. Can not continue")
                return EXIT_ERR

            ret1 = cli_bmc_dbg(bmcDbgSsh, "/etc/init.d/firewall stop")
            print "ret1: \n---\n" + str(ret1) + "\n---\n"
    
            # try getip.sh 0 and 1 both.

            for i in range(0, 2):
                ret1 = cli_bmc_dbg(bmcDbgSsh, "/etc/scripts/getip.sh " + str(i))
                print "ret1: \n---\n" + str(ret1) + "\n---\n"

                if re.search("No lease, forking to background", str(ret1)):
                    printDbg("getip "+ str(i) +"  failed on interface " + str(i))
                elif re.search("Lease of.*obtained", str(ret1)):
                    printDbg("Successfully obtained DHCP IP")
    
                    if validateIp(ret1.split()[2].strip()):
#                       return ret1.strip().split()[1].split(':')[1]
                        return ret1.split()[2].strip()
                    else:
                        print "Warning: DHCP IP lease obtained but unable to validate the IP address."
                        return NO_EXIT_ERR
    
            # for try=0 fail, try CMC, if try=1 exit immediately.
    
            if tryNo == 0:
                print "BMC DHCP IP without CMC failed, trying CMC now..."

                if pInternal:
                    self.cmcGetDhcpIpFromBmc(bmcDbgSsh)
                else:        
                    if pFi.cmcGetDhcpIp(pForce, 1):            
                        printDbg("CMC DHCP IP lease is successful. Now trying BMC DHCP IP.", debug)
                    else:
                        printErr("CMC DHCP IP lease failed. Can not continue.")
                        return EXIT_ERR
            else:
                print "BMC DHCP IP with CMC failed, giving up."
                return EXIT_ERR

    # get CMC DHCP IP by telnetting from BMC (not working).
    # Must be called from BMC dbg console, no exception
    # input:
    # - pBmcDbgSsh - bmc debug ssh console
    # return        
    # - SUCCESS - if it gets DHCP IP
    # - EXIT_ERR if fail to get DHCP IP

    def cmcGetDhcpIpFromBmc(self, pBmcDbgSsh):
        debug = 0
        debugL2 = 0
        debugCli = 0
        ret1 = None

        if pBmcDbgSsh == None:
            printErr("ssh to bmc debug does not exit")
            return EXIT_ERR

        cmcIpInt = ['127.3.0.254','127.4.0.254']

        for i in cmcIpInt:
            ret1 = cli_bmc_dbg(pBmcDbgSsh, "telnet " + i, "cmc.*login", 1) 
            printDbg("ret1: " + str(ret1))
            time.sleep(1)

            ret1 = cli_bmc_dbg(pBmcDbgSsh, "root", "Password:", 1)
            printDbg("ret1: " + str(ret1))
            time.sleep(1)

            ret1 = cli_bmc_dbg(pBmcDbgSsh, "cmc", "#", 1)
            printDbg("ret1: " + str(ret1))
            time.sleep(1)

            ret1 = cli_bmc_dbg(pBmcDbgSsh, "cms -c altproduction,pfw=bmcdbg", "cmc.*#", 1)
            printDbg("ret1: " + str(ret1))
            time.sleep(1)

            ret1 = cli_bmc_dbg(pBmcDbgSsh, "cms dbgon", "cmc.*#", 1)
            printDbg("ret1: " + str(ret1))
            time.sleep(1)

            '''
            pBmcDbgSsh.sendline("telnet " + i)
            pBmcDbgSsh.expect("cmc.*login") 
            time.sleep(1)

            pBmcDbgSsh.sendline("root")
            pBmcDbgSsh.expect("Password:") 
            time.sleep(1)

            pBmcDbgSsh.sendline("cmc")
            pBmcDbgSsh.expect("#") 
            time.sleep(1)

            pBmcDbgSsh.sendline("cms -c altproduction,pfw=bmcdbg")
            pBmcDbgSsh.expect("cmc.*#") 
            time.sleep(1)

            pBmcDbgSsh.sendline("cms dbgon")
            pBmcDbgSsh.expect("cmc.*#") 
            time.sleep(1)

            '''

            ret1 = cli_bmc_dbg(pBmcDbgSsh, "/usr/bin/getip.sh 0", "cmc.*#", 1)
            time.sleep(1)
        
            if re.search("Lease.*obtained", str(ret1)):
                printDbg(str(i) + " succeeded." )
                ret1 = cli_bmc_dbg(pBmcDbgSsh,  "exit")
                printDbg("should be back to BMC: " + str(ret1))
                return SUCCESS
            elif re.search("No lease", ret1):
                printDbg(str(i) + " failed." )
            else:
                printDbg("Unknown returns, assuming failed.")

        printDbg("can not get DHCP IP on CMC internally from BMC. Closing telnet and back to bmc debug console.")

        ret1 = cli_bmc_dbg(pBbgSsh, "exit", "IBMC-SLOT\[.\] #",1)
        return EXIT_ERR

    # Logon to RH1 and interact with CID server to get back the challenge Response string.
    # input:
    # - pChallengeKey - challengekey string, it may have garbages.
    # - pRh1TargetPw - RH1 password.
    # return:
    # - responseString if successful.
    # - EXIT_ERR if any error is encountered.

    def cidProcessChallengeKey(self, pChallengeKey, pRh1TargetPw):
        configEnableSwimsTicket = getGlobal('CONFIG_ENABLE_SWIMS_TICKET')
        debug = 0
        debugCli = 0
        debugL2 = 0
        sshRh1 = None
        ticketRecreated = 0

        if configEnableSwimsTicket:
            productCode = swimsPidToProduct(self.pid)
    
            if productCode:
                printDbg("OK. Found product code by PID.: " + str(productCode), debug)
            else:
                printDbg("Fail. Did not find product code by PID: " + str(self.pid))
                return EXIT_ERR
    
            ticketFileName = self.pid + "-ticket.tic"
            ticketFileNameFull = "/users/ggankhuy/ticket/" + ticketFileName
            printDbg("ticketFileName: " + str(ticketFileName), debug)
    
            cidCommandTicket = "cat " + ticketFileNameFull
    
        # Login to RH1 and send the challenge key and get the response back

        RH1_USERNAME = getGlobal('CONFIG_RH1_SERVER_UNAME')
        printDbg("retrieved username: " + str(RH1_USERNAME), debug)                    

        if RH1_USERNAME == None:
            printErr("Unable to retrieve RH1 username.")
            return EXIT_ERR

        RH1_PASSWORD = pRh1TargetPw

        if RH1_PASSWORD == None:
            printErr("Unable to retrieve CEC password") 
            return EXIT_ERR

        printDbg("Logging into RH1 server.")
        sshRh1 = sshLogin(RH1_IP, RH1_USERNAME, RH1_PASSWORD)                    

        if sshRh1 == None:
            printErr("Unable to login to RH1 server")
            return EXIT_ERR

        printDbg("Logged onto RH1 server.", debug)

        if configEnableSwimsTicket:
            printDbg("Obtaining ticketValue with command: " + str(cidCommandTicket))
            ticketValue = cli_with_ret(sshRh1, cidCommandTicket, "\[.*\].*$", "linuxShell")
            printDbg("ticketValue: \n----------\n" + str(ticketValue) + "\n--------\n", debug)

            if ticketValue == None:
                printErr("Unable to get ticketValue. ")
                return EXIT_ERR
            
            if re.search("No such file or directory", ticketValue):
                printWarn("Ticket does not exist. It needs to be created.")
                listTicketCreateData = swimsCreateTicket(self, productCode)
        
                if listTicketCreateData == EXIT_ERR:
                    printErr("Failed to create the ticket.")
                    return EXIT_ERR

                if ticketFileName != listTicketCreateData[1].strip():
                    printErr("Original ticket name and new ticket name does not match.\
                    this is not supposed to happen: " + str(ticketFileName) + " : " + \
                    str(listTicketCreateData[1]) + "len: " + str(len(ticketFileName)) + "|" \
                    + str(len(listTicketCreateData[1].strip())))
                    return EXIT_ERR                                                    

                printDbg("Retry obtaining ticketValue.")
                ticketValue = cli_with_ret(sshRh1, cidCommandTicket, "\[.*\].*$", "linuxShell")

                if re.search("No such file or directory", ticketValue):
                    printErr("Ticket does not exist after creating ticket.")
                    return EXIT_ERR

                printDbg("TicketValue is obtained.")
                ticketRecreated = 1                            
            else:
                printDbg("Using existing ticket. No need to re-create ticket.")

        # start RH1 interation loop
        # login to CID server
        # construct cid server retrieve response command.

        printDbg("Logging using new CID server")
        printDbg("Challenge string: " + str(pChallengeKey), debug)
        printDbg("line1: " + str(pChallengeKey.strip().split('\n')[0]) + ":" + str(len(pChallengeKey.strip().split('\n')[0])), debug)
        printDbg("line2: " + str(pChallengeKey.strip().split('\n')[1]) + ":" + str(len(pChallengeKey.strip().split('\n')[1])), debug)
        time.sleep(5)

        if configEnableSwimsTicket:
            cidServer = "cid.cisco.com"
            cidCommand = "ssh -A -p 19027 " + cidServer + " retrieve-response " + \
                str(ticketValue) + " " + \
                str(pChallengeKey.strip().split('\n')[0]) + " " + pChallengeKey.strip().split('\n')[1]
        else:
            cidServer = "cid.cisco.com"
            cidCommand = "ssh -A -p 19027 " + cidServer + " retrieve-response " + \
                pChallengeKey.strip().split('\n')[0] + " " + str(pChallengeKey.strip().split('\n')[1])

        cidCommand = cidCommand.strip()

        printDbg("====================", debug)
        printVar(cidCommand, debug)
        printDbg("====================", debug)
        printDbg("cid command len: " + str(len(cidCommand)), debug)

        cidCommand1 = ""

        # Somehow the constructed command still had carriage return in it which was causing failure in cid command.
        # use following snippet of code to remove any NL and CR chars. 

        for i in cidCommand:
            if debugL2:
                print hex(ord(i))

            if ord(i) == 13:
                if debugL2:
                    printErr("found CR")
            elif ord(i) == 10:
                if debugL2:
                    printErr("found NL")
            else:
                cidCommand1 += i
        printDbg("cid command 1 len: " + str(len(cidCommand1)), debug)
        cidCommand = cidCommand1

        counterPassPhraseCount = 0
        counterTimeOut = 0

        # CID interaction loop

        printDbg("Interacting with CID server now from RH1 server through pexpect loop...")

        index1 = 0
        counter = 0

        while 1:
            if index1 == 2:
                printDbg(str(counter) + ". CID interaction loop index1: " + str(index1) + ", sending password ****", debug)
            else: 
                printDbg(str(counter) + ". CID interaction loop index1: " + str(index1) + ", sending " + str(cidCommand), debug)

            sshRh1.sendline(cidCommand)
            time.sleep(2)

            index1 = sshRh1.expect([\
                pexpect.TIMEOUT,\
                pexpect.EOF, \
                "This is your AD password:",\
                "Please enter your selection:", \
                "Please provide the challenge:", \
                "Hit Any Key to Continue. Yes, please find the any key.",\
                ".*Logon to Signing Request Delta Time:.*",\
                #".*Ticket may be expired.*",\
                #".*Internal Error.*"
                #".*Response String"
                 ], re.DOTALL)                

            ret1 = sshRh1.after #!!!!!

            printDbg("index: " + str(index1), debug)
            printPexBa(sshRh1, debug)

#           if index1 == 7 or index1 == 8 or index1 == 6 or index1 == 9:
            if index1 == 6:
                if getGlobal('CONFIG_BMC_LOGIN_NEW') == 1:
                    if configEnableSwimsTicket:
                        if re.search("Response String", ret1, re.DOTALL):
                            printDbg("Found response string.")

                            # by this time the ret1 should have string containing challenge response    
            
                            challengeResponse = extractChallengeString(ret1)
                            printDbg("challengeResponse stripped(2): " + str(challengeResponse), debug)
            
                            if challengeResponse == None:
                                printErr("Challenge response is None.")
                            else:    
                                bmcCommand = challengeResponse
                                break

                        elif re.search("Challenge string is not entered correctly.", ret1, re.DOTALL):
                            printDbg("Challenge string is not entered correctly, could be corrupted ticket.")
                        elif re.search("Internal Error.", ret1, re.DOTALL):
                            printDbg("Challenge string is not entered correctly, could be corrupted ticket.")
                        else:
                            printDbg("Unknown response.")

                        # If ticket is already created, then exit with error.
                        # If ticket is not created before during this call to this function, re-create one more time
                        # and try issuing. 

                        if ticketRecreated == 0:
                            printDbg("Creating again ticket one more time.")
                            ticketRecreated = 1

                            listTicketCreateData = swimsCreateTicket(self, productCode)

                            if listTicketCreateData == EXIT_ERR:
                                printErr("Failed to create the ticket.")
                                return EXIT_ERR

                            if ticketFileName != listTicketCreateData[1]:
                                printErr("original ticket name and new ticket name does not match.\
                                this is not supposed to happen: " + str(ticketFileNameFull) + " : " + \
                                str(listTicketCreateData[1]))
                                return EXIT_ERR

                            printDbg("Ticket is created or re-created. Sending the command again.")
                            ticketRecreated = 1
                            printDbg("Obtaining ticketValue.")
                            printDbg("cidCommandTicket" + str(cidCommandTicket))

                            sshRh1.close()
                            sshRh1 = sshLogin(RH1_IP, RH1_USERNAME, RH1_PASSWORD)                    

                            ticketValue = cli_with_ret(sshRh1, cidCommandTicket, "\[.*\].*$", "linuxShell")

                            printDbg("ticketValue: " + str(ticketValue))

                            cidServer = "cid.cisco.com" 
                            cidCommand = "ssh -A -p 19027 " + cidServer + " retrieve-response " + \
                                str(ticketValue) + " " + \
                                str(pChallengeKey.strip().split('\n')[0]) + " " + pChallengeKey.strip().split('\n')[1]

                            cidCommand1 = ""

                            for i in cidCommand:
                                if debugL2:
                                    print hex(ord(i))
                    
                                if ord(i) == 13:
                                    if debugL2:
                                        printErr("found CR")
                                elif ord(i) == 10:
                                    if debugL2:
                                        printErr("found NL")
                                else:
                                    cidCommand1 += i

                            printDbg("cid command 1 len: " + str(len(cidCommand1)), debug)
                            cidCommand = cidCommand1
                        else:
                            printErr("CID server failed to respond with new ticket. Ticket has been re-created one more time before.")
                            printErr("Check your ssh key.")
                            return EXIT_ERR
                    else:
                        # Somehow this expect loop unable to recognize the Welcome string which should cause index1 to 6.
                        # therefore here in timeout, just give the ret1 to extractChallengeString command and see if it returns
                        # non-null string. If so, assume it is good. (warning there could be danger in using this!!
                            
                        challengeResponse = extractChallengeString(ret1)

                        if challengeResponse != None:
                            printDbg("challengeResponse stripped(3): " + str(challengeResponse), debugL2)
                            break                                    
                        else:
                            print "could not extract response string"
                            printErr("Did not get the cid password prompt, extending...")
                            counterTimeOut += 1

                            if counterTimeOut > 3:
                                printErr("timeout counter exceeded. ")
                            return EXIT_ERR

                else:    
                    printErr("Did not get the cid password prompt, extending...")
                    counterTimeOut += 1

                    if counterTimeOut > 5:
                        printErr("timeout counter exceeded. ")
                        return EXIT_ERR
           
            elif index1 == 0:
                printErr("Timeout waiting for response.")
                return EXIT_ERR
            elif index1 == 1:
                printErr("reached EOF")
                return EXIT_ERR
            elif index1 == 2:
                RH1_PASSWORD = getPw("CEC")

                if RH1_PASSWORD == None:
                    printErr("Unable to retrieve CEC password") 
                    return EXIT_ERR

                printDbg("sending RH1 cid password")
                cidCommand = RH1_PASSWORD
            elif index1 == 3:
                printDbg("sending 1 - Retrieve response")
                cidCommand = "1"
            elif index1 == 4:
                printDbg("sending challenge Key")
                cidCommand = pChallengeKey
            elif index1 == 5:
                printDbg("Got the challenge response(1)")
                printPexBa(sshRh1, debug)

                # by this time the ret1 should have string containing challenge response    

                challengeResponse = extractChallengeString(ret1)
                printDbg("challengeResponse stripped(1): " + str(challengeResponse), debugL2)
                bmcCommand = challengeResponse
                break
            elif index1 == 100:
                # can not happen in plaintext! need to encrypt the passphrase!!!

                if getGlobal('CONFIG_BMC_LOGIN_NEW') == 1:
                    printDbg("sending passphrase") 
                    cidCommand = 'Nbv123\r'
                else:
                    printDbg("sending passphrase (empty)")
                    cidCommand = '\r'
                    counterPassPhraseCount += 1

                    if counterPassPhraseCount > 10:
                        printErr("Server is not accepting passphrase, tried 10 times. Giving up.")
                        return EXIT_ERR
            else:
                printDbg("Warning! Unknown index, index1 : " + str(index1))

            counter += 1

        # end cid interaction loop.

        return challengeResponse

    # This function will attempt to login to blade's bmc debug console
    # input:
    # - pFi - fabric interconnect object instance
    # return:   
    # - SOL connection to BMC debug console, EXIT_ERR if failure.
    # - TELNET connection to debug console, if front dongle option is enabled. (CONFIG_BMC_LOGIN_TELNET)

    def bmcDbgLogin(self, pFi, pRh1TargetPw):
        debug = 0
        debugL2 = 0
        debugCli = 0
        index1 = 0
        counter = 0
        ret1 = None
        challengeKey = ""
        challengeResponse = ""
        ucsmSsh4Bmc = None
        sshRh1 = None
        counterPassPhraseCount = None
        counterTimeOut = None
        ticketRecreated = 0

        telnetOption = getGlobal('CONFIG_BMC_LOGIN_TELNET')
        telnetIp = getGlobal('CONFIG_TELNET_IP')
        telnetPort = getGlobal('CONFIG_TELNET_PORT')

        if telnetOption == 1: 
            printDbg("Connecting through telnet: " + str(telnetIp) + ", " + str(telnetPort))

            try:
                tn = telnetlib.Telnet(telnetIp, telnetPort)
            except Exception as msg:
                printErr("Exception during telnet connection. Likely that connection is refused.")
                printErr(str(msg))
                return EXIT_ERR
            return tn            
        elif telnetOption == 0:
            printDbg("Will not use telnet connection")
        elif telnetOption == EXIT_ERR:
            printWarn("Error obtaining telnet configuration value CONFIG_BMC_LOGIN_TELNET from configuration file. Make sure it is defined or configuration file exist.")
            return EXIT_ERR
        else:
            printDbg("Unknown telnet option, must be either 1, 0 or None: " + str(telnetOption))
            return EXIT_ERR
            
        # Based on CONFIG_ENABLE_SWIMS_TICKET interact with bmc differently.
        # With the switch enabled, it uses SWIMS server ticket in order to get 
        # response from CID server.

        configEnableSwimsTicket = getGlobal('CONFIG_ENABLE_SWIMS_TICKET')
    
        if configEnableSwimsTicket:
            tsTargetUser = None
            tsTargetPw = None
            tsCopyTargetPathSuffix=""
        
            # Get password for RH1.
        
            tsTargetPw = getPw("CEC")
            tsTargetUser = getGlobal('CONFIG_RH1_SERVER_UNAME')
            tsTargetPwShow = str(getUnEncPw(tsTargetPw))
        
            if tsTargetUser == None or tsTargetPw == None:
                printErr("user/password retrieve error: /user: " + str(tsTargetUser) )
                return EXIT_ERR
        
            printDbg("Using SWIMS server.")

            # Blade PID is needed for identifying the ticket based on the blade model.

            printDbg("Setting blade.pid")
    
            if self.setPid(pFi.ucsmSsh) == EXIT_ERR:
                printErr("Can not set PID. Can not continue therefore.")
                return EXIT_ERR
        else:
            printDbg("Not using SWIMS server. This is obsolete now. Therefore giving up.")

            return EXIT_ERR
        
            if self.fiHostName == None:
                printErr("FI hostname is not known")
                return EXIT_ERR
    
	    # Login to bmc interactively.

        ucsmSsh4Bmc = sshLoginLinux(ucsmSsh4Bmc, pFi.mgmtIp, pFi.user, pFi.password)

        if ucsmSsh4Bmc == None:
            printErr("unable to connect to new spawn sol FI for BMC")            
            return EXIT_ERR

    	# Start bmc interact loop.

        printDbg("Starting BMC interaction loop", debug)

        bmcCommand = "connect cimc " + self.location
        counter = 0

        while 1:
            if index1 == 5:
                printDbg(str(counter) + ". bmc interact: password: *** ", debug)
            else:
                printDbg(str(counter) + ". bmc interact: command: " + str(bmcCommand), debug)

            if bmcCommand == None or bmcCommand == "":
                printErr("Empty bmc command. Error condition.")
                return EXIT_ERR

            ucsmSsh4Bmc.sendline(bmcCommand)
            time.sleep(2)

            index1 = ucsmSsh4Bmc.expect(\
                [pexpect.TIMEOUT, \
                pexpect.EOF, \
                "\[ help \]#", \
                "No route to host",\
                "login:", \
                "Password", \
                "when ready:", \
                "IBMC-SLOT.*#", \
                "You do not have sufficient privileges.",\
                "Invalid Challenge.",\
                "There are too many bash interactive sessions already open"\
                ], re.DOTALL)
    
            printDbg("Bmc interaction loop index1: " + str(index1), debug)
    
            if debugL2:
                printPexBa(ucsmSsh4Bmc, 1)

            if index1 == 0:
                printErr("UCSM sol connection for BMC debug plug-in Timeout or EOF")
                printPexBa(ucsmSsh4Bmc, 1)
                return EXIT_ERR
            elif index1 == 1:
                printErr("EOF")
                return EXIT_ERR
            elif index1 == 2:
                printDbg("Connection to bmc is successful, continue login wiht sldp...")
                bmcCommand = "sldp"    
            elif index1 == 3:
                printDbg("Connection failed. No route to host")
                return EXIT_ERR
            elif index1 == 4:
                printDbg("Sldp sent and reached login prompt, sending username")
                bmcCommand = "admin"
            elif index1 == 5:
                printDbg("Username sent and reached password prompt, sending pw")
                bmcCommand = "Nbv12345"
            elif index1 == 6:

                # Bmc asking for a challenge response at this point, log on to RH1->CID server to get the challenge 
                # key back.

                printDbg("Bmc asked for challenge. entering RH1 interaction loop within BMC interaction loop", debug)

                ret1 = ucsmSsh4Bmc.before

                if ret1 == None:    
                    printErr("Did not get a challenge prompt, giving up")
                    return EXIT_ERR
                else:
                    printDbg("Challenge string found:", debug)
                    printDbg("ChallengeKey raw: " + ret1, debug)
                    challengeKey = extractChallengeString(ret1)
                    printDbg("Challengekey stripped1: " + str(challengeKey), debug)

                    if challengeKey == None:
                        printErr("ChallengeKey is None.")
                        return EXIT_ERR
                    
                    challengeResponse = self.cidProcessChallengeKey(challengeKey, pRh1TargetPw)

                    if challengeResponse == None:
                        printErr("Challenge Response is None.")
                        return EXIT_ERR
    
                    bmcCommand = challengeResponse
            elif index1 == 7:
                printDbg("BMC interact: Successfully logged onto bcm debug console", debug)
                return ucsmSsh4Bmc
            elif index1 == 8:
                printErr("Logon denied due to insufficient privilege.?!", debug)                
                return EXIT_ERR
            elif index1 == 9:
                printErr("Invalid Challenge string.", debug) 
                return EXIT_ERR
            elif index1 == 10:
                printErr("Too many interactive session open.", debug)
                return EXIT_ERR
            else:
                printErr("Bmc interaction: Unknown index, should not have reached here, index1: " + str(index1))
                return EXIT_ERR

            counter += 1

    # Use this function to send batch of BMC debug console commands to save coding space.
    # It is possible that the connection drops during the execution of any of the command
    # streams, in which case, it will return EXIT_ERR immediately. 
    # req: None
    # input:  
    # - pArrCommands - list of commands to send to BMC.
    # - pBatchRet - if set to 1, then return will contain the list of every command's return value.
    # output: 
    # - output of last command if pBatchRet = 0 (default)
    # - output of every command in list type if pBatchRet = 1.
    # - EXIT_ERR - on any error condition 
    
    def sendBmcBatchCmd(self, pBmcConsole, pArrCommands, pBatchRet = 0):
        debug = 0
        stat = 0
    
        statList = []
    
        # Validate the input arguments.
    
        if pArrCommands == None:
            printErr("no command(s)")
            return EXIT_ERR
    
        # Send commands to ucsm.

        printDbg("pArrCommands: ", debug)

        if debug:
            print pArrCommands

        for i in pArrCommands:
            stat =  self.bmcSendCommand(pBmcConsole, i)
            time.sleep(2)
    
            # if error issuing command, return immediately.        
    
            if stat == EXIT_ERR:
                printErr("returned EXIT_ERR, EOL or some error?")
                return EXIT_ERR
    
            time.sleep(1)
            statList.append(stat)
    
        # Return either output of every command or last command based on pBatchRet.
    
        if pBatchRet == 1:
            return statList    
        elif pBatchRet == 0:
            return stat
        else:
            printErr("pBatchRet contains value other than 1 or 0. This is not recommended.")
            return EXIT_ERR

    # Wrapper function for issuing the bmc command. This function will detect if the pBmcConsole is telnet
    # or otherwise will assume ssh and will send the commands appropriately. For telnet, it uses telnetlib library
    # to send and reply command and its response back from bmc. For ssh connection it uses pexpect to interact.
    # In communicating with bmc back door, it is known that the interaction can be unstable specially if the command 
    # takes a long time to return back to shell. In that case, it is seen the interaction will fail. Therefore it is 
    # highly recommended that the consumer of this wrapper function uses following trick to issue command.
    # option 1:
    # <command> > <filename>.log & (returns to shell immediately. outputs are re-directed to log file.
    # poll using "ps | grep <[c]ommand>" to determine the completion of command.
    # option 2:
    # <command> > <filename>.log & (returns to shell immediately. outputs are re-directed to log file.
    # poll contents of <filename>.log to determine the completion of command, however this can be very command specific.
    #
    # input:
    # - pBmcConsole - bmc console pointer. It it either ssh or telnet connection.
    # - pCommand  - command to set to bmc.
    # return:
    # - return value of the command.
    # - EXIT_ERR if any error condition.

    def bmcSendCommand(self, pBmcConsole, pCommand):
        debug = 0

        if validateFcnInput([pBmcConsole, pCommand]) == EXIT_ERR:
            printErr("Error with inputs.")
            return EXIT_ERR

        if len(pCommand) >= 43:
            printDbg("Command: " + str(pCommand))
            printDbg("Command length is more than 43 char-s, more complicated way of sending commands...")

            # Slice the command into substrings short enough to be send over the ssh and redirect into
            # t.sh file. Before doing that, delete any prior t.sh, after redirect, do a permission and execute 
            # the command.

            splitLen = 15
            fileName = "t.sh"

            ret1 = cli_with_ret(pBmcConsole, "rm -rf " + fileName, "#", "linuxShell", 10)
            time.sleep(2)
            ret1 = cli_with_ret(pBmcConsole, "touch " + fileName, "#", "linuxShell", 10)
            time.sleep(2)

            for i in range(0, len(pCommand), splitLen):
                ret1 = cli_with_ret(pBmcConsole, "echo -n \"" + pCommand[i:i+splitLen] + "\" >> " + fileName, "#", "linuxShell", 10)
                time.sleep(2)

            cli_with_ret(pBmcConsole, "cat " + fileName, "#", "linuxShell", 10)
            time.sleep(2)

            cli_with_ret(pBmcConsole, "chmod 777 " + fileName, "#", "linuxShell", 10)
            time.sleep(2)

            ret1 = cli_with_ret(pBmcConsole, "./" + fileName, "#", "linuxShell", 10)
            time.sleep(2)
            return ret1

        # Handle the case of telnet connection. 

        if re.search("telnetlib", pBmcConsole.__module__):
            printDbg("Telnet:")
            pBmcConsole.write(pCommand + "\n")
            ret1  = pBmcConsole.read_until("#", 10) 
        else:
            printDbg("Not telnet. Assuming pexpect ssh.", debug)
            ret1 = cli_with_ret(pBmcConsole, pCommand, "#", "linuxShell", 10)
                
        if ret1 == None:
            printErr("Error executing the command.")
            return EXIT_ERR
        else:
            return ret1

        # Handle the case of ssh connection.

        return EXIT_ERR

    # Newer version of refreshBlade which uses FI object rather than ucsmSsh. 
    # input:
    # - pFi - FI instance.
    # - pWait - if 1, wait till server becomse either assoc-d or non-assoc when the assoc status is 'removing' or 'associating' with timeout value.
    #         - if 0, if server assoc status is anything other than associated, then set associate status to None and exit.    
    # return:
    # - None if error, 1 if success.

    def refreshBladeNew(self, pFi, pWait=0):
        try:
            stat1 = sendUcsmBatchCmd(pFi, ['top','scope server ' + str(self.location), 'show bios'])        
            self.versionBios = stat1.split(' ')[-2].strip()
            printInfoToFile("BIOS version: " + str(self.versionBios))
        except Exception as msg:
            printWarn("Unable to determine BIOS version and/or error parsing the version string.")
            print msg

        return self.refreshBlade(pFi.ucsmSsh, pWait)
        counter = 0
        debug = 0

    # Use the blade's location and ucsm sol connection to update the class instance's fields to most current information.
    # blade location field (blade.location) must always be set before calling this function.
    # input: 
    # - pUcsmSsh - sol connection to Ucsm.
    # - pWait 
    #   - if 1, wait till server becomse either assoc-d or non-assoc when the assoc status is 'removing' or 'associating' with timeout value.
    #   - if 0, if server assoc status is anything other than associated, then set associate status to None and exit.    
    # return:
    # - None if error, 1 if success.

    def refreshBlade(self, pUcsmSsh, pWait=0):
        debug = 0
        counter = 0

        printDbg("Entered:", debug)

        if self.location == None:
            printErr("blade location is unknown. Can not continue")
            return EXIT_ERR
        if self.fiHostName == None:
            printErr("FI hostname is set to None. Can not continue")
            return EXIT_ERR
        
        cli_with_ret(pUcsmSsh, "top", self.fiHostName)
        time.sleep(1)
        cli_with_ret(pUcsmSsh, "scope server " + self.location, self.fiHostName)
        time.sleep(1)
        ret1 = cli_with_ret(pUcsmSsh, "show assoc | egrep \"Associated|Establishing\"", self.fiHostName)

        # set blade serial number.
        
        stat = cli_with_ret(pUcsmSsh, "show inventory | grep \"Equipped Serial\"", self.fiHostName)
        self.serialNo = stat.split()[-1]

        printDbg("blade serial No. is updated to : " + str(self.serialNo), debug)

        # Association information. 

        printDbg("assoc output: " + str(ret1), debug)

        if ret1 == None:
            printWarn("Unable to find association information.")
            return EXIT_ERR

        if re.search("Associated", ret1) or re.search("Establishing", ret1):
            self.spName = ret1.strip().split()[1].strip()
            printDbg("blade.refresh: sp is set to " + str(self.spName), debug)
        else:
            printWarn("blade service profile is not found")
            return EXIT_ERR

        # set bmc management ip. # it is not reliable as some blade returns empty when issueing command from bmc scope.
        # this happens when blade is removed without decommissioning.

        cli_with_ret(pUcsmSsh, "top", self.fiHostName)
        time.sleep(1)
        cli_with_ret(pUcsmSsh, "scope server " + self.location, self.fiHostName)
        time.sleep(1)
        cli_with_ret(pUcsmSsh, "scope cimc", self.fiHostName)
        time.sleep(1)
        stat = cli_with_ret(pUcsmSsh, "show mgmt-if | grep 255", self.fiHostName)
        time.sleep(1)
        
        printDbg("mgmt ip output: " + str(stat), debug)

        if stat.strip():
            self.mgmtIp = stat.strip().split()[0].strip()
            printDbg("blade.mgmtIp set to: " + str(self.mgmtIp))
            return SUCCESS
        else:
            printErr("Unable to find the management IP from server scope")
            print EXIT_ERR

    # Attempt to decommission the blade.
    # If blade is already decommissioned, nothing will happen.
    # SOL connection to UCSM must be established prior to calling this function.
    # input:
    # - pUcsmSsh - ssh connection handle to UCSM.
    # return:
    # - EXIT_ERR - if some error with decommissioning, 1 if decommission is successful.

    def decommission(self, pUcsmSsh):
        if validateFcnInput([pUcsmSsh]) == EXIT_ERR:
            printErr("invalid function inputs: ")
            return EXIT_ERR

        ret = ""
        debug = 0
        ret = cli_with_ret(pUcsmSsh, "decommission server " + self.location, self.fiHostName)
        time.sleep(1)
        ret = cli_with_ret(pUcsmSsh, "commit",  self.fiHostName)
        time.sleep(2)
        counter = 0
        index1 = None

        while not re.search("Error:", str(ret)):
            time.sleep(10)
            counter += 1
            ret = cli_with_ret(pUcsmSsh, "scope server " +  self.location, self.fiHostName)
    
            printDbg("ret: " + str(ret), debug)
            
            if counter >= 10:
                printErr("Timeout decommissioning server")
                return EXIT_ERR

            '''
            pUcsmSsh.sendline("scope server " + self.location)
            index1 = pUcsmSsh.expect([pexpect.TIMEOUT, pexpect.EOF, "Error:"], timeout=30) 

            if index1 == 0 or index1 == 1:
                counter += 1            
                print "Server is not decommissioning, retry..."
            elif index1 == 2:
                print "Server is decommissioned."       
                return SUCCESS
            else:
                print "Unknown index, should not have come here, logical error. index1: " + index1
            '''

        return SUCCESS

    # Start discovery on a given blade. 
    # input:
    # - pUcsmSsh - pointer to UCSM sol console
    # - pConsole - console pattern to match
    # - pWait - stay in the function until discovery complete if set, if None - issue command and exit immediately.
    # output:
    # - return -  Elapsed time of discovery in seconds, 
    #           EXIT_ERR if timeout, 
    #           SUCCESS if pWait = 0.

    def startDiscovery(self, pUcsmSsh, pConsole, pWait=0):
        debug = 0
        output1 = None
        CONFIG_TIMEOUT_DISCOVERY_WAIT_SEC = 3600
        CONFIG_TIMEOUT_DISCOVERY_INTERVAL_SEC = 10
        elapsedTime = 0

        printDbg(" Entered... location: " + self.location + "...", debug)

        cli_with_ret(pUcsmSsh, "acknowledge slot " + self.location, self.fiHostName)
        time.sleep(1)
        cli_with_ret(pUcsmSsh, "commit", self.fiHostName)
        time.sleep(1)

        if pWait == 0:
            printDbg("blade.startDiscovery: done. Exiting", debug)
            return SUCCESS
        else:
            cli_with_ret(pUcsmSsh, "scope server " + self.location, self.fiHostName)
            time.sleep(1)

            while elapsedTime < CONFIG_TIMEOUT_DISCOVERY_WAIT_SEC:
                output1 = cli_with_ret(pUcsmSsh, "show status detail | grep Discovery:", pConsole)
                printDbg("show server status detail output:\n===================", debug)          

                if debug:
                    print output1

                printDbg("\n====================", debug)

                if re.search("Complete", str(output1)):
                    printDbg("\nDiscovery is successful")
                    return elapsedTime
                else:
                    time.sleep(CONFIG_TIMEOUT_DISCOVERY_INTERVAL_SEC)
                    elapsedTime += CONFIG_TIMEOUT_DISCOVERY_INTERVAL_SEC
            
                    if elapsedTime <= CONFIG_TIMEOUT_DISCOVERY_INTERVAL_SEC:
                        printDbg("blade.startDiscovery: waiting for " + str(elapsedTime) + " seconds.")
                    else:
                        if elapsedTime / CONFIG_TIMEOUT_DISCOVERY_INTERVAL_SEC % 15 == 0: 
                            printDbg("\n")
    
                        printNnl(" " + str(elapsedTime))

        printDbg("\nblade.startDiscovery: Discovery timeout " + str(CONFIG_TIMEOUT_DISCOVERY_WAIT_SEC) + " seconds exceeded", debug)
        return EXIT_ERR

    # This function is an wrapper function to bootEfiShell and should eventually replace any bootEfiShell calls.
    # However it can not replace bootEfiShell function immediately as many modules are dependent
    # and transition should occur smoothly. If called without the pTarget, it functions exactly
    # same as bootEfiShell function. Additional windows and linux boot target can be specified.
    # input:
    # - pUcsmSsh - ucsm console
    # - pBmcSsh - bmc console
    # - pTarget   - if none, (defaults) will boot to efi shell, valid targets are:
    #             - win (boot to windows server, ssh client must be installed.
    #             - lin (firewall may need to be disabled)
    #             - efi (same as bootEfiShell function)
    #             - None (same as bootEfiShell function)
    # return:
    # - ssh handle to host OS if boot is successful, 
    # - EXIT_ERR - if boot is failure for any reason.

    def bootEfiTarget(self, pFi, pTarget=None):
        debug = 0       
        stat = None
        linuxSsh = None
        CONFIG_OS_PING_RETRY_LIMIT = 5
        counter = None
        CONFIG_SLEEP_PROBE_OS_COMPLETE = 300 
    
        if pTarget == "win":
            printWarn("win target is supported but currently not implemented! Do not use this feature for now.")
            return EXIT_ERR

        if pTarget == "win":
            PATH_HOST_OS = str(getGlobal('CONFIG_EFI_WIN_BOOTLOADER_PATH'))
            WIN_USER  = str(getGlobal('CONFIG_EFI_WIN_USER'))
            WIN_PW  = str(getGlobal('CONFIG_EFI_WIN_PW'))
        elif pTarget == "lin":
            PATH_HOST_OS = str(getGlobal('CONFIG_EFI_LIN_BOOTLOADER_PATH'))
            LIN_USER  = str(getGlobal('CONFIG_EFI_LIN_USER'))
            LIN_PW  = str(getGlobal('CONFIG_EFI_LIN_PW'))
        else:
            printErr("(2)Unsupported boot target specified: " + str(pTarget))
            return EXIT_ERR
 
        if pTarget == "win" or pTarget == "lin" or pTarget == None:

            if pFi.mSp.mBlade.wBootEfiShell(pFi, 1, None) == EXIT_ERR:
                printErr("Unable to boot to efishell.")
                return EXIT_ERR
            else:
                printDbg("Booted to efi shell")

                if pTarget == None or pTarget == "efi":
                    return SUCCESS
        else:
            printErr("(1)Unsupported boot target specified: " + str(pTarget))
            return EXIT_ERR

        # booting to shell is complete. reached here because os boot is specified, continue.

        if PATH_HOST_OS == EXIT_ERR:
            printErr("bootloader path is not defined in config file. Can not continue.")
            return EXIT_ERR
        
        # launch the host OS by sending the bootloader path to efi shell prompt.
        # after that, wait for several seconds and start issuing O/S command prompt recognition
        # to see O/S responds. This needs enhanced cli_with_ret to process windows and linux
        # prompt. For windows use Windows 2012 or 2016 prompt for linux RHEL6.x prompt. 
        # we also need to re-connect the bmcSsh because it can be a full of garbage with sendline 
        # call without pexpect.
        
        stat = cli_with_ret(pFi.mSp.bmcSsh, "ls " + (PATH_HOST_OS), "", "efiShell")
    
        if stat == EXIT_ERR or re.search("File Not Found", stat, re.MULTILINE):
            printErr("Bootloader path does not exist." + str(PATH_HOST_OS))
            return EXIT_ERR
        else:
            printDbg("stat after ls-ing the PATH_HOST_OS bootloader path: " + str(stat))

        if stat != EXIT_ERR or re.search("^File Not Found", stat, re.MULTILINE):
            printDbg("stat after ls-ing the PATH_HOST_OS bootloader path: " + str(stat))
        else:
            printErr("Bootloader path does not exist." + str(PATH_HOST_OS))
            return EXIT_ERR

        time.sleep(10) 
        pFi.mSp.bmcSsh.sendline(PATH_HOST_OS)
        pFi.mSp.bmcSsh.sendline('\r')
        time.sleep(5)
        pFi.mSp.bmcSsh.sendline('\r')
        time.sleep(5)
        pFi.mSp.bmcSsh.sendline('\r')
        printDbg("booted O/S by launching " + str(PATH_HOST_OS) + ", sleeping for " + str(CONFIG_SLEEP_PROBE_OS_COMPLETE) + " sec-s.")
        time.sleep(CONFIG_SLEEP_PROBE_OS_COMPLETE)
        
        return SUCCESS
    
        '''
        printDbg("attempting to reconnect")
    
        if pTarget == "lin":
            counter = 0

            while 1:
                printDbg("pexpect wait loop " + str(counter))
        
                response = os.system("ping -c 1 " + IP_HOST_OS)
        
                if response != 0:
                    printDbg("can not ping, waiting more (15 sec-s)...") 
                    counter += 1

                    if counter > CONFIG_OS_PING_RETRY_LIMIT:
                        printDbg("Timeout. Can not ping the OS in reasonable time. Giving up.")
                        return EXIT_ERR

                    time.sleep(15)
                    continue
                else:
                    printDbg("O/S is responding with ping. Continuing with login")
                    break
    
            counter = 0 

            while 1:
                linuxSsh = sshLoginLinux(linuxSsh, IP_HOST_OS, LIN_USER, "nbv12345")

                if linuxSsh:
                    printDbg("Connection success")
                    return linuxSsh
                    printErr("Unable to reconnect to host OS at " + str(IP_HOST_OS) + " retry: " + str(counter))
                else:
                    if counter > 5:
                        printErr("Timeout trying to connect to host OS with 5 retry: " + str(IP_HOST_OS))
                        return EXIT_ERR                            
    
                    time.sleep(20)
                    counter += 1 

        elif pTarget == "win":
            printWarn("win target is supported but not implemented.")
            return EXIT_ERR
        else:
            printErr("(4)Unsupported boot target specified: " + str(pTarget))
            return EXIT_ERR
        '''
    
        '''
        # verify connection is successful by sending sample commands to O/S.
        RHEL 6.7 prompt:
        [root@localhost ~]#
    
        linux command uname -a has following cutout, could use "Linux" search to identify linux.
        [root@localhost build]# uname -a
        Linux localhost.localdomain 2.6.32-573.el6.x86_64 #1 SMP Wed Jul 1 18:23:37 EDT 2015 x86_64 x86_64 x86_64 GNU/Linux
    
        #Windows KT ssh server prompt:
        #C:\Users\Administrator>
    
        # dos command dir output cutout, could se "Directory of" search to identify windows: 
        C:\Users\Administrator>dir
        Volume in drive C has no label.
        Volume Serial Number is CCD5-37BB
        
        Directory of C:\Users\Administrator
        
        03/01/2016  10:29 AM    <DIR>          .
        '''
        '''
        if pTarget == "win":
            stat = cli_with_ret(pFi.mSp.bmcSsh, "dir", "C:\Users\Administrator>", "linuxShell")
        elif pTarget == "lin":
#           stat = cli_with_ret(linuxSsh, "uname -a", "\[.*\]#", "linuxShell")
            stat = cli_with_ret(linuxSsh, "ifconfig | grep " + str(IP_HOST_OS), "\[.*\]#", "linuxShell")
            
            printDbg("ifconfig | grep HOST_OS_IP outp: " + str(stat), debug)    

            if re.search(HOST_OS_IP, stat):
                printDbg("boot to O/S is successful and verified, returning handle")            
                return linuxSsh
            else:
                printErr("Log on to host OS is possible but can not verify.")
                return EXIT_WARN
        else:
            printErr("(1)Unsupported boot target specified: " + str(pTarget))
            return EXIT_ERR
        '''

    # Interrupt POST by either sending F6 or F2 keys, with F2 being default.
    # This is more advanced version of enterBiosSetup. The function enterBiosSetup
    # tries to capture the trigger message from BIOS screen and upon which it will send the
    # appropriate F2 or F6 few times.. Many times, this does not seem work. This function will create separate
    # thread in which it scans for "Aptio Setup Utility" during which main thread starts sending 
    # F2/F6 keys continuously in 2 seconds interval after blade is powered on or power-cycle. 
    # Once separate thread captures the "Aptio
    # Setup Utility" message it will tell the main thread to stop sending F2/F6 by setting
    # textCaptured global variable. Both main thread and separate thread will stop polling 
    # and sending F2 after timeout and server will end in either boot device selection menu
    # BIOS setup depending on the choice.

    # input: 
    # - pUcsmSsh  - UCSM console.
    # - pBmcSsh   - bmc debug console.
    # - pIntKey   - F2 or F6 string.
    # return:    
    # - SUCCESS if blade is in desired state after sending function key.
    # - FAILURE if blade is not in desired state after sending function key. 
    #   desired state: by def. bios setup if F2 is sent or boot device selection    
    #   if F6 is sent.

    def postInterruptAdvanced(self, pUcsmSsh, pBmcSsh, pPostIntKey = "F2"):
        debug = 0
        debugL2 = 1
        pReconn = 1

        global postComplete
        global textCaptured
        printDbg("Setting postComplete flag to 0")

        pBmcSshBak = None
        pBmcSshNew = None

        postComplete = 0

        # Validate inputs.

        if validateFcnInput([pUcsmSsh, pBmcSsh, pPostIntKey]) == EXIT_ERR:
            printErr("Invalid parameters.") 
            return EXIT_ERR

        if pPostIntKey != "F2" and pPostIntKey != "F6":
            printErr("Invalid post-interrupt key.")
            return EXIT_ERR

        fi1 = None
        fi1 = fi(sys.argv[1])
    
        if not fi:
            printErr("Error initializing temporari FI instance.")
    
        # Get RH1 password here early now.
    
        '''
        rh1TargetPw = getPw("CEC")
        rh1TargetUser = getGlobal('CONFIG_RH1_SERVER_UNAME')
        rh1TargetPwShow = str(getUnEncPw(rh1TargetPw))
    
        if rh1TargetUser == None or rh1TargetPw == None:
            printErr("user/password retrieve error: /user: " + str(rh1TargetUser) )
            quit()
    
        # Connect to bmc backdoor.
    
        sshBmcD = self.bmcDbgLogin(fi1, rh1TargetPw)
    
        if sshBmcD:
            printDbg("Successfully logged in to BMC debug console.")
        else:
            printDbg("BMC debug log in attempt failed.")
            return EXIT_ERR
    
        '''

        # Start the threads.

        postCompleteStat = None
        printDbg("Started sending post-interrupt key.", debug)
    
        if pReconn:
            pBmcSshBak = pBmcSsh
            bmcUser = getGlobal('CONFIG_BMC_LOGIN_USER')
            bmcPw = getGlobal('CONFIG_BMC_LOGIN_PW')

            pBmcSsh = sshLogin(pBmcSsh.args[3], bmcUser, bmcPw)
   
            if pBmcSsh == None:
                printWarn("Reconnect to BMC failed, will use original connection handle.")
                pBmcSsh = pBmcSshBak
            else:
                printDbg("Reconnect successful.")
                #pBmcSshNew = pBmcSsh

        # Reset server.

        printDbg("Resetting the system...")
        self.resetBlade(pUcsmSsh)
        printBarSingle()
        time.sleep(10)

        # Start the thread, it will check whether server entered BIOS setup.

        try:
            if thread.start_new_thread( threadHelpCheckMonitor, \
                (self, pBmcSsh, [".*Aptio Setup Utility.*,*.Entering BIOS Setup.*,*.Entering Boot Menu*."]) ) == EXIT_ERR:
                raise Exception('Timeout has reached...')
        except Exception as msg:
            printDbg("Error: Unable to start thread.")
            printDbg("reason: " + str(msg))
            return EXIT_ERR

        printDbg("Reading POST complete wait and interval timing. ", debug)

        CONFIG_POST_COMPLETE_WAIT_INTERVAL = getGlobal('CONFIG_POST_COMPLETE_WAIT_INTERVAL')
        CONFIG_POST_COMPLETE_WAIT_TIMEOUT = getGlobal('CONFIG_POST_COMPLETE_WAIT_TIMEOUT')
    
        if CONFIG_POST_COMPLETE_WAIT_INTERVAL == None or CONFIG_POST_COMPLETE_WAIT_TIMEOUT == None:
            printErr("Unable to fetch CONFIG_POST_COMPLETE_WAIT_INTERVAL/TIMEOUT value(s)")
            return EXIT_ERR

        printDbg("starting a F2/F6 send key loop.", debug)

        # Loop through end send F6 or F2 key at two seconds interval. Each time, check whether global variable
        # textCaptured has been set. In that case, stop F2/F6 keys.

        counter = 0
    
        while 1:
            time.sleep(CONFIG_POST_COMPLETE_WAIT_INTERVAL)
            counter += 2

            if counter > CONFIG_POST_COMPLETE_WAIT_TIMEOUT:
                printErr("Timeout waiting for POST to complete.")
                return EXIT_ERR

            if pPostIntKey == "F6":
                postIntKeySend = "\0336"
            elif pPostIntKey == "H":
                postIntKeySend = "\010"
            elif pPostIntKey == "R":
                postIntKeySend = "\010"
            else:
                postIntKeySend = "\0332"
    
            if pPostIntKey == "R":
                printDbg("sending ctrl+" + str(pPostIntKey), debug)
                pBmcSsh.sendcontrol('r')
            elif pPostIntKey == "H":
                printDbg("sending ctrl+" + str(pPostIntKey), debug)
                pBmcSsh.sendcontrol('h')
            elif pPostIntKey == "F6":
                printDbg("sending " + str(pPostIntKey), debug)
                pBmcSsh.send(postIntKeySend)
            else:
                printDbg("sending F2", debugL2)
                pBmcSsh.send(postIntKeySend)
    
            if textCaptured == 1:
                printDbg("Text is captured. Stopping to send post-interrupt key now.")
                break

            '''
            if counter > CONFIG_POST_COMPLETE_WAIT_INTERVAL:
                printErr("Timeout waiting for text captured. Either failed to capture text or server failed to boot.")
                return EXIT_ERR                                
            '''
            '''
            #if postComplete == 1:
                printDbg("POST complete. Stopping to send post-interrupt key now.")
                break
            '''
        if pReconn:
            printDbg("closing new bmc connection and restoring original")
            pBmcSsh.close()
            pBmcSsh = pBmcSshBak
            
        return SUCCESS

    # Wrapper function for booting efi shell. There are several different methods are supported.
    # OPTION 1: Scan screen for key and send Fx keys and wait for enter setup. Scan setup menu keyword.
    # OPTION 2: Repeatedly press Fx when OPTION 1 does not work.
    # OPTION 3: Set efi-shell to order 1. 
    # None of the above option 3 is fool-proof. If All of the options are exhausted, it will return EXIT_ERR

    # Input:
    # - pFi - fabric interconnect instance.
    # - pForceUefi - if set, set boot-mode to uefi before booting to EFI shell.
    # - pDisableTmpFcn - refer to bootEfiShell()
    # - pOrder - fine grained option for choosing which function to use:
    #   1 - normal order: 1. bootEfiShellThruBp 2. bootEfiShell (default)
    #   2 - bootEfiShellThruBp only
    #   3 - bootEfiShell only.
    #   4 - 1. bootEfiShell 2. bootEfiShellThruBp.
    #   5 - boot efi shell by sending shell command tools\boot.efi.shell.py - warning can not be used from same script! 
    # Output: 
    # - SUCCESS - if boot success.

    def wBootEfiShell(self, pFi, pForceUefi = None, pDisableTmpFcn = None, pOrder = CONFIG_BOOT_EFI_SHELL_BP_F2):
        debug = 1

        bootEfiShellFcnSuccess = getGlobalTmp("boot-efi-shell-success-fcn")

        if bootEfiShellFcnSuccess:
            if re.search("F2", bootEfiShellFcnSuccess):
                printDbg("BootEfiShellNormal is set, changing pOrder to 4. (CONFIG_BOOT_EFI_SHELL_F2_BP)", debug)
                pOrder = CONFIG_BOOT_EFI_SHELL_F2_BP
            elif re.search("BP", bootEfiShellFcnSuccess):
                printDbg("BootEfiShellNormal is set, changing pOrder to 1. (CONFIG_BOOT_EFI_SHELL_BP_F2)", debug)
                pOrder = CONFIG_BOOT_EFI_SHELL_BP_F2
            else:
                printWarn("Unsupported runtime value for bootEfiShellFcnSuccess: " + str(bootEfiShellFcnSuccess))
        else:
            printDbg("bootEfiShellFcnSuccess runtime variable is not set. Leaving pOrder as it is.")

        if debug:
            printDbg("pOrder is set to: " + str(pOrder))

        if pOrder == CONFIG_BOOT_EFI_SHELL_F2_BP or pOrder == CONFIG_BOOT_EFI_SHELL_F2:
            printInfoToFile("Attempting efishell boot through bootEfiShell()...")

            if self.bootEfiShell(pFi.ucsmSsh, pFi.mSp.bmcSsh) == EXIT_ERR:
                printErr("1. Failed to boot efi shell using bootEfiShell()")
            else:
                setGlobalTmp("boot-efi-shell-function", "bootEfiShellNormal")
                printInfoToFile("1a. Booted to efi shell using bootEfiShell")
                printDbg("Updating boot-efi-shell-success-fcn to F2...", debug)
                stat = setGlobalTmp("boot-efi-shell-success-fcn", "F2")
                return SUCCESS

        if  pOrder == CONFIG_BOOT_EFI_SHELL_F2_BP or \
            pOrder == CONFIG_BOOT_EFI_SHELL_BP_F2 or \
            pOrder == CONFIG_BOOT_EFI_SHELL_BP:

            printDbg("Attempting efishell boot through bootEfiShellThruBp()...")

            stat = pFi.mSp.bootEfiShellThruBp(pFi, pForceUefi)

            if stat == EXIT_ERR:
                printErr("Failed to boot efi shell using bootEfiShellThruBp()")
            else:
                printDbg("Booted to efi shell using bootEfiShellThruBp")
                printDbg("Updating boot-efi-shell-success-fcn to BP...", debug)
                setGlobalTmp("boot-efi-shell-success-fcn", "BP")
                return SUCCESS
                #return pFi
    
        if pOrder == 1:
            printInfoToFile("2. Attempting efishell boot through bootEfiShell()...")

            if pFi.mSp.mBlade.bootEfiShell(pFi.ucsmSsh, pFi.mSp.bmcSsh) == EXIT_ERR:
                printErr("Failed to boot efi shell using bootEfiShell()")
            else:
                printInfoToFile("2a. Booted to efi shell using bootEfiShell")
                printDbg("Updating boot-efi-shell-success-fcn to F2...", debug)
                setGlobalTmp("boot-efi-shell-success-fcn", "F2")
                return SUCCESS

        return EXIT_ERR

    # This function will boot the blade into efi shell and will attempt to number of times as the size of
    # BOOT_EFI_SHELL_PATTERN list. The numbers inside the list, dictates how many times the control will send 
    # UP arrow key to zero in onto efi shell. The default sequence is 0,1,2,3,4 therefore will try 5 times.
    # For the blade which has more than 5 boot entry, there is a risk that it might not be able to find EFI shell
    # in this case, list can be increased further. Numbers in the list should not be repeated.
    # In case the first number is slowin the efi shell boot time by not hitting the efi shell entry in boot override
    # the first number in the list can be changed. i.e. for efi shell is 3rd from the bottom:  1,2,3,4,5-> 3,1,2,4,5.

    # input:
    # - pUcsmSsh - ucsm console
    # - pBmcSsh - bmc console
    # return:
    # - SUCCESS if boot is successful, 
    #   EXIT_ERR - if boot is failure. 

    def bootEfiShell(self, pUcsmSsh, pBmcSsh, pDisableTmpFcn = 0):
        debug = 0
        debugL2 = 0
        index1 = None
        stat = None
        configAdvancedEfiShellBoot = 0

        printDbg("Entered", debug)

        if validateFcnInput([pUcsmSsh, pBmcSsh]) == EXIT_ERR:
            printErr("Invalid inputs")
            return EXIT_ERR

        # Read runtime variable fi-mgmt-ip and read efiShellBoConfigFile from config file.

        fiMgmtIp = getGlobalTmp("fi-mgmt-ip")

        efiShellBoConfigFile = getGlobal("CONFIG_EFI_SHELL_BOOT_ORDER")

        if efiShellBoConfigFile:
            efiShellBoConfigFile = PYTHON_ROOT_DIR + efiShellBoConfigFile
        else:
            printErr("unable to obtain the file name for CONFIG_EFI_SHELL_BOOT_ORDER")

        bladeSerialNo = self.serialNo
        spName = self.spName

        # Assume boot efi shell pattern.        

        # BOOT_EFI_SHELL_PATTERN = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
        
        # Get maximum number of efishell boot retry, and try constructing BOO_EFI_SHELL_PATTERN from it.
        # If not successful, will use default one: 0-10.

        configMaxEfiShellBootRetry = getGlobal("CONFIG_EFI_SHELL_BOOT_RETRY")

        try:
            BOOT_EFI_SHELL_PATTERN = range(0, int(configMaxEfiShellBootRetry))
            printDbg("configMaxEfiShellBootRetry: " + str(configMaxEfiShellBootRetry))
        except TypeError:
            printWarn("Error reading configMaxEfiShellBootRetry. Will use default.")
            BOOT_EFI_SHELL_PATTERN = range(0, 10)

        # Let lenBootEfiShellPattern hold initial fixed value of length BootEfiShellPattern. Once BOOT_EFI_SHELL_PATTERN
        # is updated by inserting a optimal boot value (which should only happens once), these two are compared to make 
        # sure it only happens once. 

        lenBootEfiShellPattern = len(BOOT_EFI_SHELL_PATTERN)

        # if self.efiShellBootUpTimesKey empty, which is the case for first time, read it from file. 

        if self.efiShellBootUpTimesKey == None:
            printDbg("Attempting to obtain the efishell BO location from config file.")

            if validateFcnInput([fiMgmtIp, efiShellBoConfigFile, bladeSerialNo, spName]) == EXIT_ERR:
                printErr("Unable to validate the required identification components, can not retrieve the boot order value")
            else:
                printDbg("Reading the config file...")

                # Read the boot up key count from config file.

                stat = getRunTimeVar(efiShellBoConfigFile, \
                    str(fiMgmtIp) + "/" + str(self.serialNo) + "/" + str(self.spName))

                if stat == EXIT_ERR:
                    printErr("Unable to obtain the efishell BO location from config file.")
                else:
                    printDbg("Found the efishell BO location.")
                
                    # Try updating the class member with the file readout value.
    
                    try:
                        self.efiShellBootUpTimesKey = int(stat)
                        printDbg("self.efiShellBootUpTimesKey is updated to " + str(self.efiShellBootUpTimesKey))
                        printDbg("inserting " + str(self.efiShellBootUpTimesKey) + " to BOOT_EFI_SHELL_PATTERN", debug)
                        printVar(self.efiShellBootUpTimesKey)
                        BOOT_EFI_SHELL_PATTERN.insert(0, self.efiShellBootUpTimesKey)

                    except TypeError:
                        printErr("efishell BO location can not be converted to integer")
        else:
            printDbg("self.efiShellBootUpTimesKey is already updated.")
            printDbg("inserting " + str(self.efiShellBootUpTimesKey) + " to BOOT_EFI_SHELL_PATTERN", debug)
            printVar(self.efiShellBootUpTimesKey)
            BOOT_EFI_SHELL_PATTERN.insert(0, self.efiShellBootUpTimesKey)

        print BOOT_EFI_SHELL_PATTERN
        printDbg("p3:", debug)
    
        # Test first to see already in efi shell.
    
        stat = cli_with_ret(pBmcSsh, "ver", "", "efiShell", 1)
    
        if re.search("UEFI Interactive Shell|2.31", str(stat)):
            printDbg("Already in EFI shell, leaving...")
            return SUCCESS
        else:
            printDbg("Not in EFI shell, rebooting..")
            printDbg("stat: \n=====\n" + str(stat) + "\n=====\n", debug)
    
        configAdvancedEfiShellBoot = 0
        configAdvancedEfiShellBoot = getGlobal('CONFIG_ADVANCED_EFI_SHELL_BOOT')

        if configAdvancedEfiShellBoot == EXIT_ERR:
            printWarn("Unable to read global setting CONFIG_ADVANCED_EFI_SHELL_BOOT, will default to 0")
            configAdvancedEfiShellBoot = 0

        for i in range(0, len(BOOT_EFI_SHELL_PATTERN)):
    
            printDbg("LoopNo(attempt)# " + str(i))
    
            # Wait for f2 and send f2 key.
    
            # Advanced boot uses POST complete flag on BMC to check the blade POST completion status in thread.
            # Thread1 will continually send F6 to trigger boot device selection.
            # Thread2 will monitor POST complete flag and if set, will send notification to Thread1
            # to stop sending F6 and kill itself by simply exiting. Once Thread1 sees notification to end simulated F6
            # presses, it will stop doing so and will also kill itself.    
            # From the boot device selection menu, function body will attempt to select efi shell.
            # If not booted to efi shell, each loop will have incrementing number of UP key presses
            # until maximum number or timeout is reached.
        
            if configAdvancedEfiShellBoot:
                printDbg("Continuiing with advanced shell boot mode.")
                if blade.postInterruptAdvanced(self, pUcsmSsh, pBmcSsh, "F2") == EXIT_ERR:
                    printErr("Can not interrupt POST successfully.")         
                    return EXIT_ERR
            else:
                printDbg("Continuiing with normal (non-advanced) shell boot mode.")
                if self.enterBiosSetup(pUcsmSsh, pBmcSsh) == EXIT_ERR:
                    printErr("can not enter BIOS setup, giving up...")      
                    return EXIT_ERR
        
            # Go to boot override menu.
    
            printDbg("Going to boot override menu.", debug)
    
            time.sleep(2)
            pBmcSsh.send('\033[D')
            time.sleep(2)
            pBmcSsh.send('\033[A')
            time.sleep(2)
    
            # FROM HERE ON UP ONCE AND BOOT
            # IF FAIL REBOOT AND UP TWICE AND BOOT
    
            for x in range(0, BOOT_EFI_SHELL_PATTERN[i]):
                printDbg("Sending UP key " + str(BOOT_EFI_SHELL_PATTERN[i]) + " times.")
                time.sleep(2)
                pBmcSsh.send('\033[A')

            if BOOT_EFI_SHELL_PATTERN[i] == 0:
                printDbg("Sending UP key " + str(BOOT_EFI_SHELL_PATTERN[i]) + " times (in another word, not pressing UP key).")
    
            time.sleep(2)
            pBmcSsh.send('\r')
    
            time.sleep(15)
    
            while 1:
                index1 = pBmcSsh.expect([\
                    pexpect.TIMEOUT, \
                    'Shell>', \
                    'Press ESC in.*continue\.',\
                    'Press any key to stop the EFI SCT running',\
                    pexpect.EOF], timeout=60)
   
                printDbg("index: " + str(index1), debug)
    
                if index1 == 0 or index1 == 4:
                    printDbg("Can not detect Shell prompt", debug)
                    break
                elif index1 == 1:
                    printDbg("Booted to efi shell", debug)
                    self.efiShellBootUpTimesKey = BOOT_EFI_SHELL_PATTERN[i]
                    printDbg("setting efiShellBootUpTimesKey to " + str(BOOT_EFI_SHELL_PATTERN[i]), 2)

                    # If BOOT_EFI_SHELL_PATTERN is at its initial value, and self.efiShellBootUpTimesKey is updated
                    # for this runtime instance (most likely this runtime instance has successfully booted to efishell
                    # and updated the self.efiShellBootUpTimesKey), then we can insert this optimal value at the beginning
                    # so that next boot efi shell call will navigate to efi shell entry directly.
                    # The fact we check against initial value is that under the assumption during runtime the boot order will
                    # not change. This could break if any script that changes the boot order or it is changed
                    # spuriously therefore it is untested.

                    # GGGG!! This check might not be necessary: (len(BOOT_EFI_SHELL_PATTERN) == lenBootEfiShellPattern)... test well. 
                    #if self.efiShellBootUpTimesKey != None and (len(BOOT_EFI_SHELL_PATTERN) == lenBootEfiShellPattern):

                    printDbg("lenBootEfiShellPattern:      |init: " + str(lenBootEfiShellPattern), debug)
                    printDbg("(len(BOOT_EFI_SHELL_PATTERN):|curr: " + str(len(BOOT_EFI_SHELL_PATTERN)), debug)

                    if self.efiShellBootUpTimesKey != None:
                        printDbg("Updating to efishell BO location config file.")
                
                        # Write to file to make it permanent.
                
                        stat = setRunTimeVar(efiShellBoConfigFile, \
                            str(fiMgmtIp) + "/" + str(self.serialNo) + "/" + str(self.spName), \
                            str(self.efiShellBootUpTimesKey))
                
                        if stat == SUCCESS or stat == EXIT_WARN:
                            printDbg("efishell BO location is updated successfully.")
                        else:
                            printDbg("efishell BO location updated has failed.")
                    else:
                        printDbg("Not updating the efiShellBootUpTimesKey in runtime file: \
                            \nself.efiShellBootUpTimesKey: " + str(self.efiShellBootUpTimesKey) + \
                            "\nlen(BOOT_EFI_SHELL_PATTERN): " + str(len(BOOT_EFI_SHELL_PATTERN)) + \
                            "\nlenBootEfiShellPattern: " + str(lenBootEfiShellPattern), debug)
            
                    return SUCCESS
                elif index1 == 2 or index1 == 3:
                    printDbg("Skipping any startup commands or programs", debug)
                    pBmcSsh.sendline('\r')
                else:
                    printErr("Unknown index, should not have reached here.", debug)
                    return EXIT_ERR

        printErr("after " + str(len(BOOT_EFI_SHELL_PATTERN)) + " failed attempt, unable to boot to efi shell. giving up...")
        return EXIT_ERR    

    # This function resets the blade.
    # pUcsmSsh  - serial connection ot ucsm console
    # return    - SUCCESS if reset succeeded.
    #           - FAILURE if reset failed for any reason.

    def resetBlade(self, pUcsmSsh):

        if self.location == None or self.fiHostName == None:
            printErr("None: self.location " + str(self.location) + " self.fiHostName " + str(self.fiHostName))
            return EXIT_ERR

        cli_with_ret(pUcsmSsh, 'scope server ' + self.location, self.fiHostName)
        time.sleep(2)
        cli_with_ret(pUcsmSsh, 'reset hard-reset-immediate', self.fiHostName)
        time.sleep(2)
        cli_with_ret(pUcsmSsh, 'commit', self.fiHostName)
        time.sleep(20)
        return SUCCESS

    # This function will reset the blade and will attempt to enter BIOS setup/F6 boot menu/LSi RAID utility during next POST.
    # pUcsmSsh  - SOL connection to UCSM console
    # pBmcSsh   - SOL connection to BMC console of blade
    # pPostIntKey  - BIOS POST interrupt key (optional) could be F6, ctrl+h (not working), ctrl+r(not working)
    # pDisableTmpFcn - disable temporary function if set. 
    # return    - SUCCESS if enter bios is successful.
    #           - EXIT_ERR if any error is encountered.

    def enterBiosSetup(self, pUcsmSsh, pBmcSsh, pPostIntKey = None, pReconn = 0, pDisableTmpFcn = 1):
        debug = 1
        counter_enter_setup_attempts = 0
        counter_boot_efi_shell_attempts = 0
        boot_efi_shell_ok = 0
        index1 = 0
        lBmcSsh = 0
        stat = None

        if validateFcnInput([pUcsmSsh, pBmcSsh]) == EXIT_ERR:
            printErr("Invalid inputs")
            return EXIT_ERR

        printVars([pPostIntKey, pReconn, pDisableTmpFcn])

        pBmcSshBak = None
        pBmcSshNew = None

        if pUcsmSsh == None:
            printErr("pUcsmSsh is None")
            return EXIT_ERR

        # if pReconn is set, then pBmcSsh is set to new value by reconnecting.
        # Note that python is a pass-by-value, therefore old parameter passed as 
        # pBmcSsh is lost in this function specifc but still available.
        # since pBmcSsh takes on new value it should be closed prior to exiting this 
        # function.

        if pReconn:
            pBmcSshBak = pBmcSsh
            bmcUser = getGlobal('CONFIG_BMC_LOGIN_USER')
            bmcPw = getGlobal('CONFIG_BMC_LOGIN_PW')

        printDbg("Entered... pPostIntKey: " + str(pPostIntKey), debug)

        if pPostIntKey == "R":
            keywords = ['MegaRAID Configuration Utility', 'LSI', 'MegaRAID', 'Virtual Drive', 'JBOD']
        elif pPostIntKey == "H":
            keywords = ['LSI', 'LSI', 'MegaRAID', 'Virtual Drive', 'JBOD']
        else:
            keywords = ['Press', 'Press', 'platform', 'hardware', 'Bios']
        
        if pPostIntKey == "F6":
            postIntKeySend = "\0336"
        elif pPostIntKey == "H":
#           postIntKeySend = char(int("8"))
            postIntKeySend = "\010"
        elif pPostIntKey == "R":
#           postIntKeySend = chr(int("18"))
            postIntKeySend = "\010"
        else:
            postIntKeySend = "\0332"

        if pPostIntKey == "H" or pPostIntKey == "R":
            f2Interval = [0, 0, 0, 1, 0, 0, 1, 0, 0, 1, 0, 0, 1, 0, 0, 2, 2, 3]
        else:
            f2Interval = [1, 1, 2, 2, 5, 10, 10, 10, 10, 10, 10]

        TIMEOUT_HOTKEY_SEND_TRIGGER_KEYWORD = getGlobal('CONFIG_TIMEOUT_HOTKEY_SEND_TRIGGER_KEYWORD')

        if TIMEOUT_HOTKEY_SEND_TRIGGER_KEYWORD == EXIT_ERR:
            TIMEOUT_HOTKEY_SEND_TRIGGER_KEYWORD = 120

        printDbg("TIMEOUT_HOTKEY_SEND_TRIGGER_KEYWORD is set to : " + str(TIMEOUT_HOTKEY_SEND_TRIGGER_KEYWORD))
    
        TIMEOUT_TRIGGER_KEYWORD_SCAN = getGlobal('CONFIG_TIMEOUT_TRIGGER_KEYWORD_SCAN')

        if TIMEOUT_TRIGGER_KEYWORD_SCAN == EXIT_ERR:
            TIMEOUT_TRIGGER_KEYWORD_SCAN = 120
        LIMIT_ENTER_BIOS_SETUP_ATTEMPT = len(keywords)
            
        printDbg("TIMEOUT_TRIGGER_KEYWORD_SCAN is set to : " + str(TIMEOUT_TRIGGER_KEYWORD_SCAN))
        printDbg("Starting auto-(re)boot to BIOS setup/F6 menu/LSI Raid Utility, it will attempt several times by scanning following words from BIOS screen", debug)

        if debug:
            printSeq(keywords)
        
        counter = 1

        # loop to attempt several times to enter bios setup.       
        
        for i in range (0, LIMIT_ENTER_BIOS_SETUP_ATTEMPT):
            if pReconn:
                pBmcSsh = sshLogin(pBmcSsh.args[3], bmcUser, bmcPw)
   
                if pBmcSsh == None:
                    printWarn("reconnect to bmc failed, will use original connection handle.")
                    pBmcSsh = pBmcSshBak
                else:
                    pBmcSshNew = pBmcSsh
    
                # reset the blade
        
            printDbg("resetting the system...")

            if self.resetBlade(pUcsmSsh) == EXIT_ERR:
                printErr("Can not resett the blade.")
                return EXIT_ERR

            printDbg("Scanning for keyword '" + keywords[i] + "' from BIOS screen for up to " + str(TIMEOUT_HOTKEY_SEND_TRIGGER_KEYWORD) + " seconds")
            printVar(postIntKeySend)
            
            index1 = pBmcSsh.expect([pexpect.TIMEOUT, pexpect.EOF, ".*" + keywords[i] + ".*"], timeout=TIMEOUT_HOTKEY_SEND_TRIGGER_KEYWORD)
        
            if index1 == 0:
                printWarn("Reached timeout, was not able to intercept trigger word")
                counter += 1
                continue
            elif index1 == 1:
                printWarn("Reached EOF, was not able to intercept trigger word")
                counter += 1
                continue
            else:
                printDbg("captured one of the keyword, now sending hot key several times in succession: hotkey for " + str(pPostIntKey), debug)

                for i in range(0,2):
                
                    if pPostIntKey == "R":
                        printDbg("sending ctrl+" + str(pPostIntKey), debug)
                        pBmcSsh.sendcontrol('r')
                    elif pPostIntKey == "H":
                        printDbg("sending ctrl+" + str(pPostIntKey), debug)
                        pBmcSsh.sendcontrol('h')
                    elif pPostIntKey == "F6":
                        printDbg("sending " + str(pPostIntKey), debug)
                        pBmcSsh.send(postIntKeySend)
                    else:        
                        printDbg("sending F2", debug)
                        pBmcSsh.send(postIntKeySend)

                for sleepTime in f2Interval:
                    index1 = pBmcSsh.expect([pexpect.TIMEOUT, \
                        ".*Entering Setup.*", \
                        ".*Entering boot selection.*", \
                        ".*Initializing.*", \
                        ".*will be executed.*", \
                        ".*Please select.*"\
                        ".*Unable to match boot policy.*"\
                        ], timeout=sleepTime)

                    if index1 == 0:
                        time.sleep(sleepTime)

                        if pPostIntKey == "R" or pPostIntKey == "H":
                            printDbg("sending ctrl+" + str(pPostIntKey), debug)
                            pBmcSsh.send(postIntKeySend)
                        else:        
                            pBmcSsh.send(postIntKeySend)
        
                    elif index1 == 1:
                        printDbg("captured 'Entering setup' word.", debug)
                        break
                    elif index1 == 6:
                        printWarn("captured 'Unable to match boot policy error", debug)
                        break
                    elif index1 == 2 or index1 == 5:
                        printDbg("captured 'Entering boot selection menu' word.", debug)
                        break
                    elif index1 == 3 or index1 == 4:
                        printDbg("captured LSI Raid word", debug)
                        break
                    else:
                        printDbg("Unknown index: " + str(index1), debug)
                        break
            
            printDbg("Waiting BIOS to enter setup for up to " + str(TIMEOUT_TRIGGER_KEYWORD_SCAN/60) + " minutes...", debug)

            if pPostIntKey == "F6":
                printDbg("scanning for F6 boot message menu...", debug)
            elif pPostIntKey == "H":
                printDbg("scanning for H-pressed raid utility menu...", debug)
            elif pPostIntKey == "R":
                printDbg("scanning for LSI Raid utility menu...", debug)
            else:
                printDbg("scanning for 'Aptio' from BIOS screen...", debug)

            index1 =  pBmcSsh.expect([pexpect.TIMEOUT, pexpect.EOF, '.*Aptio Setup.*', 'UEFI:', 'boot device', 'VD Mgmt', 'PD Mgmt', 'Unable to match boot policy'], timeout=TIMEOUT_TRIGGER_KEYWORD_SCAN)
        
            printDbg("index1: " + str(index1), debug)

            if index1 == 0 or index1 == 7:
                if index1 == 7:
                    printErr("WARNING!!! KEYWORD CAPTURE SCAN FAILURE IS DUE TO BOOT ORDER ERROR. SCRIPT WILL ATTEMPT BUT THIS MEANS IT WILL IGNORE THIS ERROR/BUG!!!!")
                    printErr("ATTEMPTING WORKAROUND BY SETTING BACK TO LEGACY AND THEN UEFI. NOT GUARANTEED TO FIX.")

                    # if this flag is set, will try toggline between legacy and uefi one more time
                    # to re-send the token. this function assumes blade is in UEFI mode!
                    # if the test was running in legacy mode, this will leave the system in 
                    # uefi mode!

                    if pDisableTmpFcn:
                        pSp = None
                        stat = None
    
                        pSp = self.getSpInfo(pUcsmSsh)
    
                        if pSp:
                            stat = tmpReConfigBootPol(pSp, pUcsmSsh)
            
                            if stat == EXIT_ERR:
                                printErr("can not re-config the blade")
                        else:
                            printErr("Unable to create sp object on-the-fly. Giving up")                    

                if counter < LIMIT_ENTER_BIOS_SETUP_ATTEMPT:
                    printBarSingle()
                    printWarn("attempt #" + str(counter) + ":")
                    printDbg("did not capture the keyword. Not sure if sent F2 successfully, will reboot again in 30 sec-s.")
                    printDbg("Visually inspect the blade to see if it entered setup if so, press Ctrl+C to break this script.", debug)
                    printDbg("Otherwise, it will attempt again " + str(LIMIT_ENTER_BIOS_SETUP_ATTEMPT-counter-1) + "times.", debug)
                    time.sleep(30)

                    if pReconn: 
                        printDbg("closing new bmc connection")
                        pBmcSshNew.close()

                    counter += 1
                else:
                    printErr("did not capture the keyword. Not sure if sent F2 successfully, therefore not guaranteed to enter setup", debug)

                    if pReconn:
                        printDbg("closing new bmc connection")
                        pBmcSshNew.close()
    
                    printDbg("retry exhausted", debug)
                    return EXIT_ERR
            elif index1 == 1:
                    printDbg("EOF. Giving up.")

                    if pReconn:
                        printDbg("closing new bmc connection")
                        pBmcSshNew.close()
    
                    return EXIT_ERR
            else:
                printDbg("captured the keyword from BIOS screen. Entered the BIOS setup, done")

                if pReconn:
                    printDbg("closing new bmc connection")
                    pBmcSshNew.close()
                    
                return SUCCESS
                         
    # Check if there is a blade in the slot. 
    # Will return SUCCESS if blade is in the slot discovered or being discovered
    # Will return EXIT_ERR if no blade is in the slot or decommissioned
    # (unimplemented).

    def checkSlotOccupancy():
        return EXIT_ERR

    # Sets the blade location.
    # input:
    # - pLocatoin - location in x/y format.
    # return:
    # - SUCCESS if location is set.
    # - EXIT_ERR if location is not set.

    def setLocation(self, pLocation):
        if pLocation:
            try:
                self.chassisNo = pLocation.split('/')[0]
                self.slotNo = pLocation.split('/')[1]
                self.location = pLocation
            except Exception as msg:
                printErr("Exception occurred when determining blade location: " + str(pLocation))
                print msg
                return EXIT_ERR
        else:
            printErr("pLocation is None. can not setup blade location")
            return EXIT_ERR

    # Given blade position, set service-profile name (this is not associate, it simply sets the class variable: self.spName
    # input:
    # - pUcsmSsh - ssh handle to ucsm
    # - pHostName - hostname of ucsm
    # return:
    # - EXIT_ERR if failure to sets the service-profile name
    # - SUCCESS if sets the SP correctly.

    def setSp(self, pUcsmSsh, pHostName):
        counter = 0
        output1 = None
        debug = 0

        if pUcsmSsh == None:
            printErr("UCSM ssh handle is not initialized")
            return EXIT_ERR

        expectTermination= ".*#.*"

        output1 = cli_with_ret(pUcsmSsh, "scope server " + self.location, pHostName)
        time.sleep(2)

        if re.search("Error:", output1):
            printErr("Error. Blade can not be scoped to. (decommissioned?)")   
            return EXIT_ERR

        time.sleep(1)
        output1 = cli_with_ret(pUcsmSsh, "show assoc | grep Associated", pHostName)

        if re.search("Associated", output1):
            output1 = output1.strip()
            self.spName = output1.split()[1]
            printDbg("obtained service-profile: " + self.spName, debug)
            return SUCCESS
        else:
            printDbg("Error. Blade service-profile can not be obtained. (Disassociated?)")
            return EXIT_ERR

    # Create service-profile and associates it to slot.
    # This function is best used for setting up the blade newly with no service-profile associated.
    # If the blade in the slot is associated already, it will simply assigned to slot therefore will start
    # associating whenever the blade becomes disassociate.
    # input:    
    # - pSsh - ssh handle to ucsm
    # - pSpName - service-profile name
    # - pVnicName - name of vnic if created. Set to None if not vnic is to be created.
    # returns:  
    # - SUCCESS - if service-profile created successfully.
    # - EXIT_ERR - if any failure.
    
    def createSp(self, pSsh, pSpName, pVnicName="eth0"):
        debug = 0

        if self.location == None:
            printDbg("createSp: error: blade location is not set.")
            return EXIT_ERR

        printDbg("creating sp: " + str(pSpName))

        cli_with_ret(pSsh, 'scope org', self.fiHostName)
        time.sleep(1)
        stat = cli_with_ret(pSsh, 'create service-profile ' + pSpName, self.fiHostName)
        
        if re.search("Error: Managed object already exists", stat):
            cli_with_ret(pSsh, 'scope org', self.fiHostName)
            time.sleep(1)
            cli_with_ret(pSsh, 'scope service-profile ' + pSpName, self.fiHostName)
            time.sleep(1)
            cli_with_ret(pSsh, 'associate server ' + self.location, self.fiHostName)
            time.sleep(1)
            cli_with_ret(pSsh, 'commit', self.fiHostName)
            time.sleep(1)
            return EXIT_NO_ERR

        if pVnicName:
            time.sleep(1)
            cli_with_ret(pSsh, 'create vnic ' + str(pVnicName), self.fiHostName)
            time.sleep(1)
            cli_with_ret(pSsh, 'set identity mac-pool default', self.fiHostName)
            time.sleep(1)
            cli_with_ret(pSsh, 'create eth-if default', self.fiHostName)
            time.sleep(1)
            cli_with_ret(pSsh, 'set default-net yes', self.fiHostName)
            time.sleep(1)
            cli_with_ret(pSsh, 'commit', self.fiHostName)
            time.sleep(1)
        cli_with_ret(pSsh, 'scope org', self.fiHostName)
        time.sleep(1)
        cli_with_ret(pSsh, 'scope service-profile ' + pSpName, self.fiHostName)
        time.sleep(1)
        cli_with_ret(pSsh, 'associate server ' + self.location, self.fiHostName)
        time.sleep(1)
        cli_with_ret(pSsh, 'commit', self.fiHostName)
        time.sleep(1)
        self.spName = pSpName
        return SUCCESS

#   UCS blade service-policy class implementation.
#   All aspects blade service-profile properties and methods should be implemented in this class.
    
class sp:
    classString = "sp class instance info:"
    debug = 0
    bmcIp = None
    mgmtIp = None
    bladeLoc = None
    bladePid = None

    mgmtUsername = 'admin'
    mgmtPassword = 'Nbv12345'

    hostLinuxIp = None
    hostLinuxUserName = 'root'
    hostLinuxPassword = 'nbv12345'

    spName = None
    fiHostName = None

    bootPolicyName = None
    solPolicyName = None 
    ipmiPolicyName = None 
    biosPolicyName = None
    ipmiProfileName = None
    hostFwPolicyName = None
    localDiskConfigPolName = None
    bmcSsh = None

    ucsmIp = None

    mBp = None
    blade = None
    
    def __init__(self, pLocation = None, pSpName = None):        
        debug = 0
        printDbg("Creating blade instance.")

        printDbg("sp:__init__ param-s: (pLocation, pSpName)", debug)
        print pLocation, pSpName

        if pLocation:
            self.mBlade = blade(pLocation, pSpName)
            self.bladeLoc = pLocation
        else:
            printWarn("blade location, pLocation is None! May not create blade instance.")

        if pSpName:
            printDbg("spName is deliberately given. Setting now to " + str(pSpName))
            self.spName = pSpName
            self.mBp = bp(pSpName)
        else:
            printDbg("pSpName: is None.")
            self.mBp = bp()

    # Power off and on the blade from service-profile.
    # input:
    # - pFi - FI instant.
    # - pPowerState - power state request, 1 is for on, 0 is for off state, any other values passed will result in a error condition.
    # - pVerify - once power state is sent to blade, verify the state after set time. Default is not verify = None.
    # return:
    # - SUCCESS for successful power state transition, EXIT_ERR for any failure. 

    def spPower(self, pFi, pPowerState, pVerify = None):
        debug = 1
        lPowerState = {1: "up", 0: "down"}
        lPowerStatus = {1: "On", 0: "Off"}

        CONFIG_POWER_STATE_TRANSITION_WAIT_LIMIT = getGlobal('CONFIG_POWER_STATE_TRANSITION_WAIT_LIMIT')
        CONFIG_POWER_STATE_TRANSITION_WAIT_INTERVAL = getGlobal('CONFIG_POWER_STATE_TRANSITION_WAIT_INTERVAL')

        if not CONFIG_POWER_STATE_TRANSITION_WAIT_LIMIT:
            printDbg("Unable to get CONFIG_POWER_STATE_TRANSITION_WAIT_LIMIT from configuration file. Default to 60 seconds.")
            CONFIG_POWER_STATE_TRANSITION_WAIT_LIMIT = 60

        if not CONFIG_POWER_STATE_TRANSITION_WAIT_INTERVAL:
            printDbg("Unable to get CONFIG_POWER_STATE_TRANSITION_WAIT_INTERVAL from configuration file. Default to 10 seconds.")
            CONFIG_POWER_STATE_TRANSITION_WAIT_INTERVAL = 10 

        if validateFcnInput([pFi, pPowerState]) == EXIT_ERR:
            printErr("Error with input.")
            return EXIT_ERR

        try:     
            printDbg("Setting power state...", debug)   

            if sendUcsmBatchCmd(pFi, ['top', 'scope org', 'scope service-profile ' + self.spName,\
                'power ' + lPowerState[pPowerState], 'commit'\
                ]) == EXIT_ERR:
                printErr("(1)Faiure to send power state command.")
                return EXIT_ERR
        except Exception as msg:
            printErr("(2)Failure to send power state command.")
            return EXIT_ERR

        printDbg("Wait for 5 sec-s...", debug)   
        time.sleep(5)

        elapsedTime = 0

        if pVerify:
            time.sleep(CONFIG_POWER_STATE_TRANSITION_WAIT_INTERVAL)
            elapsedTime += CONFIG_POWER_STATE_TRANSITION_WAIT_INTERVAL
          
            printDbg("Checking back the power state.", debug)   
            stat = sendUcsmBatchCmd(pFi, ['top', 'scope org', 'scope service-profile ' + self.spName,\
                'show status'\
                ])
                
            if not re.search(lPowerStatus[pPowerState], stat):
                printWarn("Power state request: " + str(lPowerState[pPowerState]) + ", current state: " + str(stat) + " for " + str(elapsedTime) + " seconds...")

                if elapsedTime > CONFIG_POWER_STATE_TRANSITION_WAIT_LIMIT:
                    printErr("Power state request: " + str(lPowerState[pPowerState]) + ", current state: " + str(stat) + " for " + str(elapsedTime) + " seconds (timeout).")
                    return EXIT_ERR

            printDbg("Power state is OK.")
            return SUCCESS
        else:
            printDbg("pVerify = 0, power state will not be verified.")
            return SUCCESS

    # Get device type for specific boot order in the boot policy.
    # input:
    # - pFi - instance of fabric interconnect.
    # - pBootOrder - boot order in the boot-policy to which the device is set to.
    # return:
    # - string type of device if its boot order is found, EXIT_ERR - if boot is failure. 

    def getDeviceBo(self, pFi, pBootOrder):
        debug = 0
        bootDevicesSupported = ['boot-security' ,'efi-shell' ,'iscsi', 'lan', 'san', 'storage', 'virtual-media read-only']

        grepPattern = "Order: " + str(pBootOrder)

        for i in bootDevicesSupported:
            printDbg("checking " + str(i), debug)

            stat = sendUcsmBatchCmd(pFi, ['top', 'scope org', 'scope boot-policy ' + self.spName,\
                'scope ' + i, 'show | grep \"Order: '  + str(pBootOrder) + '\"'\
                ])

            if not re.search(str(pBootOrder), stat):
                continue

            try:
                stat = int(stat.strip().split(":")[-1])
                pBootOrder = int(pBootOrder)
            except Exception as msg:
                printErr("Unable to convert to stat to integer: " + str(stat))
                print msg
                return EXIT_ERR

            printDbg("stat: " + str(stat), debug)

            if stat == pBootOrder:
                printDbg("Found the device type for boot order: " + str(i) + ", " + str(pBootOrder))
                return str(i)

        printWarn("Unable to find device type for boot order " + str(pBootOrder))   
        return EXIT_ERR
    
    # Boots to efi-shell through boot policy. Adds efi shell boot entry to boot option as first bootable device
    # and reset the blade.

    # input:
    # - pFi - FI instant.
    # - pForceUefi - the efi shell is not added if boot-policy is in legacy mode (bug or behavior?) 
    # this switch will force to uefi mode if desired. By default, it must be turned off (so to not change
    # to prevent undesired behavior.
    # return 
    # - SUCCESS if boot is successful, EXIT_ERR - if boot is failure. 
    # return: 

    def bootEfiShellThruBp(self, pFi, pForceUefi = 0):
        debug = 0
        debugL2 = 0
        index1 = None
        stat = None
        stat1 = None
        configAdvancedEfiShellBoot = 0
        counter = None
        CONFIG_BOOT_EFI_SHELL_RETRY = 3

        printDbg("Entered", debug)

        fiMgmtIp = getGlobalTmp("fi-mgmt-ip")

        if validateFcnInput([pFi.mSp.bmcSsh]) == EXIT_ERR:
            printErr("Error with input.")
            return EXIT_ERR

        stat = cli_with_ret(pFi.mSp.bmcSsh, "ver", "", "efiShell", 1)
    
        if re.search("UEFI Interactive Shell|2.31", str(stat)):
            printDbg("Already in EFI shell, leaving...")
            return SUCCESS
            #return pFi
        else:
            printDbg("Not in EFI shell, rebooting...", debug)
            printDbg("stat: \n=====\n" + str(stat) + "\n=====\n", debug)

            # Process boot-mode behavior.
    
            # Check boot mode. If it is in uefi mode, do nothing.
            # If it is in legacy mode
            #   if pForceUefi is set, then set bp to uefi mode.
            #   Otherwise exit with error saying it is not supported. (further enhancement can include
            #   to use other boot method to efi shell.
    
            printDbg("Checking boot mode.", debug)
            bootMode = pFi.mSp.mBp.getBootMode(pFi)
            
            if bootMode == "Uefi":
                printDbg("Already in uefi mode, will continue normally.", debug)
            elif bootMode == "Legacy":
                printDbg("Boot-mode is in legacy mode.", debug)

                if pForceUefi == 1:
                    if pFi.mSp.mBp.setBootMode(pFi, pFi.mSp, pFi.mSp.mBlade, "Uefi") == EXIT_ERR:            
                        printErr("Unable to set boot mode.")
                    else:
                        printDbg("Successfully set the boot mode to UEFI", debug)
                else:
                    printWarn("Warning: pForceUefi = 0 and boot mode is in legacy. Will try other method...")

                    if  pFi.mSp.mBlade.bootEfiShell(pFi.ucsmSsh, pFi.mSp.bmcSsh, 1) == EXIT_ERR:
                        printErr("Failed to boot to efi shell")
                        return EXIT_ERR
            else:
                printErr("Unsupported boot-mode is returned by getBooMode() function: " + str(bootMode))
                return EXIT_ERR

            # Attempt to boot to efi shell now, will try 3 times. 

            # Get device in boot order 1.
            # If exists, move to highest. (at this point no device exist at boot order 1.
            # Add efi shell with explicitly specifying boot order 1
            # commit.

            # If no device is set to boot order 1, set efi-shell to boot order 1.

            deviceOrders = pFi.mSp.mBp.getBootOrderNumbers(pFi)
        
            if deviceOrders == EXIT_ERR:
                printErr("Unable to determine device boot orders.")
                return EXIT_ERR

            highestOrder = str(max(deviceOrders) + 1)

            printDbg("Next available empty slot: " + str(highestOrder), debug)

            stat = pFi.mSp.getDeviceBo(pFi, 1)

            if stat:
                stat1 = sendUcsmBatchCmd(pFi, ['top', 'scope org', 'scope boot-policy ' + self.spName,\
                'scope ' + str(stat), 'set order ' + str(highestOrder), 'commit'\
                ])

                if re.search("Error:", stat1):
                    printErr("Error moving " + str(stat) + " from boot order 1")
                    return EXIT_ERR
    
            printDbg("No device is set to boot order 1 now, setting efi-shell to boot order 1.", debug)

            stat1 = sendUcsmBatchCmd(pFi, ['top', 'scope org', 'scope boot-policy ' + self.spName,\
                'create efi-shell', 'commit'\
                ])

            stat1 = sendUcsmBatchCmd(pFi, ['top', 'scope org', 'scope boot-policy ' + self.spName,\
                'scope efi-shell', 'set order 1','commit'\
                ])

            printDbg("Success setting efi-shell to boot order 1. Waiting to boot order, sending ver periodically.", debug)
        
            CONFIG_POST_COMPLETE_WAIT_INTERVAL = getGlobal('CONFIG_POST_COMPLETE_WAIT_INTERVAL')
            CONFIG_POST_COMPLETE_WAIT_TIMEOUT = getGlobal('CONFIG_POST_COMPLETE_WAIT_TIMEOUT')
        
            for i in range(0, CONFIG_BOOT_EFI_SHELL_RETRY): 
                printDbg("Resetting the system, " + str(i) + " out of " + str(CONFIG_BOOT_EFI_SHELL_RETRY) + " retries.")
                self.mBlade.resetBlade(pFi.ucsmSsh)
    
                if CONFIG_POST_COMPLETE_WAIT_INTERVAL == None or CONFIG_POST_COMPLETE_WAIT_TIMEOUT == None:
                    printErr("Unable to fetch CONFIG_POST_COMPLETE_WAIT_INTERVAL/TIMEOUT value(s).")
                    printErr("Setting to default: INTERVAL/TIMEOUT: 20/400")
                    CONFIG_POST_COMPLETE_WAIT_INTERVAL = 15
                    CONFIG_POST_COMPLETE_WAIT_TIMEOUT = 500
                else:
                    printDbg("CONFIG_POST_COMPLETE_WAIT_INTERVAL/TIMEOUT are set to: " + str(CONFIG_POST_COMPLETE_WAIT_INTERVAL) + ", " + str(CONFIG_POST_COMPLETE_WAIT_TIMEOUT))
            
                counter = 0

                if i > 0:
                    printDbg("3. Reconnecting to bmc...")
            
                    pFi.mSp.bmcSsh.close()
                    pFi.mSp.bmcSsh = sshLoginLinux(pFi.mSp.bmcSsh, pFi.mSp.mgmtIp, pFi.mSp.mgmtUsername, pFi.mSp.mgmtPassword)
            
                    if not pFi.mSp.bmcSsh:
                        printErr("Can not login to bmc.")
                        return EXIT_ERR
                    else:
                        printDbg("Login to bmc ssh is OK.")
    
                start = time.time()

                while 1:
                    time.sleep(CONFIG_POST_COMPLETE_WAIT_INTERVAL)
                    counter = time.time() - start
        
                    if counter > CONFIG_POST_COMPLETE_WAIT_TIMEOUT:
                        printErr("Timeout waiting for POST to complete. Unable to boot to efi shell. Elapsed time " +str(counter) + " of " + str(CONFIG_POST_COMPLETE_WAIT_TIMEOUT) + " seconds.")
                        break
        
                    stat = cli_with_ret(pFi.mSp.bmcSsh, "ver", "", "efiShell", 1)
                
                    if re.search("UEFI Interactive Shell|2.31", str(stat)):
                        printDbg("Already in or booted to EFI shell, leaving after idling for few seconds...")
                        time.sleep(15)
                        return SUCCESS
                    else:
                        if counter % 60 == 0:
                            printDbg("Not in EFI shell yet...Time elapsed: " + str(counter))

            printErr("Unable to boot to efi shell for " + str(CONFIG_BOOT_EFI_SHELL_RETRY) + " retries.")
            return EXIT_ERR
            
    # Create vnic for given service-profile.
    # req:      None.
    # input:    
    # - pFi - fabric IP.
    # - pName - name of vNic.
    # - pPlacement - placement No.
    # - pVlan - vlan name.
    # - pPool - mac address pool name.
    # - pCdnName - name of cdn (optional).
    # - pCdnSource - CDN source.
    #   Acceptable values for pCdnSource is None or 1.
    #   - default: None -> vNicName
    #       pCdnName: None -> pCdnSource=vNicName
    #       pCdnName: specified -> pCdnSource=vNicName
    #   - 1: -> user-defined.
    #       pCdnName: None -> error or warning (pending determination)
    #       pCdnName: specified -> pCdnSource=user-defined.
    #   - All other values: EXIT_ERR.
    # -
    # - pHba - create vHba instead of vNic. In that case the pVlan is N/A and pVlan will be interpreted as vSan.
    #        - cdnName will be N/A for vHba and ignored.
    #        - pPool will server as wwn-pool name. 
    #        - the wwnn pool will always be assumed to be node-default.
    #        - To prevent configuration error, block will be checked and if empty, will create default blocks:
    #        - xx....00:00-xx....00:ff for wwpn pool.
    #        - xx....ff:00-xx....ff:ff for wwpn pool.
    # return:   
    # - SUCCESS if vnic is created succcessfully with no error.
    # - EXIT_ERR if any error encountered during vnic creation.

    def createVnicVhba(self, pFi, pName, pPlacement, pVlan = 'default', pPool = 'default', pCdnName = None, pCdnSource = None, pHostPort = None, pVhba = None):
        debug = 1
        stat = 0

        if pVlan == None:
            pVlan = 'default'

        if pPool == None:
            pPool = 'default'

        if debug:
            printVars([pFi, pName, pPlacement, pVlan, pPool, pCdnName, pCdnSource, pHostPort, pVhba])

        if pVhba == None:

            # Work through this logic.
            #   - default: None -> vNicName
            #       pCdnName: None -> pCdnSource=vNicName
            #       pCdnName: specified -> pCdnSource=vNicName
            #   - 1: -> user-defined.
            #       pCdnName: None -> error or warning (pending determination)
            #       pCdnName: specified -> pCdnSource=user-defined.
            #   - All other values: EXIT_ERR.

            if pCdnName == None and pCdnSource == 1:
                printErr("If you set sdnSource == 1 (user-defined), then you need to specify cdnName.")
                printVars([pCdnName, pCdnSource])
                return EXIT_ERR

            if pCdnSource != 1 and pCdnSource != None:
                printErr("pCdnSource must be either 1 or None.")
                printVar(pCdnSource)
                return EXT_ERR

            if validateFcnInput([pFi, pName, pVlan, pPool, pPlacement]) == EXIT_ERR:
                printErr("Error with input.")
                return EXIT_ERR
    
            stat = sendUcsmBatchCmd(pFi, ['top', 'scope org', 'scope service-profile ' + self.spName,\
                'create vnic ' + str(pName), ])

            if re.search("Error: Managed object already exists", stat):
                printErr("Vnic " + str(pName) + " already exists, aborting...")
                return EXIT_ERR

            stat = sendUcsmBatchCmd(pFi, ['set identity mac-pool ' + str(pPool),'create eth-if ' + str(pVlan),\
                'set default-net yes', 'exit', 'set vcon ' + str(pPlacement)])

            if pHostPort != None:
                printDbg("Setting host port to: " + str(pHostPort))

                stat = sendUcsmBatchCmd(pFi, ['set host-port ' + str(pHostPort)])

            # cdnSource:
            #   - default: None -> vNicName
            #       pCdnName: None -> pCdnSource=vNicName
            #       pCdnName: specified -> pCdnSource=vNicName
            #   - 1: -> user-defined.
            #       pCdnName: None -> error or warning (pending determination)
            #       pCdnName: specified -> pCdnSource=user-defined.

            printVars([pCdnSource, pCdnName])

            if pCdnSource == 1:
                if pCdnName:
                    printDbg("cdnName created: " + str(pCdnName))
                    stat = sendUcsmBatchCmd(pFi, ['set cdn-name ' + str(pCdnName), 'set cdn-source user-defined'])
                else:
                    printErr("If cdnSource is 1, then cdnName must be specified.")
                    printVars([pCdnSource, pCdnName])
                    return EXIT_ERR
            elif pCdnSource == None:
                if pCdnName:
                    printDbg("cdnName: " + str(pCdnName))
                    stat = sendUcsmBatchCmd(pFi, ['set cdn-name ' + str(pCdnName), 'set cdn-source vnic-name'])
                else:
                    stat = sendUcsmBatchCmd(pFi, ['set cdn-source vnic-name'])
            else:
                printErr("cdnSource must be either 1 or None.")
                printVar(pCdnSource)
                return EXIT_ERR
    
            stat = sendUcsmBatchCmd(pFi, ['commit'])

            if re.search("Error:", str(stat)):
                printErr("Detected error pattern after sending commit. Check the error message: ")
                printErr(str(stat))
                return EXIT_ERR
        
            return SUCCESS

        elif pVhba == 1:
            if validateFcnInput([pFi, pName, pVlan, pPool, pPlacement]) == EXIT_ERR:
                printErr("Error with input.")
                return EXIT_ERR
    
            stat = sendUcsmBatchCmd(pFi, ['top', 'scope org', 'scope service-profile ' + self.spName,\
                'create vhba ' + str(pName)])

            if re.search("Error: Managed object already exists", stat):
                printErr("Vhba " + str(pName) + " already exists, aborting...")
                return EXIT_ERR

            stat = sendUcsmBatchCmd(pFi, ['set identity wwpn-pool ' + str(pPool), 'exit', 'exit', 'set identity dynamic-wwnn pool-derived'\
                'set vcon ' + str(pPlacement)])
    
            stat = sendUcsmBatchCmd(pFi, ['commit'])

            # Check the blocks and if empty, create block. For wwpn-pool that is not named "default", block will not be created.
            
            if pPool != "default":
                printWarn("pPool name is not default: " + str(pPool) + ". Block for this pool will not be created")
                printWarn("If no block is created previously for this wwpn-pool, service-profile can be in failure state.")
            else:
                stat = sendUcsmBatchCmd(pFi, ['top', 'scope org', 'scope wwn-pool node-default', 'show block'])

                if stat.strip() == None:
                    printDbg("wwn-pool node-default (wwnn) appears empty. Creating block...")             
                    stat = sendUcsmBatchCmd(pFi, ['create block 20:00:00:25:b5:00:ff:00 20:00:00:25:b5:00:ff:ff', 'commit'])
                else:
                    printDbg("wwn-pool node-default (wwnn) has block, bypass creating a new block.")

            stat = sendUcsmBatchCmd(pFi, ['top', 'scope org', 'scope wwn-pool default', 'show block'])

            if stat.strip() == None:
                printDbg("wwn-pool default (wwpn) appears empty. Creating block...")             
                stat = sendUcsmBatchCmd(pFi, ['create block 20:00:00:25:b5:00:00:00 20:00:00:25:b5:00:00:ff', 'commit'])
            else:
                printDbg("wwn-pool default (wwpn) has block, bypass creating a new block.")

            return SUCCESS
        else:
            printErr("Invalid value for pVhba. Either 0(None) or 1 is accepted.")
            return EXIT_ERR

    # This function is to be called after all scripts run. It is called from restoreBlade script.
    # it will disassociate test service-profile and re-associate back to original service-profile
    # that were attached to blade, prior to launching automation script.
    # input:    
    # - pUcsmssh - ucsm sol handle
    # - pSp - test service-profile
    # return:   
    # - sp2 - restore service-profile
    # - EXIT_ERR - on any error.

    def restoreBlade(self, pUcsmSsh, pSp):
        # fetch original sp name:

        spNameOriginal = getGlobalTmp("service-profile-backup").strip()

        if spNameOriginal == EXIT_ERR:
            printErr("Unable to find service-profile-backup entry from global tmp file")
            return EXIT_ERR

        if spNameOriginal != pSp.spName:
            # pSp - CXSX-pcie
            # sp2 - CXSX

            sp2 = sp(pBlade.location)
            sp2.fiHostName = pSp.fiHostName
            sp2.spName = spNameOriginal

            printDbg("recovered original sp name: " + str(spNameOriginal), debug)
            printDbg("disAssociating from " + pSp.spName, debug)

            pSp.disassoc(self.ucsmSsh, pBlade.location, 1)

            printDbg("associating with " + sp2.spName, debug)

            sp2.assoc(self.ucsmSsh, pBlade.location, 1, 1)

            # delete service-profile and its associated policies.

            pSp.delSolPolicy(self.ucsmSsh, pSp.spName)
            print "done deleting sol access"

            pSp.delBootPolicy(self.ucsmSsh, pSp.spName)
            print "done deleting boot policy"
        
            pSp.delBiosPolicy(self.ucsmSsh, pSp.spName)
            print "done deleting biospolicy"
        
            pSp.delHostFwPolicy(self.ucsmSsh, pSp.spName)
            print "done deleting host fw policy"
        
            pSp.delIpmiProfile(self.ucsmSsh, pSp.spName)
            print "done deleteing " + pSp.spName
        
            pSp.delSp(self.ucsmSsh, pSp.spName)
            print "done deleting blade access"
        
    # Wrapper function for restoreSystemState.
    # input:    
    # - pUcsmSsh - ucsm handle for sol
    # - pBmcSsh - bmc handle for sol
    # - pDictToken - if passed, only restore those token, if not restore all tokens.
    # - pDisconnect - if set, disconnect UCSM and BMC ssh sessions.
    # output:   
    # - RET_xxxx - based on restore success.

    def wRestoreSystemState(self, pFi, pFd, RET_STATUS, pDictTokens = None, pDisconnect = 1):
        return self.restoreSystemState(pFi, pFi.ucsmSsh, pFi.mSp.bmcSsh, pFi.mSp.mBlade, pFi.mSp, pFd, RET_STATUS, pDictTokens, pDisconnect)

    # This function is to be called after current script run and running next script.
    # The only exception is PCIE modules have their own specific restore API, any other script
    # in any module must call this function to restore the system to default state.
    # This will not change current service-profile associated with the blade, rather change current
    # service-profile and related policies to default state. Currently it is implemented to restore
    # only bios-policy to default state, is most or many tests scripts change the token to some
    # other non-default state, which could interfere and/or affect the test result for subsequence 
    # tests if it is not restored properly. 
    # default-state steps include:
    # - delete current bios-policy since it is possibly in non-default state after last script run.
    # - create bios-policy with the same name with all tokens are set to platform-default initially.
    # - set the bios-policy to service profile of the target system under test. 
    # (this way of restoring one by one is obsolete and likely to phase out.)
    # -set all bios-policy tokens to default
    # -verify all bios-policy tokens that can be checked from dmpsetup 
    # tokens that can be verified by dmpsetup is only subset of all tokens. Therefore, if any
    # token can not be verified but set to default, return WARNING.
    # token that CAN be verified through dmpsetup will return FAIL if default value is not set.
    # input:    
    # - pUcsmSsh - ucsm handle for sol
    # - pBmcSsh - bmc handle for sol
    # - pDictToken - if passed, only restore those token, if not restore all tokens.
    # output:   
    # - RET_xxxx - based on restore success.

    def restoreSystemState(self, pFi, pUcsmSsh, pBmcSsh, pBlade, pSp, pFd, RET_STATUS, pDictTokens = None, pDisconnect  = 1):
        debug = 0
        debugL2 = 0
        lDmpsetupName = []
        lUcsmTokenName = []
        lUcsmToken2Name = []
        lUcsmToken2Values = []
        lBiosTokenDefault = []
        lVerifyStat = []

        selLinesStart = None
        selLinesEnd = None
        selLinesEndErr = None
        selEndErr = None
    
        printInfoToFile("---------------------------")
        printInfoToFile("Entered system restore:", debug)
        printDbg("received RET_STATUS: " + str(RET_STATUS))

        stat = getGlobalTmp("no-clear-sel")
        printDbg("no clear sel flag:")

        if re.search("yes", str(stat)):
            printDbg("will not clear SEL.")
        else:
            printDbg("Will report SEL log and clear it.")

            selLinesEnd = sendUcsmBatchCmd(pFi, ['top', 'scope server ' + str(pFi.mSp.mBlade.location), 'show sel | wc -l'])
            printInfoToFile("No. of SEL lines after test completed: ")
            printInfoToFile(selLinesEnd)
        
            selLinesEndErr = sendUcsmBatchCmd(pFi, ['scope server ' + str(pFi.mSp.mBlade.location), 'show sel | grep error | wc -l'])
            printInfoToFile("No. of SEL lines with error after test completed: ")
            printInfoToFile(selLinesEndErr)
    
            try:
                if int(selLinesEndErr) > 0:
                    printWarn("Found at least one SEL log with error.")
                    RET_STATUS = setReturnStat(RET_STATUS, RET_PASS_E)
        
                if int(selLinesEndErr) < 5:
                    printInfoToFile('----------------------')
                    selEndErr = sendUcsmBatchCmd(pFi, ['scope server ' + str(pFi.mSp.mBlade.location), 'show sel | grep error'])
                    printInfoToFile(selEndErr)
                    printInfoToFile('----------------------')
            except Exception as msg:
                printWarn("Unable to determine the integer number of SEL LOG lines with error.")
        
            printInfoToFile("Clearing SEL log.")
            stat = sendUcsmBatchCmd(pFi, ['scope server ' + str(pFi.mSp.mBlade.location), 'clear sel', 'commit'])
        
            time.sleep(10)
            selLinesStart = sendUcsmBatchCmd(pFi, ['scope server ' + str(pFi.mSp.mBlade.location), 'show sel | wc -l'])
            printInfoToFile("No. of SEL lines after clear: ")
            printInfoToFile(selLinesStart)

        setGlobalTmp("no-clear-sel", "yes")

        # Validate all inputs.

        if validateFcnInput([pFi, pUcsmSsh, pBmcSsh, pBlade, pSp]) == EXIT_ERR:
            printErr("function input validation failed.")
            return RET_TERM
    
        if pSp.delBiosPolicy(pUcsmSsh, pSp.spName) == EXIT_ERR:
            return RET_TERM

        if pSp.setBiosPolicy(pUcsmSsh, pSp.spName) == EXIT_ERR:
            return RET_TERM

        if  pSp.setSolPolicy(pFi) == EXIT_ERR:
            printErr("Failed to set SOL policy.")
            return RET_BLOCK

        if pDisconnect:
            pUcsmSsh.close()
            pBmcSsh.close()
        else:
            printDbg("Will not disconnect the ucsm and bmc sessions.")

        return RET_STATUS

    # Shows brief system overall state designed to run after each script.
    # input:
    # - pUcsmSsh - ssh console to ucsm.
    # return:
    # - None
    
    def showSystemState(self, pUcsmSsh):
        printDbg("---------------------")
        printDbg("Showing system state:")
        stat = None

        # show service-profile state

        cli_with_ret(pUcsmSsh, "scope org", self.fiHostName)
        time.sleep(1)
        cli_with_ret(pUcsmSsh, "scope service-profile " + self.spName, self.fiHostName)
        time.sleep(1)
        stat = cli_with_ret(pUcsmSsh, "show stat | no-more", self.fiHostName)

        if stat:
            printDbg("sp state:")
            printDbg(stat)
        else:
            printErr("No output or error from: 'scope sp/show stat'.")

        printDbg("---------------------")

        # show sp vnics

        cli_with_ret(pUcsmSsh, "scope org", self.fiHostName)
        time.sleep(1)
        cli_with_ret(pUcsmSsh, "scope service-profile " + self.spName, self.fiHostName)
        time.sleep(1)
        stat = cli_with_ret(pUcsmSsh, "show vnic | no-more", self.fiHostName)

        if stat:
            printDbg("sp vNics:")
            printDbg(stat)
        else:
            printErr("no output or error from: 'scope sp/show vnic'.")
        printDbg("---------------------")

        '''

        # show sp boot-policy

        cli_with_ret(pUcsmSsh, "scope org", self.fiHostName)
        time.sleep(1)
        cli_with_ret(pUcsmSsh, "scope service-profile " + self.spName, self.fiHostName)
        time.sleep(1)
        stat = cli_with_ret(pUcsmSsh, "show boot-policy | no-more", self.fiHostName)

        if stat:
            printDbg("sp boot-policy:")
            printDbg(stat)
        else:
            printErr("no output or error from: 'scope sp/show boot-policy'.")
        printDbg("---------------------")

        # show sp boot-policy itself

        time.sleep(1)
        cli_with_ret(pUcsmSsh, "scope org", self.fiHostName)
        time.sleep(1)
        cli_with_ret(pUcsmSsh, "scope boot-policy " + self.spName, self.fiHostName)
        time.sleep(1)
        stat = cli_with_ret(pUcsmSsh, "show expand | no-more", self.fiHostName)
        time.sleep(1)

        if stat:
            printDbg("show expand | no-more:")
            printDbg(stat)
        else:
            printErr("no output or error from: 'show boot-policy expand'.")
        printDbg("---------------------")

        # show bios-policy brief

        time.sleep(1)
        cli_with_ret(pUcsmSsh, "scope org", self.fiHostName)
        time.sleep(1)
        cli_with_ret(pUcsmSsh, "scope bios-policy " + self.spName, self.fiHostName)
        time.sleep(1)
        stat = cli_with_ret(pUcsmSsh, "show expand | grep Enabled", self.fiHostName)
        time.sleep(1)

        if stat:
            printDbg("show bios-policy | grep Enabled:")
            printDbg(stat)
            printDbg("---------------------")
        else:   
            printErr("no output or error from: 'show bios-policy | grep Enabled'.")
        printDbg("---------------------")

        stat = cli_with_ret(pUcsmSsh, "show expand | grep Disabled", self.fiHostName)

        if stat:
            time.sleep(1)
            printDbg("show bios-policy | grep Disabled:")
            printDbg(stat)
            printDbg("---------------------")
        else:
            printErr("no output or error from: 'show bios-policy | grep Disabled'.")

        '''
        return SUCCESS

    # Restores boot-policy to default state.
    # input:
    # - pUcsmSsh - ssh console to ucsm ssh.
    # - pFi - UCS FI instance.
    # return:
    # - SUCCESS in completion.
    # - EXIT_ERR in any error condition occurred.

    def restoreBootPolicy(self, pUcsmSsh, pFi):

        # restore boot-policy to UEFI.
    
        cli_with_ret(pUcsmSsh, "scope org", pFi.hostName)
        time.sleep(1)
        cli_with_ret(pUcsmSsh, "scope boot-policy " + self.spName, pFi.hostName)
        time.sleep(1)
        cli_with_ret(pUcsmSsh, "set reboot-on-update yes", pFi.hostName)
        time.sleep(1)
        cli_with_ret(pUcsmSsh, "set boot-mode uefi", pFi.hostName)
        time.sleep(1)
        cli_with_ret(pUcsmSsh, "commit", pFi.hostName)
        time.sleep(1)

        stat = self.waitConfigComplete(pUcsmSsh)   

        if stat == EXIT_ERR:
            printErr("Timed out waiting for boot-policy restore configuration")
            return EXIT_ERR

        return SUCCESS

    # Attempt to determine the blade PID if this service-profile object is associated. 
    # input:
    # - pUscmSsh - ssh console to UCSM.
    # return:
    # - EXIT_ERR if unable to determine the blade PID.
    # - bladePid if able to determine the blade PID.

    def getBladePid(self, pUcsmSsh):
        debug = 0

        if self.bladePid:
            return self.bladePid

        # using blade location, get the PID using acknowledge PID field. Once PID is extracted, do a series if check to make sure
        # PID is valid. If any checks fail, set the bladePid member back none and return EXIT_ERR.

        if self.bladeLoc:
            ret = cli_with_ret(pUcsmSsh, "scope server " + self.bladeLoc, self.fiHostName)
            time.sleep(3)      
            ret = cli_with_ret(pUcsmSsh, "show inventory | grep \"Acknowledged PID\"", self.fiHostName)
            time.sleep(3)

            printDbg("ret: \n=================\n" +  str(ret) + "\n===============", debug)
            
            if re.search(":", ret):
                self.bladePid = ret.split(':')[-1].strip()
                printDbg("blade PID is: " + str(self.bladePid), debug)

                if re.search("UCS", self.bladePid):
                    return SUCCESS
                elif re.search("N20", self.bladePid):
                    return SUCCESS
                else:
                    printErr("blade PID does not contain 'UCS or N20' sub-string. Either blade model is too old (not supported) or wrong value for PID")
                    self.bladePid = None
                    return EXIT_ERR   
                
            else:                
                printErr("Response does not have :. Unable to extract blade PID.")
                self.bladePid = None
                return EXIT_ERR
        else:
            printErr("blade location is not set. Unable to determine blade PID.")
            return EXIT_ERR
            
    # will perform a wait loop until the blade is in configured and associated status.
    # input:
    # - pUcsmSsh - SSH connection to UCSM cli.
    # - pInterVal - interval between cycles
    #  - pMaxWaitCycle - maximum interval to tick, total wait time is pInterval * pMaxWaitCycle
    # return:
    # - EXIT_ERR if timeOut, 
    # - SUCCESS if success.

    def waitConfigComplete(self, pUcsmSsh, pInterVal = 40, pMaxWaitCycle = 80):
        configDone = None
        configWaitCounter = 0
        debug = 1
    
        if self.spName == "mysp":
            printErr("service-profile is likely in different org. Can not handle this.")
            return EXIT_ERR

        cli_with_ret(pUcsmSsh, "scope org", self.fiHostName)
        time.sleep(1)
        cli_with_ret(pUcsmSsh, "scope service-profile " + self.spName, self.fiHostName)
        time.sleep(1)

        printDbg("Waiting for configuration to complete.")
    
        while configDone == None:
            ret = cli_with_ret(pUcsmSsh, "show assoc detail | grep Assoc", self.fiHostName)

            if ret == EXIT_ERR:
                return EXIT_ERR
            
            printDbg("ret: " + ret.strip(), debug)

            if re.search("Associated", ret):
                configDone = 1
                printDbg("Configuration is done. Give another 30 sec-s to settle", debug)
                time.sleep(30)
                return SUCCESS
    
            time.sleep(pInterVal)
            printNnl(".")
            configWaitCounter += 1
    
            if configWaitCounter > pMaxWaitCycle:
                printErr("Timeout waiting for configuration is done. Token might not have been set correctly. Proceed at your own risk.")
                return EXIT_ERR

    # Note: this function is obsolete and unlikely to be used ever again.
    # This function will get the bios-policy token default value. The retrieved token will only return whatever is set in the blade model's
    # default value. It will not check whether that default value is correctly set or not. That has to be checked from UCSM bios defaults,
    # can not be automated. This is most useful in comparing to verify what is set in the bios-policy as a result of selecting platform-default
    # matches the corresponding default value in bios-default policy value.
    #
    # input:
    # - pUcsmSsh - sol connection to Ucsm.
    # - pBmcSsh - sol connection to BMC.
    # - pFi - FI instance.
    # - pBiosToken - name of the bios token 
    # - pBiosTokenL2 - name of the l2 bios token.
    # - pAll - returns all tokens if it is not None, in this case pBiosToken(L2) param-s are ignored.
    # return 
    # - EXIT_ERR if unable to fetch the default value.
    # - default value for bios-token is found in bios-default policy if pAll = None.
    #           
    # - default values for all bios-tokens if pAll != None.

    def getBiosTokenDefault(self, pUcsmSsh, pBmcSsh, pFi, pBiosToken, pBiosTokenL2, pAll = None):
        debug = 0
        debugL2 = 0
        lBiosTokenDefault = None
        lBiosTokenDefaultL2 = None
        lBiosTokenDefaultFound = None    

        if pUcsmSsh == None:
            printErr("pUcsmSsh is None")
            return EXIT_ERR

        if pBmcSsh == None:
            printErr("pBmcSsh is None")
            return EXIT_ERR

        if pFi == None:
            printErr("pFi is None")
            return EXIT_ERR

        if pBiosToken == None:
            printErr("pBiosToken is None")
            return EXIT_ERR

        if pBiosTokenL2 == None:
            printErr("pBiosTokenL2 is None")
            return EXIT_ERR

        printDbg("-----------------------------")
        printDbg("looking for bios-default value for " + str(pBiosToken) + " : " + str(pBiosTokenL2), debug)
    
        if self.getBladePid(pUcsmSsh) == EXIT_ERR:
            printErr("unable to determine blade PID. Can not get bios-default token value as a result.")
            return EXIT_ERR
    
        # Translate the name of token to the one compatible with bios-default naming scheme.
        # i.e. bios-policy-name -> Bios Token Name

        if pAll == None:    
            lBiosTokenDefault = re.sub("-", " ", pBiosToken).title().strip()
            lBiosTokenDefaultL2 = re.sub("-", " ", pBiosTokenL2).title().strip()
    
            printDbg("translated names: " + str(lBiosTokenDefault) + " | " + str(lBiosTokenDefaultL2), debug)
            #printDbg("lBiosTokenDefaultL2(hex): " + ":".join("{:02x}".format(ord(c)) for c in lBiosTokenDefaultL2), debugL2)
            printDbg("lBiosTokenDefaultL2(hex): " + (":".join(  "%02x" % ord(c)  ) for c in lBiosTokenDefaultL2), debugL2)

                #rxNextCapOfs = "{:03x}".format(int(rxNextCapOfs, 16) + 0x01)
                #rxNextCapOfs = "%03x" % (int(rxNextCapOfs, 16) + 0x01)

        ret = cli_with_ret(pUcsmSsh, "scope system", self.fiHostName)
        time.sleep(1)      
        ret = cli_with_ret(pUcsmSsh, "scope server-defaults", self.fiHostName)
        time.sleep(1)      
        ret = cli_with_ret(pUcsmSsh, "scope platform 'Cisco Systems, Inc.' " + str(self.bladePid) + " 0", self.fiHostName)
        time.sleep(1)      
        ret = cli_with_ret(pUcsmSsh, " show bios-settings detail | no-more", self.fiHostName)
        time.sleep(1)      

        printDbg("show bios-settings detail | no-more output:\n", debug)

        if pAll != None:
            printDbg("returning all default values.", debug)
            return ret
    
        # At this point ret will have huge array of all tokens. walk through each and attempt to find the one that matches.
        
        # find lBiosTokanDefault by tokenizing (split by newline)
        #   if found, walk line by line until next empty line.
        #   any lines found untill empty lines are (after 1st one) is L2 token.
        #       walk through again (from 2nd to empty line) to lBiosTokenDefaultL2 match.
        #       if match found, extract its value.

        if ret:    
            retTokens = ret.split('\n')
        else:
            printErr("ret is empty. can not set retTokens.")
            return EXIT_ERR
            
        lBiosTokenDefaultFound = None    

        printDbg("found " + str(len(retTokens)) + " lines...", debug)

        ZeroLenLineCounter = 0
    
        for currLine in retTokens:
            printDbg("curr Line: " + str(currLine).strip(), debugL2)
    
            # if main token found set the flag.
    
            if re.search(lBiosTokenDefault, currLine, re.IGNORECASE):
                printDbg("found default token name: " + str(lBiosTokenDefault), debug)
                lBiosTokenDefaultFound = 1
                continue
    
            # once we set the flag, we need to skip this line before searching L2 token name since it is main token line. 

            # if main token found flag is set, then search for l2 token name.

            if lBiosTokenDefaultFound:
                printDbg("currline(hex): " + ":".join("{:02x}".format(ord(c)) for c in currLine), debugL2)

                if re.search(lBiosTokenDefaultL2, currLine, re.IGNORECASE):
                    printDbg("found default L2 token name: " + str(lBiosTokenDefaultL2), debug)
                    
                    # further check, verify it conforms to formatting: <l2TokenName>: <defValue>

                    if re.search(": ", currLine):          
                        printDbg("found the default value: " + str(currLine).strip(), debug)
                        return currLine.split(":")[-1].strip()
                    else:
                        printErr("Can not find :. does it conform to this line format? L2TokenName: defValue")
                        return EXIT_ERR
                elif len(currLine.strip()) < 1:
                    ZeroLenLineCounter += 1
                    printWarn("empty line reached after main token was found. This means did not find sub token", debug)
                    return EXIT_ERR
    
    # Sets the bios-policy token and at the same time verifies the token set correctly.
    # This function is largely the wrapper function that integrates the setBiosToken and checkTokenEfiDmpSetup functionality.
    # Ideally, the setBiosToken should itself integrate the checkTokenEfiDmpSetup, however because of the fact that checkTokenEfiDmpSetup
    # requires pBlade parameter which the setBiosToken does not require and to the fact modifying the setBiosToken will affect
    # massive number of tests, this function servers "newer" version of setBiosToken that integrates pBlade parameter acceptance also.
    # Doing so will enable the consumers of the function setBiosToken function to gradually transfer more smoothly and eventually
    # phasing out the setBiosToken function.
    # The bios-policy name MUST be same as the service-profile name!, otherwise it will not function corretly.
    # NOTE: To enhance the default value setting, it needs to know the value of default setting from default bios-policy.
    # Otherwise, it currently return unsupported status for default-setting.

    # input:
    # - pUcsmSsh - sol connection to Ucsm.
    # - pBmcSsh - sol connection to BMC.
    # - pFi - FI instance.
    # - pBlade - blade instance.
    # - pBiosToken - name of the bios token
    # - pBiosTokenL2 - name of the l2 bios token.
    # - pVal - value to be set.
    # - pReboot - whether blade reboot required:
    #           1 - will reboot the blade and wait till configuration is done.
    #           0 - will not reboot the blade and leave immediately.
    #           any other value or (preferably -1) - will leave the current setting intact
    # - pVer - whether to verify the setting after configuration is complete.
    # return:  
    # - EXIT_ERR if error setting the token except verification fail.
    # - EXIT_WARN   - if dmpsetup entry can not be found
    #               - if token can not be verified that it is correctly.
    # !!! no longer the case for time being -> SUCCESS - if token is set correctly and verified.
    # - cFi - if token is set successfully.

    def setBiosTokenVerify(self, pFi, pBiosToken, pBiosTokenL2, pVal, pReboot = 1, pWait = 1, pVer = 0):
        stat = None
        efiShellOutput = None
        debug = 1

        CONFIG_VERIFY_TOKEN = 0

        printDbg("Entered...")

        if validateFcnInput([pFi, pBiosToken, pBiosTokenL2, pVal]) == EXIT_ERR:
            printErr("Invalid parameters.")
            return EXIT_ERR

        printVars([pBiosToken, pBiosTokenL2, pReboot, pWait, pVer], debug)

        stat = self.setBiosToken(pFi, pBiosToken, pBiosTokenL2, pVal, pReboot, pWait, pVer)

        printWarnMinor("CONFIG_VERIFY_TOKEN = 0. Will not verify whether token is set correctly.")

        printDbg("1. Reconnecting to bmc...")

        pFi.mSp.bmcSsh.close()
        pFi.mSp.bmcSsh = sshLoginLinux(pFi.mSp.bmcSsh, pFi.mSp.mgmtIp, pFi.mSp.mgmtUsername, pFi.mSp.mgmtPassword)

        if not pFi.mSp.bmcSsh:
            printErr("Can not login to bmc.")
            return EXIT_ERR
        else:
            printDbg("Login to bmc ssh is OK.")

        printDbg("Booting to efi shell..")

        lFi = pFi.mSp.mBlade.wBootEfiShell(pFi, 1, None)

        if lFi == EXIT_ERR:
            printDbg("1. Failed to boot to efi shell.")
        else:
            printDbg("Could be booted to efi shell")
    
        printDbg("2. Reconnecting to bmc...")

        pFi.mSp.bmcSsh.close()
        pFi.mSp.bmcSsh = sshLoginLinux(pFi.mSp.bmcSsh, pFi.mSp.mgmtIp, pFi.mSp.mgmtUsername, pFi.mSp.mgmtPassword)

        if not pFi.mSp.bmcSsh:
            printErr("Can not login to bmc.")
            return EXIT_ERR
        else:
            printDbg("Login to bmc ssh is OK.")
            #return pFi
            return SUCCESS

        #return pFi
        return SUCCESS

    # Sets the bios-policy token. 
    # The bios-policy name MUST be same as the service-profile name!, otherwise it will not function corretly.
    # NOTE: To enhance the default value setting, it needs to know the value of default setting from default bios-policy.
    # Otherwise, it currently return unsupported status for default-setting.
    #
    # input:
    # - pUcsmSsh - sol connection to Ucsm.
    # - pBmcSsh - sol connection to BMC.
    # - pFi - FI instance.
    # - pBiosToken - name of the bios token 
    # - pBiosTokenL2 - name of the l2 bios token.
    # - pVal - value to be set. 
    # - pReboot - whether blade reboot required: 
    #           1 - will reboot the blade and wait till configuration is done. 
    #           0 - will not reboot the blade and leave immediately.
    #           any other value or (preferably -1) - will leave the current setting intact
    # - pVer - whether verify the setting after configuration is complete.
    # return 
    # - EXIT_ERR if error,
    # - EXIT_WARN if dmpsetup entry can not be found
    #           !!!! Below is not accurate. No code returns it.
    #           or if dmpsetup entry found but can not find from ucsm token list file.
    #           list [dmpsetup entry name for token][expected value]

    def setBiosToken(self, pFi, pBiosToken, pBiosTokenL2, pVal, pReboot = 1, pWait = 1, pVer = 0):
        debug = 1
        debugL2 = 0
        ret  = None
        retVal = None
        configDone = None
        configWaitCounter = 0
        line = None
        counter = 0
        token2Idx = None
        dmpsetupName = None

        lDmpsetupName = None
        lUcsmTokenName = None
        lUcsmToken2Name = None
        lUcsmToken2Values = None
        lReturn = SUCCESS

        if debug:
            printDbg("-------------------\nEntered: ")
            printVars([pBiosToken, pBiosTokenL2, pVal, pReboot, pWait, pReboot])
    
        # Set the ucsm token stage now. 

        printDbg("Setting UCSM bios token", debug)    
    
        ret = cli_with_ret(pFi.ucsmSsh, "scope org", self.fiHostName)
        time.sleep(1)
        ret = cli_with_ret(pFi.ucsmSsh, "scope bios-policy " + self.spName, self.fiHostName)
        time.sleep(1)

        # Set the reboot required (default).

        if pReboot == 1:
            printDbg("Setting yes to reboot", debug)
            ret = cli_with_ret(pFi.ucsmSsh, "set reboot-on-update yes", self.fiHostName)
            time.sleep(1)
            ret = cli_with_ret(pFi.ucsmSsh, "commit", self.fiHostName)
            time.sleep(1)
        elif pReboot == 0:
            printDbg("setting no to reboot", debug)
            ret = cli_with_ret(pFi.ucsmSsh, "set reboot-on-update no", self.fiHostName)
            time.sleep(1)
            ret = cli_with_ret(pFi.ucsmSsh, "commit", self.fiHostName)
            time.sleep(1)
            return lReturn
        else:
            printDbg("reboot setting unchanged", debug)

        # Issue the bios-policy token now.

        ret = cli_with_ret(pFi.ucsmSsh, "set " + pBiosToken + " " + pBiosTokenL2 + " " + pVal, self.fiHostName)
        time.sleep(1)
        ret = cli_with_ret(pFi.ucsmSsh, "commit", self.fiHostName)
        time.sleep(1)

        # if wait is specified, wait it out. 
    
        if pWait:
            ret = self.waitConfigComplete(pFi.ucsmSsh)

            if ret == EXIT_ERR:
                printErr("timeout waiting for configuration to complete")
                return ret
        else:
            printDbg("Service-profile configuration is finished for change of token.")
            return lReturn

    # new wrapper function that implements refreshSp in a new way.
    # this will replace to original refreshSp function eventually

    # This function will use the blade's location and ucsm sol connection to update the class field's to most current information"
    # blade location field must always be set before calling this function.

    # input:
    # - pUcsmSsh - sol connection to Ucsm.
    # -  pFi - FI instance.
    # - pWait - if 1, wait till server becomse either assoc-d or non-assoc when the assoc status is 'removing' or 'associating' with timeout value.
    #         if 0, if server assoc status is anything other than associated, then set associate status to None and exit.
    # return:
    # - EXIT_ERR - if error, 
    # - SUCCESS if success.

    def refreshSpNew(self, pUcsmSsh, pFi, pBlade=None, pWait=0):
        ret1 = None
        ret2 = None
        counter = 0
        debug = 0

        printDbg("Entered: ", debug)

        if self.spName == "mysp":
            printErr("service-profile is likely in different org, associated with mysp sp. Can not handle this.")
            return EXIT_ERR

        if self.spName == "None":
            printErr("service-profile is None")
            return EXIT_ERR

        self.fiHostName = pFi.hostName

        # Set management ip.

        if pBlade:
            if self.setBmcMgmtIp(pUcsmSsh, pFi, pBlade.location) == EXIT_ERR:
                printErr("Failed to set management IP.")
                return EXIT_ERR

            if self.refreshSp(pUcsmSsh) == EXIT_ERR:
                printErr("Failed to refresh sp.")
                return EXIT_ERR

            # set self.bmcSsh
        
            self.bmcSsh = sshLoginLinux(self.bmcSsh, self.mgmtIp, self.mgmtUsername, self.mgmtPassword)
        
            if not self.bmcSsh:
                printErr("Can not login to bmc.")       
                return EXIT_ERR
            else: 
                printDbg("Login to bmc ssh is OK.")        
                return SUCCESS
        else:
            printWarn("pBlade is None, will not set management ip or blade.")
            return SUCCESS

    # This function will use the blade's location and ucsm sol connection to update the class field's to most current information"
    # blade location field must always be set before calling this function.
    # input:
    # - pUcsmSsh - SSH connection to UCSM cli.
    # - pFi - FI instance.
    # - pWait - if 1, wait till server becomse either assoc-d or non-assoc when the assoc status is 'removing' or 'associating' with timeout value.
    #           if 0, if server assoc status is anything other than associated, then set associate status to None and exit.
    # return:
    # - None if error, 1 if success.

    def refreshSp(self, pUcsmSsh, pWait=None):
        printDbg("Entered: ")
        ret1 = None
        ret2 = None
        counter = 0
        debug = 0

        if debug:
            printVars([pUcsmSsh, self.spName])

        if self.spName == "mysp":
            printErr("service-profile is likely in different org. Can not handle this.")
            return EXIT_ERR

        if self.spName == "None":
            printErr("service-profile is None")
            return EXIT_ERR

        if self.fiHostName == None:
            printErr("FI hostname is set to None. Can not continue")    
            return EXIT_ERR

        # Determine blade service profile if it is not set deliberately.

        if self.spName == None:
            printDbg("spName is not deliberately set. Try Setting from blade instance.")
            self.spName = self.mBlade.spName

        if self.spName == None:
            printDbg("spName is unknown after setting from blade. Will try determine from actual blade.")

            cli_with_ret(pUcsmSsh, "scope org", self.fiHostName)
            time.sleep(1)
            cli_with_ret(pUcsmSsh, "scope service-profile " + str(self.spName), self.fiHostName)
            time.sleep(1)
            ret1 = cli_with_ret(pUcsmSsh, "show assoc detail | grep Association", self.fiHostName)
    
            printDbg("ret1: \n============\n" + str(ret1) + "\n==============\n", debug)
    
            if re.search("Associated", ret1):
                ret2 = cli_with_ret(pUcsmSsh, "show assoc detail | egrep \"^Server:\"", self.fiHostName)
    
                print "ret2: " + str(ret2)
    
                if ret2:
                    self.bladeLoc = ret2.strip().split(' ')[1].strip()
    
                printDbg("sp.refresh: blade location is set to " + str(self.bladeLoc), debug)
    
            else:
                printDbg("return did not contain associated string", debug)
    
                if pWait == None:
                    printDbg("pWait=None", debug)
                    self.spName = None
                    printDbg("warning! SP is not in associated status and pWait=0: setting spName to None")
                    printDbg("sp could be unassoc-d, currently being assoc-d or unassoc-d")
                else:
                    printDbg("pWait=1", debug)
                    conuter = 0
    
                    while counter < 600:
                        time.sleep(30)
                        counter += 30
                        cli_with_ret(pUcsmSsh, "scope org", self.fiHostName)
                        time.sleep(1)
                        cli_with_ret(pUcsmSsh, "scope service-profile " + self.spName, self.fiHostName)
                        time.sleep(1)
                        ret1 = cli_with_ret(pUcsmSsh, "show assoc detail | grep Associated", self.fiHostName)
            
                        printDbg("ret1: \n============\n" + str(ret1) + "\n==============\n", debug)
    
                        if ret1 == EXIT_ERR:
                            printErr("Error getting show assoc detail output.")
                            return EXIT_ERR
    
                        if re.search("Associated", ret1):
                            ret2 = cli_with_ret(pUcsmSsh, "show assoc detail | egrep \"^Server:\"", self.fiHostName)
                
                            printDbg("ret2: \n============\n" + str(ret2) + "\n==============\n", debug)
                
                            if ret2:
                                self.bladeLoc = ret2.split(' ')[1].strip()
                
                            printDbg("sp.refresh: sp is set to " + str(self.bladeLoc), debug)
                            return SUCCESS
                
                    printErr("timeout: waiting for service assoc-d status")
                    return EXIT_ERR
                            # determine blade location.
    
        # Set blade pid now. If blade location is not set and thus can not pid now, exit with WARNING
        # the reason is later, getBladePid() function can be used to set the blade PID for add'l attempt.

        stat = self.getBladePid(pUcsmSsh)

        if stat == EXIT_ERR:
            printWarn("blade PID can not be set.")
            return EXIT_ERR
        else:
            return SUCCESS

    # This function will start association of service-profile with the server.
    # input:
    # - pUcsmSsh - SSH connection to UCSM cli.
    # - pLocation - location of the blade to be assoc-d
    # - pConsole - console pattern to match
    # - pForce - if SP is already assoc-d, it will be disassoc-d first
    # - pWait - wait until association is complete (disassoc is complet if already assoc-d)
    # return:
    # - Elapsed time of assocation in seconds, None if timeout or some other error.

    def assoc(self, pUcsmSsh, pLocation, pWait=0, pForce=0):
        output1 = None
        elapsedTime = 0
        CONFIG_TIMEOUT_ASSOC_WAIT_SEC = 3600
        CONFIG_TIMEOUT_ASSOC_INTERVAL_SEC = 30
        debug = 0

        if self.spName == None:
            printErr("spName is set to None")
            return EXIT_ERR

        if pUcsmSsh == None:
            printErr("pUcsmSsh is None")
            return EXIT_ERR

        cli_with_ret(pUcsmSsh, "scope org", self.fiHostName)
        time.sleep(1)
        cli_with_ret(pUcsmSsh, "scope service-profile " + self.spName, self.fiHostName)
        time.sleep(1)

        if pForce == 0:
            output1 = cli_with_ret(pUcsmSsh, "show assoc detail | grep Association:", self.fiHostName)

            if re.search("Associated", output1):
                printErr("already associated. Force option is not set! Exiting...")
                return EXIT_ERR

        # force is specified.

        cli_with_ret(pUcsmSsh, "disassociate", self.fiHostName)
        time.sleep(1)
        cli_with_ret(pUcsmSsh, "commit", self.fiHostName)
        time.sleep(1)
        cli_with_ret(pUcsmSsh, "associate server " + pLocation, self.fiHostName)
        time.sleep(1)
        cli_with_ret(pUcsmSsh, "commit", self.fiHostName)             
        time.sleep(1)
    
        if pWait == 0:
            printInfoToFile("Started associating service-profile " + str(self.spName) +  " with server " + str(pLocation) + ", returning with no Wait.")
            return EXIT_ERR
        else:
            printDbg("Waiting until assoc is complete")

            while elapsedTime < CONFIG_TIMEOUT_ASSOC_WAIT_SEC:
                output1 = cli_with_ret(pUcsmSsh, "show assoc detail | grep Association:", self.fiHostName)

                if re.search("Associated", output1):
                    printDbg("\nAssociation is complete.")
                    return elapsedTime
                else:
                    time.sleep(CONFIG_TIMEOUT_ASSOC_INTERVAL_SEC)
                    elapsedTime += CONFIG_TIMEOUT_ASSOC_INTERVAL_SEC

                    if elapsedTime == CONFIG_TIMEOUT_ASSOC_INTERVAL_SEC:
                        printDbg("Waiting for assoc for " + str(elapsedTime) + " seconds\n")
                    else:
                        if elapsedTime / CONFIG_TIMEOUT_ASSOC_INTERVAL_SEC % 15 == 0: 
                            printDbg("\n")

                        printNnl(" " + str(elapsedTime))
                    
            printErr("\nTimed out waiting for associaiton to complete. There could be association error or taking too long.")
            return EXIT_ERR
              
    # This function will start association of service-profile with the server.
    # input:
    # - pUcsmSsh - ucsm sol connection
    # - pLocation - location of the blade to be assoc-d
    # - pConsole - console pattern to match
    # - pWait - wait until association is complete (disassoc is complet if already assoc-d)
    # return:
    # - Elapsed time of assocation in seconds, None if timeout or some other error, SUCCESS is pWait = 0

    def disassoc(self, pUcsmSsh, pLocation, pWait=0):
        debug = 0

        if validateFcnInput([pUcsmSsh, pLocation]) == EXIT_ERR:
            printErr("Invalid parameters.")
            return EXIT_ERR
    
        elapsedTime = 0
        CONFIG_TIMEOUT_DISASSOC_WAIT_SEC = 3600
        CONFIG_TIMEOUT_DISASSOC_INTERVAL_SEC = 30

        cli_with_ret(pUcsmSsh, "scope org", self.fiHostName)
        time.sleep(1)
        cli_with_ret(pUcsmSsh, "scope service-profile " + self.spName, self.fiHostName)
        time.sleep(1)
        cli_with_ret(pUcsmSsh, "disassociate", self.fiHostName)
        time.sleep(1)
        cli_with_ret(pUcsmSsh, "commit", self.fiHostName)
        time.sleep(1)

        if pWait == 0:
            printDbg("sent disassociation command, pWait=0, exiting...")
            return SUCCESS
        else:
            while elapsedTime < CONFIG_TIMEOUT_DISASSOC_WAIT_SEC:
                cli_with_ret(pUcsmSsh, "scope server " + pLocation, self.fiHostName)
                time.sleep(1)
                output1 = cli_with_ret(pUcsmSsh, "show assoc", self.fiHostName)

                if output1 == None:
                    printErr("unable to to get association status.")
                    return EXIT_ERR
                else:
                    if re.search("None", output1):
                        printDbg("\nDisassociation is complete.")
                        return elapsedTime
                    else:
                        time.sleep(CONFIG_TIMEOUT_DISASSOC_INTERVAL_SEC)
                        elapsedTime += CONFIG_TIMEOUT_DISASSOC_INTERVAL_SEC
        
                        if elapsedTime <= CONFIG_TIMEOUT_DISASSOC_INTERVAL_SEC:
                            printDbg("waiting for disassoc for " + str(elapsedTime) + " seconds")
                        else:
                            if elapsedTime / CONFIG_TIMEOUT_DISASSOC_INTERVAL_SEC % 15 == 0: 
                                printDbg("\n")

                            printNnl(" " + str(elapsedTime))
    
            printErr("\nTimed out waiting for dis-associaiton to complete. There could be disassociation error or taking too long.")
            return EXIT_ERR

    # Given ssh handle to ucsm, set the management IP.
    # input:
    # - pSsh - ssh handle
    # - pFi - FI instance
    # - pBladeLocation - blade location info.
    # return:
    # - EXIT_ERR if fails to sets the bmc management IP.
    # - SUCCESS if sets the bmc management ip successfully.
    
    def setBmcMgmtIp(self, pSsh, pFi, pBladeLocation):
        debug = 0

        if validateFcnInput([pSsh, pFi, pBladeLocation]) == EXIT_ERR:
            printErr("Invalid parameters.")
            return EXIT_ERR

        printDbg("Entered: ")
        lFilterString = '255.'

        out1 = cli_with_ret(pSsh, "scope server " + pBladeLocation, self.fiHostName)
        time.sleep(1)
        out1 = cli_with_ret(pSsh, "scope cimc", self.fiHostName)
        time.sleep(1)

        #cli_with_ret(pSsh, 'scope server ' + pBladeLocation)
        #time.sleep(1)
        #cli_with_ret(pSsh, 'scope cimc')
        #pSsh.expect(expectTermination)
        #time.sleep(1)
        #pSsh.expect(expectTermination)

        out1 = cli_with_ret(pSsh, "show mgmt-if | grep " + lFilterString, self.fiHostName)
    
        printDbg("show mgmt-if output: " + str(out1), debug)
        out1 = str(out1).strip()
        self.mgmtIp = out1.split(' ')[0].strip()

        if self.mgmtIp.strip() == "" or self.mgmtIp.strip() == None:
            printErr("bmc management IP not found")
            return EXIT_ERR
        else:
            printDbg("bmc management IP found: "  + self.mgmtIp)
            return SUCCESS

    # Given service-profile name, create local disk configuration policy and will attach to service-profile.
    # pSsh      - ssh handle to ucsm
    # return     - SUCCESS if setting is OK, EXIT_ERR if error.

    def setLocalDiskConfigPol(self, pFi):
        debug = 0
        debugL2 = 0
    
        if self.spName == None:
            printErr("spName for sp is not set, trying to set now:")
            return EXIT_ERR

        printDbg("Entered... " + self.spName, debug)

        if pFi.ucsmSsh == None:
            print "error: UCSM ssh is not initialized"
            return EXIT_ERR

        cli_with_ret(pFi.ucsmSsh, "scope org", self.fiHostName)
        time.sleep(1)
        cli_with_ret(pFi.ucsmSsh, 'create local-disk-config-policy ' + self.spName, self.fiHostName)
        time.sleep(1)

        stat = sendUcsmBatchCmd(pFi, ['top','scope org', 'create local-disk-config-policy' + self.spName, \
            'set flexflash-state disable','set flexflash-raid-reporting-state disable', 'commit']) 
    
        self.localDiskPolName = self.spName
        return SUCCESS

    # Given service-profile name, deletes local disk configuration policy.
    # pSsh      - ssh handle to ucsm
    # return     - SUCCESS if setting is OK, EXIT_ERR if error.

    def deleteLocalDiskConfigPol(self, pFi):
        debug = 0
        debugL2 = 0

        if self.spName == None:
            printErr("spName for sp is not set, trying to set now:")
            return EXIT_ERR

        printDbg("Entry: " + self.spName, debug)

        if pFi.ucsmSsh == None:
            print "error: UCSM ssh is not initialized"
            return EXIT_ERR

        stat = sendUcsmBatchCmd(pFi, ['top','scope org', 'del local-disk-config-policy ' + self.spName, \
            'commit'])

        self.localDiskPolName = self.spName
        return SUCCESS


    # Temporary wrapper function for calling setSolPolicy, until all scripts use setSolPolicy.
    # input:
    # - pSsh - ucsmSsh, not used.
    # - pFi - FI instance.      
    # return:
    # - SUCCESS on setting SOL policy, EXIT_ERR on any failure.
       
    def setSol(self, pSsh, pFi = None):        
        if pFi == None:
            printWarn("!!! setSol is obsolete. Modify you caller script to use setSolPolicy() function. Can not set SOL.")
            printWarn("!!! or call this function with setSol(pSsh, pFi) convention!!!")
            return EXIT_ERR
        else:
            return self.setSolPolicy(pFi)

    # Given service-profile name, create sol/ipmi-profile policy with the same name as service-profile and assign$
    # input:
    # - pSsh - ssh handle to ucsm
    # return:
    # - SUCCESS if setting is OK, EXIT_ERR if error.

    def setSolPolicy(self, pFi):
        debug = 0
        debugL2 = 0
    
        if self.spName == None:
            printErr("spName for sp is not set, trying to set now:")
            return EXIT_ERR

        if validateFcnInput([pFi, pFi.ucsmSsh]) == EXIT_ERR:
            printErr("Error on input validation.")
            return EXIT_ERR

        statNoSolInit = getGlobalTmp("no-sol-init")

        if statNoSolInit:
            if re.search("yes", str(statNoSolInit)):
                printDbg("FI(2): no-sol-init specified, skipping SOL initialization.")
                return SUCCESS

        # Create ipmi access profile.

        printDbg("Creating ipmi-access-profile")
        stat = sendUcsmBatchCmd(pFi, ['top','scope org', 'create ipmi-access-profile ' + self.spName])

        if not re.search("Error: Managed object already exists", str(stat)):
            stat = sendUcsmBatchCmd(pFi, ['commit'])
        elif re.search("Invalid Value", stat):
            printErr("Invalid value for name: " + str(self.spName) + ". Check for name, max len=16")
            return EXIT_ERR
        else:
            stat = sendUcsmBatchCmd(pFi, ['scope ipmi-access-profile ' + self.spName])
    
        printDbg("Creating ipmi-user: " + self.spName, debug)

        stat = sendUcsmBatchCmd(pFi, ['create ipmi-user admin'])

        if not re.search("Error: Managed object already exists", str(stat)):
            stat = sendUcsmBatchCmd(pFi, ['commit'])
        else:
            stat = sendUcsmBatchCmd(pFi, ['scope ipmi-user admin'])

        stat = sendUcsmBatchCmd(pFi, ['set privilege admin', 'commit'])
    
        printDbg("Setting up ipmi-user pw...", debug)
    
        pFi.ucsmSsh.sendline("set password")
        time.sleep(1)
        #pSsh.expect("password:")
        pFi.ucsmSsh.sendline("Nbv12345")
        time.sleep(1)
        #pSsh.expect("password")
        cli_with_ret(pFi.ucsmSsh, 'Nbv12345', self.fiHostName)
        time.sleep(1)
        cli_with_ret(pFi.ucsmSsh, 'commit', self.fiHostName)
        time.sleep(1)
    
        printDbg("Finished creating ipmi-profile", debug)
    
        # Set ipmi-access profile to service-profile

        stat = sendUcsmBatchCmd(pFi, ['top', 'scope org', 'scope service-profile ' + self.spName, \
            'set ipmi-access-profile ' + self.spName, 'commit'])
    
        printDbg("Finished assigning ipmi-profile, creating SOL policy", debug)
    
        # Create SOL policy and attach to service-profile
    
        stat = sendUcsmBatchCmd(pFi, ['top', 'scope org', 'create sol-policy ' + self.spName])

        if not re.search("Error: Managed object already exists", str(stat)):
            stat = sendUcsmBatchCmd(pFi, ['set speed 115200', 'enable', 'commit'])
        else:
            stat = sendUcsmBatchCmd(pFi, ['scope sol-policy ' + self.spName])

        stat = sendUcsmBatchCmd(pFi, ['top', 'scope org', 'scope service-profile ' + self.spName, \
            'set sol-policy ' + self.spName, 'commit'])

        printDbg("Finished setting sol-policy, creating bios-policy", debug)

        # In bios policy enable console redirection and enable baud-rate to 115200

        printDbg("setting bios-policy SOL settings...", debug)

        stat = sendUcsmBatchCmd(pFi, ['top', 'scope org', 'create bios-policy ' + self.spName])

        if not re.search("Error: Managed object already exists", str(stat)):
            stat = sendUcsmBatchCmd(pFi, ['commit'])
        else:
            stat = sendUcsmBatchCmd(pFi, ['scope bios-policy ' + self.spName])

        stat = sendUcsmBatchCmd(pFi, ['set console-redir-config console-redir enable', \
            'set console-redir-config baud-rate 115200', 'commit'])

        stat = sendUcsmBatchCmd(pFi, ['top', 'scope org', 'scope service-profile ' + self.spName, \
            'set bios-policy ' + self.spName, 'commit'])

        stat = cli_with_ret(pFi.ucsmSsh, "commit", self.fiHostName)
        time.sleep(1)

        # by this time, management ip should work"

        self.ipmiProfileName = self.spName
        self.solPolicyName = self.spName
        return SUCCESS

    # Create and assign to service-profile a firmware host policy. Its name is same as spName.
    # input:
    # - pSsh - ssh handle to ucsm
    # return:
    # - EXIT_ERR if error setting the host fw policy
    # - SUCCESS if set the host fw policy correctly. 
        
    def setHostFwPolicy(self, pSsh):
        debug = 0

        if self.spName == None:
            printErr("spName is not set.")
            return EXIT_ERR

        cli_with_ret(pSsh, 'scope org', self.fiHostName)
        time.sleep(1)
        cli_with_ret(pSsh, 'create fw-host-pack ' + self.spName, self.fiHostName)
        time.sleep(1)
        cli_with_ret(pSsh, 'commit', self.fiHostName)
        time.sleep(1)
        cli_with_ret(pSsh, 'scope org', self.fiHostName)
        time.sleep(1)
        cli_with_ret(pSsh, 'scope service-profile ' + self.spName, self.fiHostName)
        time.sleep(1)
        cli_with_ret(pSsh, 'set host-fw-policy ' + self.spName, self.fiHostName)
        time.sleep(1)
        cli_with_ret(pSsh, 'commit', self.fiHostName)
        time.sleep(1)

        self.hostFwPolicy = self.spName
        return SUCCESS
    
    # Create and assign to service-profile a new boot-policy.
    # input:
    # - pFi - UCS object. 
    # - pBootPolicyName - name of the boot-policy, if none, then by default service-profile name is used.
    # - pVnicName - name of the vnic to added to service-profile.
    # return:
    # - EXIT_ERR if error setting boot-policy.
    # - SUCCESS if successfully set the boot-policy.
    
    def setBootPolicy(self, pFi, pBootPolicyName=None, pVnicName=None):
        debug = 0
        stat = 0

        if validateFcnInput([pFi, pFi.mSp]) == EXIT_ERR:
            printErr("Error with input.")
            return EXIT_ERR

        if pBootPolicyName == None:
            self.bootPolicyName = self.spName
        else:
            self.bootPolicyName = pBootPolicyName

        if self.spName == None:
            printErr("spName is not set.")
            return EXIT_ERR

        cli_with_ret(pFi.ucsmSsh, 'scope org', pFi.mSp.fiHostName)
        time.sleep(1)
        stat = cli_with_ret(pFi.ucsmSsh, 'create boot-policy ' + self.bootPolicyName, pFi.mSp.fiHostName)

        if re.search("Error: Managed object already exists", str(stat)):
            printWarn("boot-policy " + self.bootPolicyName + " already exists.")
        else:
            stat = sendUcsmBatchCmd(pFi, ['set boot-mode uefi', 'create lan', 'set order 3', 'create path primary',\
                'commit'])

            if pVnicName:
                cli_with_ret(pFi.ucsmSsh, 'set vnic ' + str(pVnicName) , pFi.mSp.fiHostName)
            else:
                cli_with_ret(pFi.ucsmSsh, 'set vnic eth0' , pFi.mSp.fiHostName)
            time.sleep(1)

            stat = sendUcsmBatchCmd(pFi, ['exit', 'exit', 'create virtual-media read-only', 'set order 2',\
                'exit', 'create storage', 'create local', 'create local-any', 'exit', 'exit', 'set order 1',\
                'exit', 'commit'])

        stat = sendUcsmBatchCmd(pFi, ['scope org', 'scope service-profile ' + self.spName,\
            'set boot-policy ' + self.bootPolicyName, 'commit'])

        self.bootPolicy = self.spName
        return SUCCESS
    
    # Create and assign to service-profile a new bios-policy
    # input:
    # - pSsh - ucsm handle.
    # - pBiosPolicyName - name of bios-policy.
    # return:
    # -EXIT_ERR if fails to set the bios-policy.
    # - SUCCESS if sets the bios-policy correctly. 

    def setBiosPolicy(self, pSsh, pBiosPolicyName = None):
        debug = 0

        if self.spName == None:
            printErr("spName is not set.")
            return EXIT_ERR

        cli_with_ret(pSsh, 'scope org', self.fiHostName)
        time.sleep(1)
        cli_with_ret(pSsh, 'create bios-policy ' + self.spName, self.fiHostName)
        time.sleep(1)
        cli_with_ret(pSsh, 'scope org', self.fiHostName)
        time.sleep(1)
        cli_with_ret(pSsh, 'scope service-profile ' + self.spName, self.fiHostName)
        time.sleep(1)
        
        if pBiosPolicyName == None:
            cli_with_ret(pSsh, 'set bios-policy ' + self.spName, self.fiHostName)
        else:
            cli_with_ret(pSsh, 'set bios-policy ' + str(pBiosPolicyName), self.fiHostName)
    
        time.sleep(1)
        cli_with_ret(pSsh, 'commit', self.fiHostName)
        time.sleep(1)
        self.biosPolicy = self.spName

        return SUCCESS

    # This function will delete service-profile. 
    # If sol policy is associated with the service-profile, then the sp.spName must be set, and same sol name must be assoc-d and 
    # then it will deleted.
    # If sol policy is not associated with the service-profile, the name must be passed to this function as a parameter.
    # input:
    # - pSsh - ssh console to ucsm.
    # - pSpName - name of service-profile
    # return:
    # - EXIT_ERR if any error condition.
    # - SUCCESS if deleted the sp successfully.

    def delSp(self, pSsh, pSpName = None):
        debug = 0

        printDbg("Entered: ", debug)

        if self.spName == None and pSpName == None:
            printErr("Neither spName is not set and pSolPolicyName is passed.")
            return EXIT_ERR

        cli_with_ret(pSsh, 'scope org', self.fiHostName)
        time.sleep(1)
        cli_with_ret(pSsh, 'delete service-profile ' + self.spName, self.fiHostName)
        time.sleep(1)
        cli_with_ret(pSsh, 'commit', self.fiHostName)
        time.sleep(1)
        
        self.spName = None
        return SUCCESS

    # This function will delete sol policy associated with the service-profile. 
    # If sol policy is associated with the service-profile, then the sp.spName must be set, and same sol name must be assoc-d and 
    # then it will deleted.
    # If sol policy is not associated with the service-profile, the name must be passed to this function as a parameter.
    # input:
    # - pSsh - ssh connection to ucsm
    # - pSolPolicyName - sol policy name to be deleted
    # return:
    # - EXIT_ERR if error deleting the sol policy
    # - SUCCESS if successfully deletes the sol policy
    
    def delSolPolicy(self, pSsh, pSolPolicyName = None):
        debug = 0

        printDbg("Entered: ", debug)

        if pSolPolicyName == None:
                pSolPolicyName = self.spName

        if self.spName == None and pSolPolicyName == None:
            printErr("Neither spName is not set and pSolPolicyName is passed.")
            return EXIT_ERR
     
        cli_with_ret(pSsh, 'scope org', self.fiHostName)
        time.sleep(1)
        cli_with_ret(pSsh, 'delete sol-policy ' + pSolPolicyName, self.fiHostName)
        time.sleep(1)
        cli_with_ret(pSsh, 'commit', self.fiHostName)
        time.sleep(1)

        self.solPolicy = None
        return SUCCESS
    
    # This function will delete the host firmware policy.
    # If host fw policy is associated with the service-profile, then the sp.spName must be set, and same host fw pol name must be assoc-d and 
    # then it will deleted.
    # If host fw policy is not associated with the service-profile, the name must be passed to this function as a parameter.
    # input:
    # - pSsh - ssh connection to ucsm
    # - pHostFwPolicyName  - name of host fw policy to delete
    # return:
    # - EXIT_ERR if fail or any error condition
    # - SUCCESS if successfully deletes the host fw policy
    
    def delHostFwPolicy(self, pSsh, pHostFwPolicyName = None):
        debug = 0

        printDbg("Entered: ", debug)

        if pHostFwPolicyName == None:
                pHostFwPolicyName = self.spName

        if self.spName == None and pHostFwPolicyName == None:
            printErr("sp.delHostFwPolicy: error: Neither spName is not set and pHostFwPolicyName is passed.")
            return EXIT_ERR

        cli_with_ret(pSsh, 'scope org', self.fiHostName)
        time.sleep(1)
        cli_with_ret(pSsh, 'delete fw-host-pack ' + pHostFwPolicyName, self.fiHostName)
        time.sleep(1)
        cli_with_ret(pSsh, 'commit', self.fiHostName)
        time.sleep(1)

        self.hostFwPolicy = None
        return SUCCESS

    # This function will delete the boot policy.
    # If boot policy is associated with the service-profile, then the sp.spName must be set, and same sol name must be assoc-d and 
    # then it will deleted.
    # If boot policy is not associated with the service-profile, the name must be passed to this function as a parameter.
    # input:
    # - pSsh - ssh connection to ucsm
    # - pBootPolicyName - boot policy name to be deleted
    # return:
    # - EXIT_ERR if any error condition
    # - SUCCESS if successfully deletes the boot policy name
    
    def delBootPolicy(self, pFi, pBootPolicyName = None):
        debug = 0

        if validateFcnInput([pFi]) == EXIT_ERR:
            printErr("Error with input.")
            return EXIT_ERR

        printDbg("Entered: ", debug)

        if pBootPolicyName == None:
            if self.spName:
                printDbg("pBootPolicyName is none. Setting to : " + str(self.spName))
                pBootPolicyName = self.spName
            else:
                printErr("pBootPolicyName is none and self.spName is also none. Unable to determine the boot-policy to be deleted.")
                return EXIT_ERR

        stat = sendUcsmBatchCmd(pFi, ['scope org','delete boot-policy ' + str(pBootPolicyName),\
            'commit'])
    
        self.bootPolicy = None
    
    # This function will delete the bios policy.
    # If bios policy is associated with the service-profile, then the sp.spName must be set, and same sol name must be assoc-d and 
    # then it will deleted.
    # If bios policy is not associated with the service-profile, the name must be passed to this function as a parameter.
    # input:
    # - pSsh - ssh connection to ucsm
    # - pBiosPolicyName - bios policy name to be deleted
    # return:
    # - EXIT_ERR if any error condition
    # - SUCCESS if successfully deletes the bios policy

    def delBiosPolicy(self, pSsh, pBiosPolicyName = None):
        debug = 0

        printDbg("sp.delBiosPolicy: entry", debug)

        if pBiosPolicyName == None:
                pBiosPolicyName = self.spName

        if self.spName == None and pBiosPolicyName == None:
            return EXIT_ERR
            printDbg("sp.delBiosPolicy: error: Neither spName is not set and pBiosPolicyName is passed.")

        if self.spName == "SRIOV":
            print "SRIOV is a built-in bios-policy, it can not be deleted. skipping..."
            return EXIT_ERR

        cli_with_ret(pSsh, 'scope org ', self.fiHostName)
        time.sleep(1)
        cli_with_ret(pSsh, 'delete bios-policy ' + pBiosPolicyName, self.fiHostName)
        time.sleep(1)
        cli_with_ret(pSsh, 'commit', self.fiHostName)
        time.sleep(1)

        self.biosPolicy = None
        return SUCCESS
    
    # This function will delete the bios policy.
    # If ipmi profile is associated with the service-profile, then the sp.spName must be set, and same sol name must be assoc-d and 
    # then it will deleted.
    # If ipmi profile is not associated with the service-profile, the name must be passed to this function as a parameter.
    # input:
    # - pSsh - ssh conection to ucsm
    # - pIpmiProfileName - ipmi profile name to be deleted.
    # return:
    # - EXIT_ERR - if any error condition
    # - SUCCESS - if successfully deletes the ipmi - profile

    def delIpmiProfile(self, pSsh, pIpmiProfileName):
        debug = 0

        printDbg("Entered: ", debug)

        if pIpmiProfileName == None:
                pBiosIpmiProfileName = self.spName

        if self.spName == None and pIpmiProfileName == None:
            printErr("Neither spName is not set and pBiosPolicyName is passed.")
            return EXIT_ERR

        cli_with_ret(pSsh, 'scope org ', self.fiHostName)
        time.sleep(1)
        cli_with_ret(pSsh, 'delete ipmi-access-profile ' + pIpmiProfileName, self.fiHostName)
        time.sleep(1)
        cli_with_ret(pSsh, 'commit', self.fiHostName)
        time.sleep(1)

        self.ipmiProfile = None
        return SUCCESS

#   Fabric interconnect/ucsm class. Any definition/methods and constant and variables related 
#   to FI goes here.

class fi:
    classString = "fi class instance info:"
    mgmtIp = None
    mgmtIpA = None
    mgmtIpA = None

    cmcIpA = None
    cmcIpB = None
    
    ucsmSsh = None
    mSp = None
    versionUcsm = None
    versionFiA = None
    versionFiB = None
    statFastInit = None

    # HostnameBase holds the hostname without its suffix -A or -B. i.e. if FI has two Fabric
    # PCIE-A and PCIE-B then hostNameBase will be PCIE.
    # Hostname will initially is same as hostnameBase but after login first command execution, the code 
    # will find the lead switch and will set the hostname suffix to either A or B. 
    # This way the hostName will update to either <hostName-A> or <hostName-B>. hostName is used in 
    # many functions and places throughout this suite, specially when sending the command to UCSM 
    # through cli and it is essential for recognizing the pattern recognition when interating with
    # UCSM cli through pexpect module.

    hostName = None
    hostNameBase = None
    debug = 0
    password = "Nbv12345"
    user = "admin"

    # Initialize the FI instance. This is all one when class object is instantiated.

    def __init__(self, pMgmtIp = None, pBladeLoc = None, pSpName = None):
        debug = 0
        printDbg("fi.__init__", self.debug)
        self.mgmtIp = pMgmtIp        

        ucsmSsh = None
        stat = None

        printDbg("fi:__init__ param-s: (pMgmtIp, pBladeLoc, pSpName)", debug)
        print pMgmtIp, pBladeLoc, pSpName

        # create sp instance which in turns creates blade instance.

        printDbg("Creating fi.mSp.")

        self.mSp = sp(pBladeLoc, pSpName)

        try:
            self.mSp.mBlade.fiHostName = self.hostName
        except Exception as msg:
            printWarn("Blade object is not created. Will not set hostname.")

        if debug:
            try:
                printDic(self.mSp)
                printDic(self.mSp.mBlade)
            except AttributeError:
                printWarn("Can not print debug message: mSp, mSp.mBlade instances.")

        # setFi - determine the hostname and other optional information.

        if setFi(self) == EXIT_ERR:
            printErr("Unable to find test bed info.")
            return EXIT_ERR

        self.ucsmSsh = sshLogin(self.mgmtIp, self.user, self.password)

        if self.ucsmSsh == EXIT_ERR:
            printErr("Unable to login to UCSM.")
            return EXIT_ERR
        else:
            printDbg("Connected to UCSM ssh console...OK.", debug)

        # Set hostName based on whether A or B is lead switch, by trying to login and execute the command

        stat = cli_with_ret(self.ucsmSsh, "show ver", self.hostName + "-A", 'ucsmCli', 1)
    
        if stat:
            printDbg("Setting hostname to suffix to A")
            self.hostName = self.hostName + "-A"
            self.mSp.fiHostName = self.hostName

            stat = cli_with_ret(self.ucsmSsh, "terminal session-timeout 0", self.hostName)
            time.sleep(1)
            stat = cli_with_ret(self.ucsmSsh, "show cli session-config | grep Timeout", self.hostName)
            time.sleep(1)

            printDbg("Session timeout: " + str(stat), debug)

            try:
                self.mSp.mBlade.fiHostName = self.hostName
            except Exception as msg:
                printWarn("Blade object is not created. Will not set hostname.")

            # If fast initialization flag is set in the global tmp file, then skip the version determination.
            
            statFastInit = getGlobalTmp("fast-init")
    
            if statFastInit:
                if re.search("yes", str(statFastInit)):
                    printDbg("FI(2): fast-init specified, skipping version.")
            else:
                if re.search("yes", str(statFastInit)):
                    printDbg("FI(2): fast-init specified, skipping version.")
                else:
                    try:
                        stat = sendUcsmBatchCmd(self, ['top','show version'])        
                        printDbg("show version output: " + str(stat), debug)
                        statKernelFiA = sendUcsmBatchCmd(self, ['top','scope fabric-interconnect A','show version | grep Running-Kern-Vers'])        
                        printDbg("show version FI A kernel output: " + str(statKernelFiA), debug)
                        statSystemFiA = sendUcsmBatchCmd(self, ['top','scope fabric-interconnect A','show version | grep Running-Sys-Vers'])        
                        printDbg("show version FI A system output: " + str(statSystemFiA), debug)
        
                        self.versionUcsm = stat.split(':')[-1].strip()
                        self.versionKernelFiA = statKernelFiA.split(':')[-1].strip()
                        self.versionSystemFiA = statSystemFiA.split(':')[-1].strip()
        
                        printInfoToFile("UCSM version:      " + str(self.versionUcsm), debug)
                        printInfoToFile("Ks/System version: " + str(self.versionKernelFiA) + ", " + str(self.versionSystemFiA), debug)
    
                    except Exception as msg:
                        printWarn("Unable to determine UCSM/FI version and/or error parsing the version string(FI-A).")
                        print msg

            if debug:
                printDic(self)

            return None

        printDbg("Switch A failed. Trying switch B")

        self.ucsmSsh.close()
        self.ucsmSsh = sshLogin(self.mgmtIp, self.user, self.password)

        if self.ucsmSsh == EXIT_ERR:
            printErr("Unable to login to UCSM.")
            return EXIT_ERR
        else:
            printDbg("Connected to UCSM ssh console...OK(1)", debug)
    
        stat = cli_with_ret(self.ucsmSsh, "show ver", self.hostName + "-B", 'ucsmCli', 1)
    
        if stat:
            printDbg("setting hostname to suffix to B")
            self.hostName = self.hostName + "-B"
            self.mSp.fiHostName = self.hostName

            stat = cli_with_ret(self.ucsmSsh, "terminal session-timeout 0", self.hostName)
            time.sleep(1)
            stat = cli_with_ret(self.ucsmSsh, "show cli session-config | grep Timeout", self.hostName)
            time.sleep(1)
            printDbg("session timeout: " + str(stat), debug)

            try:
                self.mSp.mBlade.fiHostName = self.hostName
            except AttributeError:
                printWarn("Did not set the blade hostname from FI hostname as blade instance is not known.")

            # If fast initialization flag is set in the global tmp file, then skip the version determination.
            
            statFastInit = getGlobalTmp("fast-init")
    
            if statFastInit:
                if re.search("yes", str(statFastInit)):
                    printDbg("FI(2): fast-init specified, skipping version.")
            else:
                if re.search("yes", str(statFastInit)):
                    printDbg("FI(2): fast-init specified, skipping version.")
                else:
                    try:
                        stat = sendUcsmBatchCmd(self, ['top','show version'])        
                        statKernelFiB = sendUcsmBatchCmd(self, ['top','scope fabric-interconnect B','show version | grep Running-Kern-Vers'])        
                        printDbg("show version FI B kernel output: " + str(statKernelFiB), debug)
                        statSystemFiB = sendUcsmBatchCmd(self, ['top','scope fabric-interconnect B','show version | grep Running-Sys-Vers'])        
                        printDbg("show version FI A system output: " + str(statSystemFiB), debug)

                        self.versionUcsm = stat.split(':')[-1].strip()
                        self.versionKernelFiB = statKernelFiB.split(':')[-1].strip()
                        self.versionSystemFiB = statSystemFiB.split(':')[-1].strip()
                        printInfoToFile("UCSM version: " + str(self.versionUcsm))
                        printInfoToFile("UCSM version:      " + str(self.versionUcsm), debug)
                        printInfoToFile("Ks/System version: " + str(self.versionKernelFiB) + ", " + str(self.versionSystemFiB), debug)
                    except Exception as msg:
                        printWarn("Unable to determine UCSM/FI version and/or error parsing the version string(FI-B).")
            if debug:
                printDic(self)
            return None

        printErr("both A and B switch did not work. This switch may not be usable: "  + str(self.mgmtIp) + " : " + str(self.hostNameBase))
        return None

    #   Displays information about the class instance.
    #   return -    None

    def disp(self):
        print "instance info:"

        for i in self.__dict__:
            print i

    # Simplified interface for downloading the firmware from external server to FI. This is different than copying the 
    # from worksplace scope. Rather it uses the firmware copy commands from firmware scope of FI.
    # input:
    # - pExpIp - External IP of server from which the firmware is downloaded from.
    # - pProtocol - protocol used in downloading.
    # - pImageFileName - name of the image file to be downloaded.
    # - pExpPath - relative path of the image on pExpIp.
    # - pWait - 1: wait until download is finished or until it fails/timeout.
    #           0 or None: do not wait until download is finished, in case if failure it does not check either.
    # return:
    # - SUCCESS - if download is successful.
    #   EXTI_ERR - on any error.

    def copyFwToFi(self, pExtIp, pExpPath, pImageFileName, pProtocol="FW_DW_PROTOCOL_SCP",  pWait = 1):
        debug = 0
        protocol = None

        # Validate inputs.

        if validateFcnInput([pExtIp, pImageFileName, pProtocol]) == EXIT_ERR:
            printErr("Error with input.")
            return EXIT_ERR

        if validateIp(pExtIp) == EXIT_ERR:
            printErr("Invalid IP address: " + str(pExpIp))
            return EXIT_ERR

        if not self.ucsmSsh:
            printErr("No ssh connection to UCSM")
            return EXIT_ERR

        if not pProtocol in fwDwProtocols:
            printErr("Unsupported protocol: " + str(pProtocol))
            printErr("Supported protocols: ")
            printSeq(fwDwProtocols)
            return EXIT_ERR

        if pProtocol == "FW_DW_PROTOCOL_TFTP":
            protocol = 'tftp'

        if pExpPath == None:
            pExpPath = ""

        stat = sendUcsmBatchCmd(self, ['top','scope firmware', 'show package | grep ' + str(pImageFileName)])
        printDbg("show package output:" + str(stat), debug)

        if stat.strip():
            if re.search(pImageFileName, str(stat)):
                printDbg("Image " + str(pImageFileName) + " is already on the FI. Skipping download")
                return SUCCESS
        else:
            printDbg("Image does not appears to be on FI. Downloading...")

        time.sleep(5)
        printDbg("Deleting existing download task for " + str(pImageFileName))
        stat = sendUcsmBatchCmd(self, ['top','scope firmware','delete download-task ' + str(pImageFileName)])

        if stat == EXIT_ERR:    
            printErr("Error sending delete download task command.")
            print stat
            return EXIT_ERR

        printDbg("stat:")
        counter = 0 
        CONFIG_FW_DW_TIMEOUT = 600
        CONFIG_FW_DW_WAIT_INTERVAL = 15

        printDbg("Starting download\n")

        stat = sendUcsmBatchCmd(self, ['top','scope firmware',\
            'download image ' + str(protocol) + '://' + str(pExtIp) + '/' + str(pExpPath) + '/' + str(pImageFileName)])

        while not re.search("Downloaded", stat, re.MULTILINE):
    
            if stat == EXIT_ERR:    
                printErr("Error sending download command.")
                print stat
                return EXIT_ERR
    
            stat = sendUcsmBatchCmd(self, ['top','scope firmware','show download-task | begin ' + str(pImageFileName) + ' | head lines 2 | grep Tftp'])

            if re.search("Failed", stat, re.IGNORECASE):
                printErr("Download is unsuccessful, failed.")
                stat1 = sendUcsmBatchCmd(self, ['top','scope firmware','scope download-task ' + str(pImageFileName), 'show fsm status expand detail | egrep \"Error Description\"'])
                printErr("Fail reason: " + str(stat1))
                return EXIT_ERR

            if debug:
                printDbg("stat:")
                printPexBa(self.ucsmSsh, stat)

            time.sleep(CONFIG_FW_DW_WAIT_INTERVAL)
            counter += CONFIG_FW_DW_WAIT_INTERVAL
            printNnl(" " + str(counter))
            printDbg(" " + str(counter), debug)
    
            if counter > CONFIG_FW_DW_TIMEOUT:
                printErr("Timeout reached waiting for download to finish. Download problem or consider extending the timeout for large file.")
                printErr("Current download status: " + str(stat))
                return EXIT_ERR
        
        return SUCCESS

    # This function attemps to get DHCP IP from CMC console. 
    # If IP address is already assigned, it will simply quit with SUCCESS.
    # Note: this has not been tested well and could be broken.
    # req:      
    # - cmcIpA or cmcIpB telnet access info must be populated in the FI list ilfe in order use it.
    # - cmc that are being accessed must have serial console access that matches the entry in the FI list file.
    # input:    
    # - pForce      - 1 force reset telnet server corresponding line if access denied, 0 - do not force reset.
    # - pInternal   - 1 use internal 127.3.0.254/127.4.0.254 instead of serial server
    # return:
    # - IP string of DHCP IP  if CMCA or CMCB can get lease.
    #   NO_EXIT_ERR if lease obtained but can not extract DHCP IP string.
    #   EXIT_ERR, fail if none of are able to get DHCP IP.

    def cmcGetDhcpIp(self, pForce=0, pInternal=0):
        debug = 0
        debugL2 = 0
        ret1 = None
        cmcIp = None

        # iterate over A and B

        for i in range(0, 2):

            if i == 0:
                printDbg("trying CMC A:", debug)

                if pInternal:
                    cmcIp = "127.3.0.254"
                    cmcPort = "23"
                else:
                    cmcIp = self.cmcIpA
    
            if i == 1:
                printDbg("trying CMC B:", debug)

                if pInternal:
                    cmcIp = "127.4.0.254"
                    cmcPort = "23"
                else:
                    cmcIp = self.cmcIpB

            if cmcIp == "-" or cmcIp == None:
                printErr("CMC telnet info is not available")
                return EXIT_ERR
            else:

                # validate CMC IP read from FI list file. 
                
                if pInternal == 0:
                    if not re.search(".*:[0-9]*", cmcIp.strip()):
                        printErr("must be in <IP>:<Port> format")
                        return EXIT_ERR
        
                    if validateIp(cmcIp.strip().split('/')[0]) == EXIT_ERR:
                        printErr("must be in <IP>:<Port> format")
                        return EXIT_ERR
                        
                    cmcPort = cmcIp.strip().split(':')[1]
                    cmcIp = cmcIp.strip().split(':')[0]
    
                    # if force specified                
    
                    if pForce:
    
                        print "clearing the line from serial server " + cmcIp
    
                        ssTelnet = telnetLogin(cmcIp, 23, 'admin', 'nbv12345', 10)
        
                        if ssTelnet == EXIT_ERR:
                            printErr("telnet login to serial server " + cmcIp + ":23  failed.")
                            return EXIT_ERR
                        
                        ret1 = cli_with_ret(ssTelnet, "enable", "Password:", "linuxShell")
                        printDbg(ret1, debug)
                        ret1 = cli_with_ret(ssTelnet, "clear line " + str(cmcPort)[2:], "[confirm]", "linuxShell")    
                        printDbg(ret1, debug)
                        ret1 = cli_with_ret(ssTelnet, "\r", "[OK]", "linuxShell")
                        printDbg(ret1, debug)
        
                        print "done clearing line. Closing."
        
                        print "closing telnet....."            
                        ssTelnet.close() 
    
                # establish telnet communicatin.

                cmcTelnet = telnetLogin(cmcIp, cmcPort, 'root', 'cmc', 10)
    
                if cmcTelnet == EXIT_ERR:
                    printErr("telnet login to CMC " + cmcIp + ":" + cmcPort + " failed.")

                    if cmcTelnet:
                        print "closing telnet....."            
                        cmcTelnet.close()
                
                    return EXIT_ERR

                # first check if IP is already assigned if so, leave it.
        
                ret1 = cli_with_ret(cmcTelnet, "ifconfig | grep 10\.193\.", "cmc.*#", "linuxShell")  
                time.sleep(1)
                printDbg("ret1: " + str(ret1), debug)

                if re.search("[0-9]*\.[0-9]*\.[0-9]*\.[0-9]* ", ret1):
                    print "This IOM has already has 10.193.x.x IP address assigned"
                    print "IP address: " + str(ret1.strip().split()[1].split(':')[1])

                    if cmcTelnet:
                        print "closing telnet....."            
                        cmcTelnet.close()
                        return ret1.strip().split()[1].split(':')[1]
                else:
                    print "CMC does not have IP assigned, attempting to assign. "
                
                ret1 = cli_with_ret(cmcTelnet, "cms -c altproduction,pfw=bmcdbg", "cmc.*#", "linuxShell")  
                time.sleep(1)
                ret1 = cli_with_ret(cmcTelnet,"cms dbgon", "cmc.*#", "linuxShell")  
                time.sleep(1)
                ret1 = cli_with_ret(cmcTelnet,"/etc/init.d/iptables stop", "cmc.*#", "linuxShell")  
                time.sleep(1)

                for i in range(0, 2):
                    ret1 = cli_with_ret(cmcTelnet, "/usr/bin/getip.sh " + str(i), "cmc.*#", "linuxShell")  
                
                    if re.search("No lease, forking to background", str(ret1)):
                        printDbg("Warning getip " + str(i) + " failed")
                    elif re.search("Lease of.*obtained", str(ret1)):
                        printDbg("Successfully obtained DHCP IP on CMC: " + cmcIp + ":" + cmcPort)
        
                        if validate(  str(ret1.strip().split()[1].split(':')[1]) ):

                            if cmcTelnet:
                                print "closing telnet....."            
                                cmcTelnet.close()

                            return ret1.strip().split()[1].split(':')[1]
                        else:
                            print "Warning: DHCP IP lease obtained but unable to validate the IP address."
                            return NO_EXIT_ERR

            # close this particular connection.

            print "closing telnet....."            
            cmcTelnet.close()

        printErr("Unable to get DHCP lease at all from this FI IOM. Giving up, check the connection. ")
        return EXIT_ERR

    # Note: This function will copy file to fabric interconnect in workspace directory. 
    # Once copied, the file can be accessible from local-mgmt scope. Many tests require file needs to be
    # placed onto /bootflash directory, however this file service does not place it in /bootflash location.
    # If particular file is needed to be placed onto /bootflash, call the cpFileToBootFlash function.

    # req:      
    # input:    
    # - pPath - full path of filename to be copied. If just a filename, assumes it is root directory.
    # Format and assumption of full path may depend on underlying protol. Therefore this parameter full
    # definition is TBD.
    # - pSrcIp - source IP from which to be copied from.
    # - pProtocol to be used:
    #   Currently, the supported protocols are: "scp"
    # - pDbgPath - full path of ucs debug plugin filename to be copied. If just a filename, assumes it is root directory.
    # Format and assumption of full path may depend on underlying protol. Therefore this parameter full
    # definition is TBD.
    #   For FILE_PROTOCOL_TFTP, pPath and pDbgPath must be a relative path to tftp root directory. <tftpRoot>a/b/c/<fileName>
    #   For FILE_PROTOCOL_SCP, pPath and pDbgPath must be a absolute path of the filename. /a/b/c/<fileName>
    #   Following values are for accepted:
    #   pDbgPath=None - this is the default value and tells the function not to copy debug plugin at all.
    #   pDbgPath=1 -  default path/IP/protocol values for pDbgPath/pDbgrcIp/pDbgProtocol must be defined in either generic configuration file or blade specific configuration file.
    #   pDbgPath=<full_path> User supplies parameter specifying full path for these parameters.
    # - pDbgSrcIp - source IP from which to be copied from.
    # - pDbgProtocol to be used:
    # - pUserName - username used for some protocol: FILE_PROTOCOL_SCP
    # - pPassword - password used for some protocol: FILE_PROTOCOL_SCP
    #   Currently, the supported protocols are: "scp"
    # return:
    # -  EXIT_ERR on any falure.
    #    SUCCESS on copy success.

    def cpFileToFi(self, pPath, pSrcIp = 1, pProtocol = 1, pDbgPath = 1, pDbgSrcIp = 1, pDbgProtocol = 1, pUserName = None, pPassword = None):
        stat = None
        debug = 0

        if validateFcnInput([pPath, pSrcIp, pProtocol]) == EXIT_ERR:
            printErr("Error with input.")
            return EXIT_ERR

        # Set default values if arguments are 1 for file being copied, otherwise leave it untouched.

        if pSrcIp == 1:
            printDbg("Default copy file source IP is set to: " + str(DEFAULT_FILE_COPY_SRC_IP), debug)
            pSrcIp = DEFAULT_FILE_COPY_SRC_IP
        else:
            printDbg("Copy file source IP is set to: " + str(pSrcIp), debug)

        if pProtocol == 1:
            printDbg("Default copy file protocol is set to: " + str(DEFAULT_FILE_COPY_PROTOCOL), debug)
            pProtocol = DEFAULT_DEBUG_PLUGIN_PROTOCOL
        else:
            printDbg("Copy file protocol is set to: " + str(pProtocol), debug)

        # Set default values if arguments are 1 for debug plugin being copied, otherwise leave it untouched.

        if pDbgPath == None:
            printDbg("Will not try copying the debug plugin.")
        else:
            if pDbgPath == 1:
                pDbgPath = DEFAULT_DEBUG_PLUGIN_FILE_NAME
                printDbg("Default plugin path is set to: " + str(DEFAULT_DEBUG_PLUGIN_FILE_NAME), debug)
            else:
                printDbg("Debug plugin path is set to: " + str(pDbgPath), debug)

            if pDbgSrcIp == 1:
                pDbgSrcIp = DEFAULT_DEBUG_PLUGIN_SRC_IP
                printDbg("Default plugin source IP is set to: " + str(DEFAULT_DEBUG_PLUGIN_SRC_IP), debug)
            else:
                printDbg("Debug plugin source IP is set to: " + str(pDbgSrcIp), debug)

            if pDbgProtocol == 1:
                pDbgProtocol = DEFAULT_DEBUG_PLUGIN_PROTOCOL
                printDbg("Default plugin copy protocol is set to: " + str(DEFAULT_DEBUG_PLUGIN_PROTOCOL), debug)
            else:
                printDbg("Debug plugin copy protocol is set to: " + str(pDbgProtocol), debug)

        # if protocols are not in supported protocol or not equal to 1 (default), exit with error.

        if not pProtocol in fileProtocols and pProtocol != 1:
            printErr(str(pProtocol) + " is not in supported protocol.")
            return EXIT_ERR

        if not pDbgProtocol in fileProtocols and pDbgProtocol != 1:
            printErr(str(pDbgProtocol) + " is not in supported protocol.")
            return EXIT_ERR

        # Handle the case of TFTP file transfer for debug plugin.

        # Determine the tftp server address. Will try to obtain the value from global config file: config.txt
        # if not defined there, will use hard-coded value defined in this function as a last resort.
    
        if pDbgPath == DEFAULT_DEBUG_PLUGIN_FILE_NAME:
            printDbg("Debug plugin to be copied with default options.")
            
            if pDbgProtocol == 'FILE_PROTOCOL_TFTP':
                printDbg("Using TFTP to copy.", debug)
                srcServerIp = DEFAULT_DEBUG_PLUGIN_SRC_IP
                ucsDebugPluginFileName = DEFAULT_DEBUG_PLUGIN_FILE_NAME
            
                # Login to FI and copy the BIOS and debug plugin file:
            
                ucsmSsh = sshLogin(self.mgmtIp, self.user, self.password)
            
                if ucsmSsh == None:
                    printErr("Unable to establish add'l session to UCSM.")
                    return EXIT_ERR
            
                # Connect to local-mgmt.
            
                printDbg("Connecting to local-mgmt")
                output1 = cli_with_ret(ucsmSsh, "connect local-mgmt", "")
            
                printDbg("output1:", debug)
                printDbg(output1)
            
                commandHints = [\
                "Copying UCS FI debug plugin " + str(ucsDebugPluginFileName) + " to /workspace" ,\
                "exit"\
                ]
            
                commandSets = [\
                "cp tftp://" + srcServerIp + "/" + ucsDebugPluginFileName + " /" + ucsDebugPluginFileName\
                ]
            
                errorTriggers = [\
                "File not found|timeout",\
                "command not found"
                ]
            
                errorMessages = [\
                "UCS FI debug plugin " + ucsDebugPluginFileName + " does not exist on TFTP server " + srcServerIp+ " or TFTP " +\
                "Failed to exit from local-mgmt"
                ]
            
                time.sleep(3)
            
                # Process all commands above.
            
                for i in range(0, len(commandSets)):
                    printBarDouble()
                    printDbg(commandHints[i])
                    time.sleep(3)
                    printDbg("FI command: " + str(commandSets[i]))
                    output1 = cli_with_ret(ucsmSsh, commandSets[i], "")

                    printBarSingle()
                    printDbg("1. index: " + str(i))
                    printDbg("Looking for error pattern: " + str(errorTriggers[i]) + "...")
                    printDbg("Will throw error message if failure: " + str(errorMessages[i]))
                    printDbg("output1: \n" + str(output1) + "\n")
            
                    if re.search(errorTriggers[i], output1):
                        printErr(errorMessages[i])
                        ucsmSsh.close()
                        return EXIT_ERR

                ucsmSsh.close()
            elif pDbgProtocol == 'FILE_PROTOCOL_SCP':
                printDbg("Using SCP to copy.", debug)
                # Login to FI and copy the BIOS and debug plugin file:
            
                ucsmSsh = sshLogin(self.mgmtIp, self.user, self.password)
            
                if ucsmSsh == None:
                    printErr("Unable to establish add'l session to UCSM.")
                    return EXIT_ERR
            
                # Connect to local-mgmt.
            
                printDbg("Connecting to local-mgmt")
                output1 = cli_with_ret(ucsmSsh, "connect local-mgmt", "")
            
                printDbg("output1:", debug)
                printDbg(output1)
            
                commandHints = [\
                "Copying UCS FI debug plugin " + str(ucsDebugPluginFileName) + " to /workspace" ,\
                "exit",\
                ]
            
                commandSets = [\
                "cp scp://" + pUserName + "@" + srcServerIp + ucsDebugPluginFileName + " .",\
                pPassword\
                ]
            
                errorTriggers = [\
                "Incomplete Command|Invalid Command",\
                "No such file or directory|Permission denied"
                ]
            
                errorMessages = [\
                "Problem with command syntax? " +\
                "Failed to copy file."
                ]
            
                time.sleep(3)
            
                # Process all commands above.
            
                for i in range(0, len(commandSets)):
                    printBarDouble()
                    printDbg(commandHints[i])
                    time.sleep(3)
                    printDbg("FI command: " + str(commandSets[i]))
                    output1 = cli_with_ret(ucsmSsh, commandSets[i], "")

                    printBarSingle()
                    printDbg("2. index: " + str(i))
                    printDbg("Looking for error pattern: " + str(errorTriggers[i]) + "...")
                    printDbg("Will throw error message if failure: " + str(errorMessages[i]))
                    printDbg("output1: \n" + str(output1) + "\n")
            
                    if re.search(errorTriggers[i], output1):
                        printErr(errorMessages[i])
                        ucsmSsh.close()
                        return EXIT_ERR

                ucsmSsh.close()
            else:
                printErr("Unsupported or currently unimplemented protocol for default debug plugin copy to FI." + str())
                return EXIT_ERR

        # Handle the case of SCP for actual file transfer 
        # Determine the tftp server address. Will try to obtain the value from global config file: config.txt
        # if not defined there, will use hard-coded value defined in this function as a last resort.

        srcServerIp = pSrcIp
        pFileName = pPath
        
        if pProtocol == 'FILE_PROTOCOL_TFTP':
            printDbg("Using TFTP to copy.", debug)
    
            # Determine the fabric interconnect debug plugin file name. Will try to obtain the value from global config file: config.txt
            # if not defined there, will use hard-coded value defined in this function as a last resort.
        
            # Login to FI and copy the BIOS and debug plugin file:
        
            ucsmSsh = sshLogin(self.mgmtIp, self.user, self.password)
        
            if ucsmSsh == None:
                printErr("unable to establish add'l session to UCSM.")
                return EXIT_ERR
        
            # Connect to local-mgmt.
        
            printDbg("connecting to local-mgmt")
            output1 = cli_with_ret(ucsmSsh, "connect local-mgmt", "")
        
            printDbg("output1:", debug)
            printDbg(output1)
        
            commandHints = [\
            "Copying file " + pFileName + " to /workspace" ,\
        
            "Copying UCS FI debug plugin to volatile:a",\
            "Loading UCS FI debug plugin from volatile:a",\
            "ls /bootflash/ to see UCS FI debug environment is entered.",\
        
            "copying /bootflash/" + pFileName + " to /bootflash",\
        
            "exit",\
            "exit",\
            ]
        
            commandSets = [\
            "cp tftp://" + srcServerIp + "/" + pFileName + " /" + pFileName,\
        
            "cp " + ucsDebugPluginFileName + " volatile:a",\
            "load volatile:a",\
            "ls /bootflash/",
        
            "cp /workspace/" + str(pFileName) + " /bootflash/",\
            ]
        
            errorTriggers = [\
            "File not found|timeout",\
        
            "cannot stat",\
            "Image doesn't exist|Digital signature verification failed.",\
            "bytes total",\
        
            "cannot stat",\
        
            "Invalid Command",\
            "command not found"
            ]
        
            errorMessages = [\
            pFileName + " does not exist on TFTP server " + srcServerIp + " or TFTP timeout due to wrong TFTP server.",\
        
            "UCS FI debug plugin " + ucsDebugPluginFileName + " is not on /workspace.",\
            "UCS FI debug plugin load from volatile:a failed.",\
            "ls /bootflash returns local-mgmt scope returns. Failed to enter debug plugin",\
        
            "For some reason, file " + pFileName + "is not on /workspace",\
        
            "Failed to exit from debug-plugin",\
            "Failed to exit from local-mgmt"
            ]
        
            time.sleep(3)
        
            # Process all commands above.
        
            for i in range(0, len(commandSets)):
                printBarDouble()
                printDbg(commandHints[i])
                time.sleep(3)

                printDbg("FI command: " + str(commandSets[i]))
                output1 = cli_with_ret(ucsmSsh, commandSets[i], "")

                printBarSingle()
                printDbg("3. index: " + str(i))
                printDbg("Looking for error pattern: " + str(errorTriggers[i]) + "...")
                printDbg("Will throw error message if failure: " + str(errorMessages[i]))
                printDbg("output1: \n" + str(output1) + "\n")
        
                if re.search(errorTriggers[i], output1):
                    printErr(errorMessages[i])
                    ucsmSsh.close()
                    return EXIT_ERR

            ucsmSsh.close()
            return SUCCESS

        elif pProtocol == 'FILE_PROTOCOL_SCP':
            printDbg("Using SCP to copy.", debug)

            # Login to FI and copy the BIOS and debug plugin file:
        
            ucsmSsh = sshLogin(self.mgmtIp, self.user, self.password)
        
            if ucsmSsh == None:
                printErr("Unable to establish add'l session to UCSM.")
                return EXIT_ERR
        
            # Connect to local-mgmt.
        
            printDbg("connecting to local-mgmt")
            output1 = cli_with_ret(ucsmSsh, "connect local-mgmt", "")
        
            printDbg("output1:", debug)
            printDbg(output1)
        
            commandHints = [\
            "Copying file " + pFileName + " to /workspace" ,\
        
            "Copying UCS FI debug plugin to volatile:a",\
            "Sending password",\
            "Loading UCS FI debug plugin from volatile:a",\
            "ls /bootflash/ to see UCS FI debug environment is entered.",\
        
            "copying /bootflash/" + pFileName + " to /bootflash",\
        
            "exit",\
            "exit",\
            ]

            expectPattern = [\
            "password:",\
            "",\
            "", "", "", ""\
            ]
        
            commandSets = [\
            "cp scp://" + pUserName + "@" + srcServerIp + pFileName + " .",\
            pPassword,\
        
            "cp " + ucsDebugPluginFileName + " volatile:a",\
            "load volatile:a",\
            "ls /bootflash/",
        
            "cp /workspace/" + str(pFileName) + " /bootflash/",\
            ]
        
            errorTriggers = [\
            "#File not found|timeout",\
            "Incomplete Command|Invalid Command",\
            "No such file or directory|Permission denied"
        
            "cannot stat",\
            "Image doesn't exist",\
            "bytes total",\
        
            "cannot stat",\
        
            "Invalid Command",\
            "command not found"
            ]
        
            errorMessages = [\
            #!!!pFileName + " does not exist on TFTP server " + srcServerIp + " or TFTP timeout due to wrong TFTP server."\
            "Problem with command syntax? ",\
            "Failed to copy file."
        
            "UCS FI debug plugin " + ucsDebugPluginFileName + " is not on /workspace."
            "UCS FI debug plugin load from volatile:a failed.",\
            "ls /bootflash returns local-mgmt scope returns. Failed to enter debug plugin",\
        
            "For some reason, file " + pFileName + "is not on /workspace",\
        
            "Failed to exit from debug-plugin",\
            "Failed to exit from local-mgmt"
            ]

            # Process all commands above.
        
            for i in range(0, len(commandSets)):
                printBarDouble()
                printDbg(commandHints[i])
                time.sleep(3)
                printDbg("FI command: " + str(commandSets[i]))
                output1 = cli_with_ret(ucsmSsh, commandSets[i], expectPattern[i])
        
                if debug:
                    printBarSingle()
                    printDbg("4. index: " + str(i))
                    printDbg("Looking for error pattern: " + str(errorTriggers[i]) + "...")
                    printDbg("Will throw error message if failure: " + str(errorMessages[i]))
                    printDbg("output1: \n" + str(output1) + "\n")
        
                if re.search(errorTriggers[i], output1):
                    printErr(errorMessages[i])
                    printDbg("output1: \n" + str(output1) + "\n")
                    ucsmSsh.close()
                    return EXIT_ERR

            ucsmSsh.close()
        else:
            printErr("Unsupported or currently unimplemented protocol for file copy to FI.")
            return EXIT_ERR
    
    # Note: This function will copy file from fabric interconnect's workspace: location to another network location.
    # There is rarely a need to copy a file from /bootflash so this function is only concerned with copying
    # the file from local-mgmt scope workspace: directory to location outside the fabric interconnect.

    # req:      
    # input:    
    # - pPath - full path of filename to be copied. If just a filename, assumes it is root directory.
    # Format and assumption of full path may depend on underlying protol. Therefore this parameter full
    # definition is TBD.
    # - DstIp - destination IP to which to be copied to.
    # - pProtocol to be used:
    #   Currently, the supported protocols are: "scp"
    # - pUserName - if needed for certain protocol that requires user login i.e. scp.
    # - pPassword - if needed for certain protocol that requires user login i.e. scp.
    # return:
    # - EXIT_ERR on any falure.
    #   SUCCESS on copy success.
    #
    # Note: the following function prototype is only saved here in case if there is a need to implement copy from
    # /bootflash in which case debug plugin parameters will be needed.
    # def cpFileFromFi(self, pPath, pDstIp = 1, pProtocol = 1, pDbgPath = 1, pDbgDstIp = 1, pDbgProtocol = 1, pUserName = None, pPassword = None):

    def cpFileFromFi(self, pPath, pDstIp = 1, pProtocol = 1, pUserName = None, pPassword = None):
        stat = None
        debug = 0

        CONFIG_COPY_FROM_BOOTFLASH = 0

        if validateFcnInput([pPath, pDstIp, pProtocol]) == EXIT_ERR:
            printErr("Error with input.")
            return EXIT_ERR

        # Set default values.

        # Set default values if arguments are 1 for file being copied, otherwise leave it untouched.

        if pDstIp == 1:
            printDbg("Default copy file destination IP is set to: " + str(DEFAULT_FILE_COPY_DST_IP), debug)
            pDstIp = DEFAULT_FILE_COPY_DST_IP
        else:
            printDbg("Copy file destination IP is set to: " + str(pDstIp), debug)

        if pProtocol == 1:
            printDbg("Default copy file protocol is set to: " + str(DEFAULT_FILE_COPY_PROTOCOL), debug)
            pProtocol = DEFAULT_DEBUG_PLUGIN_PROTOCOL
        else:
            printDbg("Copy file protocol is set to: " + str(pProtocol), debug)

        # Set default values if arguments are 1 for debug plugin being copied, otherwise leave it untouched.
    
        if CONFIG_COPY_FROM_BOOTFLASH:
            if pDbgPath == None:
                printDbg("Will not try copying the debug plugin.")
            else:
                if pDbgPath == 1:
                    pDbgPath = DEFAULT_DEBUG_PLUGIN_FILE_NAME
                    printDbg("Default plugin path is set to: " + str(DEFAULT_DEBUG_PLUGIN_FILE_NAME), debug)
                else:
                    printDbg("Debug plugin path is set to: " + str(pDbgPath), debug)
    
                if pDbgDstIp == 1:
                    pDbgDstIp = DEFAULT_DEBUG_PLUGIN_DST_IP
                    printDbg("Default plugin source IP is set to: " + str(DEFAULT_DEBUG_PLUGIN_DST_IP), debug)
                else:
                    printDbg("Debug plugin source IP is set to: " + str(pDbgDstIp), debug)
    
                if pDbgProtocol == 1:
                    pDbgProtocol = DEFAULT_DEBUG_PLUGIN_PROTOCOL
                    printDbg("Default plugin copy protocol is set to: " + str(DEFAULT_DEBUG_PLUGIN_PROTOCOL), debug)
                else:
                    printDbg("Debug plugin copy protocol is set to: " + str(pDbgProtocol), debug)

            if not pDbgProtocol in fileProtocols and pDbgProtocol != 1:
                printErr(str(pDbgProtocol) + " is not in supported protocol.")
                return EXIT_ERR
    
        # endif CONFIG_COPY_FROM_BOOTFLASH

        # if protocols are not in supported protocol or not equal to 1 (default), exit with error.

        if not pProtocol in fileProtocols and pProtocol != 1:
            printErr(str(pProtocol) + " is not in supported protocol.")
            return EXIT_ERR

        # Handle the case of TFTP file transfer for debug plugin.

        # Determine the tftp server address. Will try to obtain the value from global config file: config.txt
        # if not defined there, will use hard-coded value defined in this function as a last resort.
    
        if CONFIG_COPY_FROM_BOOTFLASH:

            if pDbgPath == DEFAULT_DEBUG_PLUGIN_FILE_NAME:
                printDbg("Debug plugin to be copied with default options.")
                
                if pDbgProtocol == 'FILE_PROTOCOL_TFTP':
                    printDbg("Using TFTP to copy.", debug)
                    srcServerIp = DEFAULT_DEBUG_PLUGIN_DST_IP
                    ucsDebugPluginFileName = DEFAULT_DEBUG_PLUGIN_FILE_NAME
                
                    # Login to FI and copy the BIOS and debug plugin file:
                
                    ucsmSsh = sshLogin(self.mgmtIp, self.user, self.password)
                
                    if ucsmSsh == None:
                        printErr("Unable to establish add'l session to UCSM.")
                        return EXIT_ERR
                
                    # Connect to local-mgmt.
                
                    printDbg("Connecting to local-mgmt")
                    output1 = cli_with_ret(ucsmSsh, "connect local-mgmt", "")
                
                    printDbg("output1:", debug)
                    printDbg(output1)
                
                    commandHints = [\
                    "Copying UCS FI debug plugin " + str(ucsDebugPluginFileName) + " to /workspace" ,\
                    "exit"\
                    ]
                
                    commandSets = [\
                    "cp tftp://" + srcServerIp + "/" + ucsDebugPluginFileName + " /" + ucsDebugPluginFileName\
                    ]
                
                    errorTriggers = [\
                    "File not found|timeout",\
                    "command not found"
                    ]
                
                    errorMessages = [\
                    "UCS FI debug plugin " + ucsDebugPluginFileName + " does not exist on TFTP server " + srcServerIp+ " or TFTP " +\
                    "Failed to exit from local-mgmt"
                    ]
                
                    time.sleep(3)
                
                    # Process all commands above.
                
                    for i in range(0, len(commandSets)):
                        printBarDouble()
                        printDbg(commandHints[i])
                        time.sleep(3)
                        printDbg("FI command: " + str(commandSets[i]))
                        output1 = cli_with_ret(ucsmSsh, commandSets[i], "")
                
                        printDbg("output1: \n" + str(output1) + "\n")
                
                        if re.search(errorTriggers[i], output1):
                            printErr(errorMessages[i])
                            ucsmSsh.close()
                            return EXIT_ERR
    
                    ucsmSsh.close()
                elif pDbgProtocol == 'FILE_PROTOCOL_SCP':
                    printDbg("Using SCP to copy.", debug)
                    # Login to FI and copy the BIOS and debug plugin file:
                
                    ucsmSsh = sshLogin(self.mgmtIp, self.user, self.password)
                
                    if ucsmSsh == None:
                        printErr("Unable to establish add'l session to UCSM.")
                        return EXIT_ERR
                
                    # Connect to local-mgmt.
                
                    printDbg("Connecting to local-mgmt")
                    output1 = cli_with_ret(ucsmSsh, "connect local-mgmt", "")
                
                    printDbg("output1:", debug)
                    printDbg(output1)
                
                    commandHints = [\
                    "Copying UCS FI debug plugin " + str(ucsDebugPluginFileName) + " to /workspace" ,\
                    "exit",\
                    ]
                
                    commandSets = [\
                    "cp scp://" + pUserName + "@" + srcServerIp + ucsDebugPluginFileName + " .",\
                    pPassword\
                    ]
                
                    errorTriggers = [\
                    "Incomplete Command|Invalid Command",\
                    "No such file or directory|Permission denied"
                    ]
                
                    errorMessages = [\
                    "Problem with command syntax? " +\
                    "Failed to copy file."
                    ]
                
                    time.sleep(3)
                
                    # Process all commands above.
                
                    for i in range(0, len(commandSets)):
                        printBarDouble()
                        printDbg(commandHints[i])
                        time.sleep(3)
                        printDbg("FI command: " + str(commandSets[i]))
                        output1 = cli_with_ret(ucsmSsh, commandSets[i], "")
                
                        printDbg("output1: \n" + str(output1) + "\n")
                
                        if re.search(errorTriggers[i], output1):
                            printErr(errorMessages[i])
                            ucsmSsh.close()
                            return EXIT_ERR
    
                    ucsmSsh.close()
                else:
                    printErr("Unsupported or currently unimplemented protocol for default debug plugin copy to FI." + str())
                    return EXIT_ERR

        # end if CONFIG_COPY_FROM_BOOTFLASH

        # Handle the case of SCP for actual file transfer 
        # Determine the tftp server address. Will try to obtain the value from global config file: config.txt
        # if not defined there, will use hard-coded value defined in this function as a last resort.

        srcServerIp = pDstIp
        pFileName = pPath.split('/')[-1]
        
        if pProtocol == 'FILE_PROTOCOL_TFTP':
            printDbg("Using TFTP to copy.", debug)
    
            # Determine the fabric interconnect debug plugin file name. Will try to obtain the value from global config file: config.txt
            # if not defined there, will use hard-coded value defined in this function as a last resort.
        
            # Login to FI and copy the BIOS and debug plugin file:
        
            ucsmSsh = sshLogin(self.mgmtIp, self.user, self.password)
        
            if ucsmSsh == None:
                printErr("unable to establish add'l session to UCSM.")
                return EXIT_ERR
        
            # Connect to local-mgmt.
        
            printDbg("connecting to local-mgmt")
            output1 = cli_with_ret(ucsmSsh, "connect local-mgmt", "")
        
            printDbg("output1:", debug)
            printDbg(output1)
        
            commandHints = [\
            "Copying file " + pFileName + " from /workspace" ,\
            "exit"\
            ]
        
            #"cp " + pFileName + " tftp://" + srcServerIp + "/" + pPath,\ <-- this and below: only tftp root supported.

            commandSets = [\
            "cp " + pFileName + " tftp://" + srcServerIp + "/" + pFileName,\
            "exit"\
            ]
        
            errorTriggers = [\
            "File not found|timeout",\
            "command not found"
            ]
        
            errorMessages = [\
            pFileName + " does not exist or TFTP timeout due to wrong TFTP server."\
            "Failed to exit from local-mgmt"
            ]
        
            time.sleep(3)
        
            # Process all commands above.
        
            for i in range(0, len(commandSets)):
                printBarDouble()
                printDbg(commandHints[i])
                time.sleep(3)
                printDbg("FI command: " + str(commandSets[i]))
                output1 = cli_with_ret(ucsmSsh, commandSets[i], "")
        
                printDbg("output1: \n" + str(output1) + "\n")
        
                if re.search(errorTriggers[i], output1):
                    printErr(errorMessages[i])
                    ucsmSsh.close()
                    return EXIT_ERR

            ucsmSsh.close()
            return SUCCESS

        elif pProtocol == 'FILE_PROTOCOL_SCP':
            printDbg("Using SCP to copy.", debug)
            
            # Login to FI and copy the BIOS and debug plugin file:
        
            ucsmSsh = sshLogin(self.mgmtIp, self.user, self.password)
        
            if ucsmSsh == None:
                printErr("Unable to establish add'l session to UCSM.")
                return EXIT_ERR
        
            # Connect to local-mgmt.
        
            printDbg("connecting to local-mgmt")
            output1 = cli_with_ret(ucsmSsh, "connect local-mgmt", "")
        
            printDbg("output1:", debug)
            printDbg(output1)
        
            commandHints = [\
            "Copying file " + pFileName + " from /workspace" ,\
            "exit",\
            ]

            expectPattern = [\
            "password:",\
            "",\
            ]
        
            commandSets = [\
            "cp " + pFileName + " scp://" + pUserName + "@" + srcServerIp + pPath + " .",\
            pPassword,\
            ]
        
            errorTriggers = [\
            "File not found|timeout",\
            "command not found"
            ]
        
            errorMessages = [\
            pFileName + " does not exist or TFTP timeout due to wrong TFTP server."\
            "Failed to exit from local-mgmt"
            ]

            # Process all commands above.
        
            for i in range(0, len(commandSets)):
                printBarDouble()
                printDbg(commandHints[i])
                time.sleep(3)
                printDbg("FI command: " + str(commandSets[i]))
                output1 = cli_with_ret(ucsmSsh, commandSets[i], expectPattern[i])
        
                printDbg("output1: \n" + str(output1) + "\n")
        
                if re.search(errorTriggers[i], output1):
                    printErr(errorMessages[i])
                    ucsmSsh.close()
                    return EXIT_ERR

            ucsmSsh.close()
        else:
            printErr("Unsupported or currently unimplemented protocol for file copy to FI.")
            return EXIT_ERR

        return SUCCESS

    # Note: This function is not fully implemented yet. 
    # Note: This function will copy file to fabric interconnect in workspace directory. 
    # Once copied, the file can be accessible from local-mgmt scope. Many tests require file needs to be
    # placed onto /bootflash directory, however this file service does not place it in /bootflash location.
    # If particular file is needed to be placed onto /bootflash, call the cpFileToBootFlash function.
    # req:      
    # - File must exist on workspace: directory, otherwise function will fail with exit. 
    # input:    
    # - pFileName - file name to be copied. The file name is assumed to be in workspace directory. 
    # - pFileDbgPath - name of debug file if other than default. 
    # Format and assumption of full path may depend on underlying protol. Therefore this parameter full
    # definition is TBD.
    #   Following values are for accepted:
    #   pFileDbgPath=None - this is the default value and tells the function not to copy debug plugin at all.
    #   pFileDbgPath=1 -  default path/IP/protocol values for pDbgPath/pDbgrcIp/pDbgProtocol must be defined in either generic configuration file or blade specific configuration file.
    #   pFileDbgPath=<full_path> User supplies parameter specifying full path for these parameters.
    # - pFileDbgSrcIp - source ip from which to copy the debug plugin from.
    # - pFileDbgProtocol - protocol used to copy the debug plugin.
    #   Currently, the supported protocols are: "scp"
    # return    
    #           EXIT_ERR on any falure.
    #           SUCCESS on copy success.

    def cpFileToBootflash(self, pFileName, pFileDbgPath = None, pFileDbgSrcIp = None, pFileDbgProtocol = None):
        return SUCCESS
#   Class definition related to blade object, any declaraions, function and variables that 
#   blade instance use it to identify and represent itself should be declared within the blade object.
            
