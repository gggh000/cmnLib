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

from time import gmtime, strftime
from Crypto.PublicKey import RSA
from Crypto import Random

PYTHON_ROOT_DIR = os.environ.get('CURRENT_TREE')
FIT_TYPE_ACM = 0x02

#   Given blade PID, return product code for swims ticket function.
#   input:
#   - pPid - PID of blade server.
#   return:
#   - product code used for swims command's -product switch.
#   - EXIT_ERR for any failure.

def swimsPidToProduct(pPid):
    bladePidToTicketMap = {\
    "UCSB-B200-M2":"gooding-login",\
    "UCSB-B200-M3":"castlerock-login",\
    "UCSB-B420-M3":"sequoia-login",\
    "UCSB-B200-M5":"presidio-login",\
    "UCSB-B480-M5":"presidio-login",\
    "UCSB-B200-M4":"candlestick-login"\
    }

    if not pPid in bladePidToTicketMap:
        printErr("Unable to find " + str(pPid) +  "'s associated product code.")
        return EXIT_ERR
    else:
        returnData = bladePidToTicketMap[pPid]
        return returnData

# Create ticket function.
# Steps:
#   - delete current ticket file name or move somewhere else.
#   - construct ticket file name. (blade pid must be part of it)
#   - get cec username,pw.
#   - log on to rh1.
#   - create ticket with -log option.
#   - extract ticket id from log.
#   - return list (ticket id, ticketFileName)
#   input: 
#   pBlade - blade instance object.
#   return:
#   list [ticket id, ticketFilename] both members are string types.

def swimsCreateTicket(pBlade, pProductCode):
    debug = 0
    rh1TargetPw = getPw("CEC")
    rh1TargetUser = getGlobal('CONFIG_RH1_SERVER_UNAME')
    rh1TargetPwShow = str(getUnEncPw(rh1TargetPw))
    ticketLocation = "/users/ggankhuy/ticket/"

    ticketFileName = pBlade.pid + "-ticket.tic"
    ticketLogFileName = pBlade.pid + "-ticket.create.log"
    ticketIdLogFileName = pBlade.pid + "-ticket.id.txt"

    if rh1TargetUser == None or rh1TargetPw == None:
        printErr("user/password retrieve error: /user: " + str(rh1TargetUser) )
        return EXIT_ERR
    
    cmdCreateTicket = \
    "/router/bin/code_sign swims ticket create -products " + pProductCode + " -ticketType DEV -maxUses 500\
    -validityHours 744 -reason automation -format json -username1 ggankhuy -authType CEC -out " + ticketFileName + "\
     -verbose -logFile " + ticketLogFileName + " > ./temp.log"

    sshRh1a = sshLogin(RH1_IP, rh1TargetUser, rh1TargetPw)

    if sshRh1a == None:
        printErr("Unable to login to RH1 server")
        return EXIT_ERR

    # Delete the ticket log file (important!) and re-create the ticket. Once created the ticket, extract the ID 
    # and return along ticketFileName.

    printDbg("cd to user dir:")
    stat = cli_with_ret(sshRh1a, "cd " + ticketLocation, "\[.*\].*$", "linuxShell")
    printDbg("stat: " + stat, debug)

    printDbg("pwd:")
    stat = cli_with_ret(sshRh1a, "pwd", "\[.*\].*$", "linuxShell")
    printDbg("stat: " + stat, debug)

    printDbg("Removing old ticket files.")
    stat = cli_with_ret(sshRh1a, "rm -rf " + ticketLocation + ticketLogFileName, "\[.*\].*$", "linuxShell")
    printDbg("stat: " + stat, debug)

    printDbg("Removing old log file.")
    stat = cli_with_ret(sshRh1a, "rm -rf temp.log", "\[.*\].*$", "linuxShell")
    printDbg("stat: " + stat, debug)
    time.sleep(2)

    stat = cli_with_ret(sshRh1a, "rm -rf " + ticketLocation + ticketFileName, "\[.*\].*$", "linuxShell")
    printDbg("stat:" + str(stat), debug)
    time.sleep(2)

    printDbg("creating ticket")
    stat = cli_with_ret(sshRh1a, cmdCreateTicket, "\[.*\].*$", "linuxShell")
    printDbg("stat:" + str(stat), debug)
    time.sleep(2)

    if stat == EXIT_PASSWD:
        printDbg("sending passwd.")
        stat = cli_with_ret(sshRh1a, rh1TargetPw, "\[.*\].*$", "linuxShell")
    else:
        printErr("expected password.")
        sshRh1a.close()
        return EXIT_ERR            

    printDbg("grepping ticket ID")
    ticketCreateLogGrep = cli_with_ret(sshRh1a, "cat " + ticketLocation + ticketLogFileName + " | grep ticketId", "\[.*\].*$", "linuxShell")

    if type(ticketCreateLogGrep) != str:
        printErr("grepped log is not string type: " + str(ticketCreateLogGrep))
        sshRh1a.close()
        return EXIT_ERR
        
    ticketCreateLogGrep = re.sub(".*{", "", ticketCreateLogGrep)
    ticketCreateLogGrep = re.sub("}.*", "", ticketCreateLogGrep)
    printDbg("grep filtered log: \n-----------\n" + str(ticketCreateLogGrep) + "\n-------------", debug)
    time.sleep(2)

    try:
        ticketTokens = ticketCreateLogGrep.split(',')
    except AttributeError:
        printErr("Error splitting the grep, grep return might have failed.")
        printERr("grep ticket create log: " + str(ticketCreateLogGrep), debug)
        sshRh1a.close()
        return EXIT_ERR

    printDbg("ticketTokens loop.", debug)
    printDbg("ticketTokens count: " + str(len(ticketTokens)), debug)

    counter = 0

    for i in ticketTokens:
        printDbg("\n------------------------\n" +  str(counter) + ":\n" + str(i) + "\n--------------------------------" , debug)
        counter += 1

        if re.search("u\'ticketId\':", i):
            ticketId = i.split(':')[1].strip()
            printDbg("Ticket ID is found for newly created ticket: " + str(ticketId))
            
            printDbg("Saving ticket id to ticketId log file.", debug)
            stat = cli_with_ret(sshRh1a, "echo " + str(ticketId) + " >> " + ticketIdLogFileName, "\[.*\].*$", "linuxShell")

            try:
                int(ticketId)
            except ValueError:
                printErr("Invalid ticket ID, must be 5 digits.")
                sshRh1a.close()
                return EXIT_ERR
            return [str(ticketId), str(ticketFileName)]

    printErr("Unable to find ticket ID.")
    sshRh1a.close()
    return EXIT_ERR

