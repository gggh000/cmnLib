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

# This function fetches the encrypted password from file and decrypt and give back to calling funtion.
# At no point the password should be printed or stored after decryption.
# allowed password types:
#   - CEC for RH1 login
# 
#   input:
#   pPwType     - type of password to be fetched
#   return:
#   EXIT_ERR    - on any condition.
#   pwUnEnc     - unencrypted password that is either created or read from encrypted state.

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
        printDbg ("You unencrypted password is : **** " + pPwUnEnc[:-4])
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