# This function fetches the encrypted password from file and decrypt and give back to calling funtion.
# At no point the password should be printed or stored after decryption.
# allowed password types:
#   - CEC for RH1 login
# 
# pPwType    - type of password to be fetched

def getPw(pPwType=None):
    debug = 0
    user = None
    pwUnEnc = None

    pwEncFilePath = None
    pwEncFileDir = None
    pwEncFileName = None

    choice = None

    fpKeyRead = None
    fpPwRead = None
    fpPwWrite = None

    keyFileName = None
    keyFileDir = None
    keyFilePath = None

    printDbg("entry ------------ ", debug)

    user = os.environ['USER']
    TEST_MODE = 0

    #if pPwType == "CEC" or pPwType == "TEST1" or pPwType == "TEST2":

    if type(pPwType) == str and len(str(pPwType)) >= 3:
        pwEncFileName = "sa.tool.enc.pw." + pPwType + ".bin"
    
        # attempt to read the password from file.
        # guest account, can not store password so asks user to input password and also guest acconut can not store any password even encrypted.

        if user == "guest":
            print "This is a guest account. The user needs to input password everytime script needs access to server. To permanently store your "
            print "encrypted password (so you don't have to enter it everytime, establish non-root non-guest account on this server."

            while 1:
                pwUnEnc = raw_input("Input your " + pwType + "password :", dont_print_statement_back_to_screen)
    
                if pwUnEnc:
                    return pwUnEnc           

        # root account, stored on designated root folder and get from there.
        # non-root acconut, stored on user's home dir:  ~/sa.tool.enc.<pwType>.pw.bin file and fetch and decrypt.

        elif  user == "root":
            pwEncFileDir = "/rootpw/"
            printDbg("root account: ", debug)
        else:
            printDbg("non-root non-guest account: " + user, debug)
            pwEncFileDir = "/home/" + str(user) + "/"

        pwEncFilePath = pwEncFileDir + pwEncFileName

        keyFileName = "sa.tool.key." + pPwType + ".bin"
        keyFileDir = pwEncFileDir
        keyFilePath = keyFileDir + keyFileName
    
        printDbg("password file to read from: " + pwEncFilePath, debug)

        # if file not found
        # Tell user to input password and give option to store encrypted password on file:
            # option1 - user chooses No: everytime script needs access needing pw, user has to input.
            # option2 - user chooses Yes: password is encrypted and stored on ~/sa.tool.enc.<pwType>.pw.bin file and no need to input again.
        # If user password file is deleted then user will need to re-input again 
        # If user password itself on the server is changed due to security policy, script access will be denied and user needs to reset the password    
        
        if not os.path.exists(pwEncFilePath):

            print "Password file is not found. It is either you are setting up first time or password is deleted."
            print "Two options:"
            print "1.  set your password in this server. The password will be encrypted. This is done only once until password is changed or lost."
            print "    if password is changed on the remote server or forgot, delete the file: " + pwEncFilePath + "  and it will ask you to set it up"
            print "    again."
            print "2.  do not set your password in this server. With this option, everytime script needs to access the server needing " + pPwType
            print " password, you'd need to enter it manually."

            while 1:
                choice = raw_input(" 1 or 2 ?: ")

                if choice == "1":
                    if TEST_MODE == 1:
                        pwUnEnc = "testPassword12345"
                    else:
                        print "Password will be encrypted and stored in " + pwEncFilePath
    
                        while 1:
                            pwUnEnc = getpass.getpass()                           
                            pwUnEnc1 = getpass.getpass()                           

                            if pwUnEnc == pwUnEnc1:
                                break
                            else:
                                print "Password entered does not match. Try again"
                        
                    if debug:
                        printUnEncPw(pwUnEnc)

                    # Now set the password now. The pForce=None, if file exists, code should never reach here. 
                    
                    stat = setPw(pwUnEnc, pPwType, None)
                    if stat:
                        break
                    else:               
                        printErr("Error setting password.")
                        return EXIT_ERR

                elif choice == "2":
                    print "Password will not be stored. "
                    pwUnEnc = getpass.getpass()                           
                    return pwUnEnc
                else:
                    print "invalid choice. Try it again."

        # Handled the case of pwFile not exist on this server.
        # Now read back the password and encrypt and sent back to calling function        
    
        fpPwRead = open(pwEncFilePath, 'rb')
        fpKeyRead = open(keyFilePath, 'r')

        if fpKeyRead == None:
            printErr("Error opening/reading the key file: " + pwEncFilePath)
        else:
            key = RSA.importKey(fpKeyRead.read())

        printDbg("your key: ", debug)

        if debug:
            print bytes(key)
            print "Type/len of key data: " + str(type(key))

        if fpPwRead == None:
            printErr("Error reading the password file: " + pwEncFilePath)
        else:
            encPwRdBack = fpPwRead.read()
            pwUnEnc = key.decrypt(encPwRdBack)
            fpPwRead.close()

            if debug:
                printUnEncPw(pwUnEnc)
            
            return pwUnEnc        
    else: 
        printErr("Invalid password type:" + str(type(pPwType)) + ". Password type must be string and type length must be more than 2.")
        return EXIT_ERR

    return pwUnEnc

# print unencrypted password.
# this will only partially print the unencrypted password for debugging.

def printUnEncPw(pPwUnEnc):
    
    print "Printing partial password info",

    if len(pPwUnEnc) >= 6:
        printDbg ("You unecnrypted password is : **** " + pPwUnEnc[:-4])
    else:
        printDbg ("Error: can not print any part of password, it is too short")

# This function will input the unencrypted password (visible) and encrypt write to encrypted password to file.
# At no point unencrypted password should be printed or stored before encryption.
#
# pPwUnEnc   - unencrypted password
# pFileName  - name of password file that contains encrypted password
# pPwType    - password type i.e. "CEC"
# pForce     - overwrites the existing passwod file (to reset the password)
# return     - SUCCESS if password setup is successfull, EXIT_ERR if fail.

def setPw(pPwUnEnc, pPwType, pForce=None):
    user = None
    debug = 0
    fpPwWrite = None
    fpKeyWrite = None

    printDbg("entry ------------ ", debug)
    
    user = os.environ['USER']

    #if pForce set to None 
    #    if not os.path.exists(pwEncFilePath):
    #    pw file exists
    #        return err (password already set, script logic error.

    if  user == "root":
        pwEncFileDir = "/rootpw/"
        printDbg("root account: ", debug)
        print "creating /rootpw/"
        os.system("mkdir /rootpw/")
    else:
        printDbg("non-root non-guest account: " + user, debug)
        pwEncFileDir = "/home/" + str(user) + "/"

    # construct file names 

    pwEncFileName = "sa.tool.enc.pw." + pPwType + ".bin"
    pwEncFilePath = pwEncFileDir + pwEncFileName

    keyFileName = "sa.tool.key." + pPwType + ".bin"
    keyFileDir = pwEncFileDir
    keyFilePath = keyFileDir + keyFileName

    if pForce == None:
        if os.path.exists(pwEncFilePath):
            printErr("Trying to set the password when it was set previously. Logic error. Check your code.")
            return EXIT_ERR
        
    # pForce must be set yes or password file does not exist.
    # open file and validate the file pointers.

    fpPwWrite = open(pwEncFilePath, 'w')
    fpKeyWrite = open(keyFilePath, 'w')

    if fpPwWrite == None:
        printErr("File system error: can not open " + pwEncFilePath)
        return RET_EXIT

    if fpKeyWrite == None:
        printErr("File system error: can not open " + keyFilePath)
        return RET_EXIT

    printDbg("Generating random key:", debug)
    
    randNo = Random.new().read
    key = RSA.generate(1024, randNo)
    
    # print key information:
    
    printDbg("your key: ", debug)

    if debug:
        print bytes(key)
        print "Type/len of key data: " + str(type(key))

    printDbg("can enc/sign/haspriv: " + str(key.can_encrypt()) + "/" + str(key.can_sign()) + "/" + \
        str(key.has_private()), debug)
    
    # save key to file name assoc-d with user.
    
    if fpKeyWrite:
        fpKeyWrite.write(key.exportKey('PEM'))
        fpKeyWrite.close()
    else:
        printErr("File Error: Can not create a file")
        return RET_EXIT
    
    printDbg("saved key to " + str(keyFilePath), debug)
    #os.system("hexdump -C  " + keyFilePath)
    
    # encrypt:
    
    public_key = key.publickey()
    
    pwEnc = public_key.encrypt(pPwUnEnc, 32)[0]
    
    printDbg("your encrypted password: \n", debug)

    if debug:
        print pwEnc
    
    if fpPwWrite == None:
        printErr("Failed to open a file for password storage")
        return RET_EXIT
    
    fpPwWrite.write((pwEnc))
    fpPwWrite.close()
    return SUCCESS    
    
#   Return FIT (firmware interface table) entry for the blade under test.
#   Typical FIT entries include uCode, ACM, BootGuard and others. 
#
#   input:
#   pPcie_inst - pcie_inst which holds ssh connection.
#   pBlade - blade instance which holds server info
#   pType - type of FIT entry found.
#   return:  
#   <list>:<int> - memory address of fit entry if found multiples times or one time.
#   EXIT_ERR - if not found or any other error.
    '''

def getFitEntry(pBlade, pPcie_inst, pType):
    fitAddress = None
    fitSize = None
    debug = 0
    fitAddressesFound = []

    if validateFcnInput([pType]) == EXIT_ERR:
        printErr("input validation has failed.")
        return EXIT_ERR

    fitAddress = pPcie_inst.read_mem_dword(pBlade, "0xffffffc0")

    if fitAddress:
        printDbg("FIT address: " + str(fitAddress))
    else:
        printErr("Unable to obtain FIT address.")
        return EXIT_ERR

    printDbg("obtaining FIT size...", debug)

    fitSizeAddress = str(hex(int(fitAddress, 16) + 8))
    printDbg("fitSizeAddress: " + str(fitSizeAddress), debug)
    fitSize = pPcie_inst.read_mem_byte(pBlade, fitSizeAddress)

    if fitSize:
        printDbg("FIT size (no. of entries in FIT: " + str(fitSize))
    else:
        printErr("Unable to obtain FIT size.")
    
    fitAddressWalker = fitAddress
    fitTypeWalker = fitAddressWalker

    for i in range(int(fitSize, 16)):
        if debug:
            printBarSingle()

        printDbg("iteration: " + str(i), debug)
        fitAddressWalker = hex(int(fitAddressWalker, 16) + 16)          # walk to next entry.
        fitTypeWalker = hex(int(fitAddressWalker, 16) + 14)             # increment by 14 to get to type field.

        fitEntryAddress = pPcie_inst.read_mem_dword(pBlade, fitAddressWalker)
        fitEntryType  = pPcie_inst.read_mem_byte(pBlade, fitTypeWalker)

        printDbg("current entry address, type: " + str(fitEntryAddress) + ", " + str(fitEntryType), debug)

#       if int(fitEntryType, 16) == int(pType, 16):
        if int(fitEntryType, 16) == pType:
            printDbg("found matchin entry at " + str(fitEntryAddress), debug)
            fitAddressesFound.append(fitEntryAddress)

        if fitEntryAddress == "FFFFFFFF":
            printDbg("skipping.", debug)
        else:
            printDbg("FIT entry address|type: " + str(fitEntryAddress) + ", " + str(fitEntryType), debug)

    if len(fitAddressesFound):
        printDbg("FIT matchin entries found.")
        printSeq(fitAddressesFound)
        return fitAddressesFound
    else:
        printErr("No FIT matching entries found.")        
        return EXIT_ERR

#   Return dictionary data for ACM entry in FIT.
#   Using FIT table api, this returns ACM header information in dictionary format
#   for all fields. For the fields longer than 4 bytes (key, signature etc)
#   it will only return first 4 bytes. (enhancement might be done in the future).
#   Due to limitation of read_mem_dword/word/byte API, currently it will only support field size 1, 2, 4.
#   Field size over 4 bytes will be cut to 4 bytes (Future implementation can support any field size)
#   Any other field size besides mentioned above will return with error.

#   input:
#   pPcie_inst - pcie_inst which holds ssh connection.
#   pBlade - blade instance which holds server info
#   pType - type of FIT entry found.
#   return:  
#   <list>:<int> - memory address of fit entry if found multiples times or one time.
#   EXIT_ERR - if not found or any other error.
    '''
    '''
def getFitEntryAcm(pBlade, pPcie_inst, pType):
    lAddressAcmList = None
    lAddressAcm = None
    lAcmDict = {}
    currFieldSize = None
    index1 = None
    debug = 1

    # Obtain address of ACM.

    lAddressAcmList = getFitEntry(pBlade, pPcie_inst, FIT_TYPE_ACM)
    
    if lAddressAcmList == None:
        printErr("ACM address is not found.")
        return EXIT_ERR

    if len(lAddressAcmList) != 1:
        printErr("There should be only one ACM in the FIT table: No. of ACM-s: " + str(len(lAddressAcm)))
        return EXIT_ERR    

    lAddressAcm = lAddressAcmList[0]

    # Acm structure offsets, sizes and names defined.

    acmStructFieldOffsets = [0, 2, 4, 8, 12, 14, 16, 20, 24, 28, 30, 32, 36, 40, 44, 48, 52, 56, 120, 124, 128, \
        384, 388]
    acmStructFieldSizes = [2, 2, 4, 4, 2, 2, 4, 4, 4, 2, 2, 4, 4, 4, 4, 4, 4, 64, 4, 4, "KeySize*4", 4, 256]
    acmStructFieldNames = ["ModuleType", "ModuleSubType", "HeaderLen", "HeaderVersion", "ChipsetID", "Flags", \
        "ModuleVendor", "Date", "Size", "TXTSvn", "SESVN", "CodeControl", "ErrorEntryPoint", "GdtLimit", \
        "GdtBasePtr", "SegSel", "EntryPoint", "Reserved2", "KeySize", "ScratchSize", "RsaPubKey", "RsaPubExp", \
        "RsaSig"]

    currFieldSize = None
    index1 = None

    lAcmDict = parseMemStruct(pBlade, lAddressAcm, pPcie_inst, acmStructFieldNames, acmStructFieldSizes, acmStructFieldOffsets)

    if lAcmDict == None:
        printErr("Error parsing ACM struct.")
        return EXIT_ERR

    if len(lAcmDict) != len(acmStructFieldSizes):
        printWarn("Return dictionary struct size does not match: lAcmDict, acmStructFieldSizes: " + \
            str(lacmDict) + ", " + str(acmStructFieldSizes))
        return lAcmDict

    for i in acmStructFieldNames:
        print i + ": " + lAcmDict[i]
    return lAcmDict
    '''
