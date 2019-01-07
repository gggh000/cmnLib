# PCIE module (pcie.py) 
# implements any inspects of class, functions and variables that are concerned with the
# test operation pcie subsystem for the system under test. 

import time
from security import *
from saLibrary import *
import saLibrary
import re
from ucs import *

#   pcie class which implements all aspects of pcie related operation including, reading configuration space,
#   enumeration, reading pcie-setting file and others. 

class pcie():
    ucsmSsh = None
    bmcSsh = None
    fiHostName = None
    priority = None

    # defined class codes.

    PCIE_CC_OLD = "0x00"
    PCIE_CC_MSD = "0x01"
    PCIE_CC_NET = "0x02"
    PCIE_CC_VGA = "0x03"
    PCIE_CC_MMEDIA = "0x04"
    PCIE_CC_MEM = "0x05"
    PCIE_CC_BRIDGE = "0x06"
    PCIE_CC_COM = "0x07"
    PCIE_CC_BASE = "0x08"
    PCIE_CC_INPUT = "0x09"
    PCIE_CC_DOCK = "0x0a"
    PCIE_CC_PROC = "0x0b"
    PCIE_CC_SERIAL = "0x0c"
    PCIE_CC_WIRELESS = "0x0d"
    PCIE_CC_INTEL_IO = "0x0e"
    PCIE_CC_SAT_COM = "0x0f"
    PCIE_CC_CRYPTO = "0x10"
    PCIE_CC_DATA_SIG = "0x11"
    PCIE_CC_RESERVED = "0x12"
    PCIE_CC_UNDEF = "0xff"

    # PCIe capabilities and extended capability code, refer to PCI_Express_Base_r3.0_10Nov10.pdf Section 7
    # for more definitions as most of are defined there. Some of the IDs not defined there are below:
    # CAP_ID_PWR_MGMT: From PCI Bus Power Management Interface Specification Revision 1.2 
    # CAP_ID_MSI_INT: conventional_pci_2_3.pdf, 6.8.1.1 PCI Local Bus Specification Revision 2.3 March 29, 2002

    # PCIe standard capabilities are started with CAP_ID_<CAP_ID_NAME>
    # PCIe extended capabilities are started with CAP_ID_EXT_<CAP_ID_NAME>

    CAP_ID_PCI_EXPRESS = "10"
    CAP_ID_PWR_MGMT = "01" 
    CAP_ID_MSI_INT = "05"
    CAP_ID_SVID = "0D"

    CAP_ID_EXT_AER = "0001"
    CAP_ID_EXT_VC_1 = "0002"
    CAP_ID_EXT_VC_2 = "0009"
    CAP_ID_EXT_DEV_SN = "0003"
    CAP_ID_EXT_PWR_BUDGET = "0004"
    CAP_ID_RC_LINK_DECL = "0005"
    CAP_ID_RC_INT_LINK_CTRL = "0006"
    CAP_ID_EXT_ACS_EXT = "000D"
    CAP_ID_EXT_SRIOV = "0010"

    # Following variables are used by pcieSetupSp function. Many pcie test 
    # scripts need to create specific combination of vnics based on the adapter configuration
    # which itself is defined in the priority. The original vnics are simply discard since
    # new pcie specific sp is created.

    testVnics = []                                  # test vnics created specifically during the pcie test scripts.
    originalBootPolicy = None

    # pcie initializatoin routine which is called everytime pcie class is instantiated.
    # input:    pUcsmSsh - ssh handle to ucsm
    #           pBmcSsh - ssh handle to bmc sol
    #           pFiHostName - FI hostname
    #           pPriority - adapter configuration code.
    #           pBlade - blade instantiated object.

    def __init__(self, pUcsmSsh = None, pBmcSsh = None, pFiHostName = None, pPriority = None, pBlade = None):
        self.ucsmSsh = pUcsmSsh
        self.bmcSsh = pBmcSsh
        self.fiHostName = pFiHostName
        self.priority = pPriority

        if pBlade == None:
            printWarnMinor("can not set up test vnics with out pBlade information")
            return None
        if pFiHostName == None:
            printWarnMinor("can not set up test vnics with out pFiHostName information")
            return None
        if pUcsmSsh == None:
            printWarnMinor("can not set up test vnics with out pUcsmSsh information")
            return None

        # Some pcie test scripts needs the vnic names in the service-profile therefore
        # fill the vNics members with actual vnic names created specifically for pcie test
        # scripts. 

        ret = cli_with_ret(pUcsmSsh, 'top', self.fiHostName)
        time.sleep(1)
        ret = cli_with_ret(pUcsmSsh, 'scope org /', self.fiHostName)
        time.sleep(1)
        ret = cli_with_ret(pUcsmSsh, 'scope service-profile ' + pBlade.spName, self.fiHostName)
        time.sleep(1)
        ret = cli_with_ret(pUcsmSsh, 'show vnic | egrep "00:25" | egrep  invert-match dummy', self.fiHostName)

        vNics = ret.strip().split('\n')
        printDbg("original vNICS being removed: " + str(len(vNics)))

        if vNics:
            for vNic in vNics:
                printDbg("adding vnic " + str(vNic) + " to test vnics.")
                self.testVnics.append(vNic)
        else:
            printWarn("current service profile has no vnic, or error finding vnics in the service-profile!")

    # This function is used by pcieRestoreBlade script after finished running all pcie
    # test scripts and need to restore non-pcie test sp for oher non-pcie automation scripts.
    # Another application of this function is that pcieSetupBlade script uses it when the setting the blade
    # for pcie automation test scripts is unsuccesful and script needs to restore the blade associate with
    # non-pcie test sp back.
    #    
    # Here are the four initialization and restoration scripts that they do not test anything however
    # used to setup and restore the sp-s for other test scripts:
    # <spName> is the original sp prior to launching automation.
    #
    # 1. setupBlade - test script will create new service-profile specifically for any test scripts with the name <spName>-sa
    # By doing so, sp <spName> along with all information prior to launching the automation is left intact after re-association
    # with test sp: <spName>-sa
    # 2. pcieSetupBlade - will create another test sp speficially for pcie test scripts, specifically for pcie test scripts
    # This is because many of the pcie test scripts requires certain vnic adapters and other configuration. Therefore this
    # scripts will disassociate current sp <spName>-sa from the blade and will create and associate with new 
    # sp under the name <spName>-sa-pcie and will configure any pcie specific configuration in this sp.
    # 3. pcieRestoreBlade - will restore service-profile non-pcie sp <spName>-sa by re-associating the blade with this sp
    # and discarding the pcie test sp: <spName>-sa-pcie. This script should be called after running all pcie test scripts.
    # 4. restoreBlade - will restore original service-profile <spName> after running all test scripts by associating it with the blade.
    #
    # So here is the overall flow:
    # - blade is associated sp prior to running automation <spName>
    #   - blade is assoc-d with new sp <spName>-sa (setupBlade.py)
    #   - runs non-pcie automation scripts (cpu, tpm etc.,)
    #     - blade is assoc-d with new sp for pcie script: <spName>-sa-pcie (pcieSetupBlade.py)
    #     - runs pcie automation test scripts (pcie etc.,)
    #     - blade is assoc-d with non-pcie test sp: <spName>-sa (pcieRestoreBlade.py)
    #   - runs non-pcie automation scripts (cpu, tpm etc.,)
    # - blade is associated with sp prior to running auomation (restoreBlade.py)
    # - at this point, service-profile associated with blade prior to launching the script is intact.

    # req:      no requirement.
    # input:    pUcsmSsh - handle to ucsm ssh session
    #           pSp - sp instant
    #           pBlade - blade instant.
    # Return    sp object recovered or in case not recovered, original pSp.
    #           EXIT_ERR - if restoration is failed for any reason not mentioned in valid return.

    def pcieRestoreSp(self, pFi):
        debug = 1

        # temporary code patch assignment until code is fixed later.

        pUcsmSsh = pFi.ucsmSsh
        pSp = pFi.mSp
        pBlade = pFi.mSp.mBlade

        # Attempt to get original sp name from run-time file.

        try:
            spNameOriginal = getGlobalTmp("pcie-service-profile-backup").strip()
        except AttributeError:
            printWarn("Unable to find pcie-service-profile-backup from global tmp")
            return EXIT_ERR

        if spNameOriginal == EXIT_ERR:
            printErr("Unable to find pcie-service-profile-backup entry from global tmp file")
            return EXIT_ERR

        # If original spName is not same as current service-profile name (*-pcie), then re-associate
        # to old service-profile. Delete the pcie test sp along with all policies with the same name.   
        # If they are same leave without doing anything however return the current sp instant back to calling 
        # function.
        # pSp - CXSX-pcie = current pcie script sp.
        # sp2 - CXSX = prior sp.


        if spNameOriginal != pSp.spName:

            cFi2 = fi(pFi.mgmtIp, pFi.mSp.bladeLoc)
            sp2 = cFi2.mSp
            #sp2 = sp(pBlade.location)
            sp2.fiHostName = pSp.fiHostName
            sp2.spName = spNameOriginal

            printDbg("Recovered original sp name: " + str(spNameOriginal), debug)
            printDbg("DisAssociating from " + pSp.spName, debug)
    
            pSp.disassoc(pUcsmSsh, pBlade.location, 1)
    
            printDbg("Associating with " + sp2.spName, debug)
    
            sp2.assoc(pUcsmSsh, pBlade.location, 1, 1)
    
            # delete service-profile and its associated policies.

            pSp.delSolPolicy(pUcsmSsh, pSp.spName)
            printDbg("deleted sol policy")
        
            #lFi2.mSp.delBootPolicy(pFi, pBlade.spName)

            pSp.delBootPolicy(pFi, pSp.spName)
            printDbg("deleted boot-policy")
        
            pSp.delBiosPolicy(pUcsmSsh, pSp.spName)
            printDbg("deleted bios-policy")
        
            pSp.delHostFwPolicy(pUcsmSsh, pSp.spName)
            printDbg("deleted host-fw-policy")
        
            pSp.delIpmiProfile(pUcsmSsh, pSp.spName)
            printDbg("delete ipmi profile")
        
            pSp.delSp(pUcsmSsh, pSp.spName)
            printDbg("deleted service-profile")
        
            # Wait for sp re-configuration to complete.

            if sp2.waitConfigComplete(pUcsmSsh) == EXIT_ERR:
                printErr("Configuration wait time out! Next script might be affected")
                return EXIT_ERR

            printDbg("Returning original sp.")
            return sp2
        else:
            printInfoToFile("Original sp is same as current test sp: " + pSp.spName + \
                ". Leaving without restore")

            printDbg("Returning current sp.")
            return pSp       

    # This function sets up new vNICs based on the setting-file's placement flag and priority.
    # The outcome of this function is very specific number of vnics and other related settings
    # that are used for certain pcie test scripts namely: checkSriovCap, checkLinkState etc.,
    # This function should only be used for pcieSetupSp scripts and nowhere else.
    
    # req:      None
    # input:    pFi - ssh handle to fi.
    #           pBlade - blade instance. 
    #           pHandle - fileHandle.
    #           pPriority - priority. 
    #           pLogicalId - logicalId of the test. 
    #           pDynVnicPol - if set, sets up additional dynamic vnic policies attached to vnic.
    #           pVnics - No. of vNICs to be created on per adapter.
    # Return    newly created sp if successful initialization.
    #           EXIT_ERR if failure.

    def pcieSetupSp(self, pFi, pUcsmSsh, pBlade, pHandle, pPriority, pLogicalId, pDynVnicPol = 0, pVnics = 3):
        functionList = []
        priorityDependencyList = []
        self.testVnics[:] = []
        pcieVnics = []

        counter = 0
        debug = 1
        debugL2 = 0
        lineNo = 0

        priorityFlag = 0
        logicalIdIndex = 0
        vnicPlacementNo = 0
        vNicInternetVlan = None

        line = ""
        currLine = ""
        outp = ""
        ethName = ""
        skipBlock = ""

        printDbg("pLogicalId: " + str(pLogicalId) + "pHandle: " + str(pHandle) + "pPriority: " + str(pPriority), debug)

        # Disassoc from current sp and create new sp and assoc with the blade.
        # If current service-profile name ends with -pcie, do not disassoc,
        # instead directly setup vnics. It is assumed that sp that ends with -pcie
        # is specifically created throuh this pcie module, if  sp with same name
        # is created any other meands, result is undesired and unpredictable!
        # if current sp ends with -pcie, then sp2 instant is created with same sp name essentially
        # leaving the blade association same and will setup the current sp for pcie test scripts.

        if not re.search("-pcie", pBlade.spName):

            # mSp is the current blade's service-profile - non pcie test sp.

            mSp = sp(pBlade.location, pBlade.spName)
            mSp.fiHostName = pFi.hostName

            # sp2 is the new service-profile: original_sp_name-pcie - pcie test sp.
            # create pcie test sp and associated policies and re-assoc blade under test with this new sp.

            lFi2 = fi(sys.argv[1], sys.argv[2], pBlade.spName + "-pcie")
        
            if lFi2 == EXIT_ERR:
                printErr("Can not initialize FI instance")
                return RET_FAIL
    
            mSp.disassoc(self.ucsmSsh, pBlade.location, 1)
            pBlade.createSp(self.ucsmSsh, lFi2.mSp.spName, None)
            printDbg("Created service-profile.")
    
            lFi2.mSp.setBiosPolicy(self.ucsmSsh)
            printDbg("Created bios-policy.")

            lFi2.mSp.setHostFwPolicy(self.ucsmSsh)
            printDbg("Created host-fw-policy.")
    
            lFi2.mSp.setSolPolicy(pFi)
            printDbg("Created sol policy.")
        else:

            # If current sp ends with -pcie, then it is assumed that it is pcie test sp.

            lFi2 = fi(sys.argv[1], sys.argv[2])
        
            if lFi2 == EXIT_ERR:
                printErr("Can not initialize FI instance")
                return RET_FAIL

            lFi2.mSp = sp(pBlade.location, pBlade.spName)

            if lFi2.mSp.refreshSpNew(lFi2.ucsmSsh, lFi2, lFi2.mSp.mBlade) == EXIT_ERR:
                printDic(lFi2.sp)
                printErr("Can not refresh sp, quitting.")
                return EXIT_ERR
            
        # Create dummy vnic so that when original vnics are deleted no default vnic added automatically.

        printDbg("Creating dummy vnic", debug)

        ret = cli_with_ret(self.ucsmSsh, 'top', self.fiHostName)
        time.sleep(1)
        ret = cli_with_ret(self.ucsmSsh, 'scope org', self.fiHostName)
        time.sleep(1)
        ret = cli_with_ret(self.ucsmSsh, "scope service-profile " + pBlade.spName, self.fiHostName)
        time.sleep(1)
        ret = cli_with_ret(self.ucsmSsh, 'create vnic dummy', self.fiHostName)
        time.sleep(1)
        ret = cli_with_ret(self.ucsmSsh, 'scope vnic dummy', self.fiHostName)
        time.sleep(1)
        ret = cli_with_ret(self.ucsmSsh, 'set identity mac-pool default', self.fiHostName)
        time.sleep(1)

        ret = cli_with_ret(self.ucsmSsh, 'commit', self.fiHostName)
        time.sleep(1)

        # Delete every original vnic except dummy vnic.

        printDbg("Removing original vNic", debug)
        
        ret = cli_with_ret(self.ucsmSsh, 'top', self.fiHostName)
        time.sleep(1)
        ret = cli_with_ret(self.ucsmSsh, 'scope org /', self.fiHostName)
        time.sleep(1)
        ret = cli_with_ret(self.ucsmSsh, 'scope service-profile ' + pBlade.spName, self.fiHostName)
        time.sleep(1)
        ret = cli_with_ret(self.ucsmSsh, 'show vnic | egrep "00:25" | egrep  invert-match dummy', self.fiHostName) # need better way to implement!!!!
        
        vNics = ret.strip().split('\n')
        printDbg("original vNICS being removed: " + str(len(vNics)), debug)

        if debug:
            printSeq(vNics)

        counter = 0

        # For each original vnic, delete from service-profile. 
        
        for vNIC in vNics:
            if debug:
                printDbg("iter | vNIC line: " + str(counter) + " | " + str(vNIC))
                printDbg("vNIC split line: ", debug)
                print vNIC.split()

            if len(vNIC) and re.search('00:25', vNIC):            
                if not vNIC.split()[0] in pcieVnics:
                    printDbg("deleting this vnic: " + vNIC.split()[0])
                    ret = cli_with_ret(self.ucsmSsh, 'delete vnic ' + vNIC.split()[0], self.fiHostName)
                    time.sleep(1)
            else:
                printWarn("Line is empty!:")
                printDbg(str(vNIC))

            counter += 1
        
        ret = cli_with_ret(self.ucsmSsh, 'commit', self.fiHostName)

        # With only dummy vnics left in the sp, create pcie test specific vnics. 
        # The No. of vnics and also the placement will depend on the blade mode, adapter
        # configuration/priority. We also need to collect all dependent priorities 
        # because list belonging to those dependent priorities may dictate need for creating
        # add'l vnics too.
        
        # Find logical id index of the test case column. Terminate if not found.

        logicalIdIndex = self.pcieGetFunctionLogicalIdIndex(pBlade, pHandle, pLogicalId, 1)

        if logicalIdIndex == None:
            printErr("Unable to find the logicalIdIndex. Exiting...")
            return EXIT_ERR

        # Fill the priorityDependencyList list. if empty return the empty list.

        pPriority = pPriority.strip()
        pHandle.seek(0)

        priorityDependencyList = self.pcieCollectAllDependentPriorities(pBlade, pHandle)

        printDbg("DependencyList: ", debug)
        printSeq(priorityDependencyList)

        if priorityDependencyList == None:
            printErr("no priority found. returning empty list.")
            return EXIT_ERR

        # For next, each iteration goes through test case column and creates vnics based on the placement obtained.
    
        printDbg("Creating test case specific vNICs", debug)

        pHandle.seek(0)

        while 1:
            line = pHandle.readline()
            printDbg("Line" + str(counter) + ":", debugL2)

            if not line:
                break

            currLine = line
            vnicPlacementNo = 0

            # if current line is priority line, then turn on the flag if priority is in priorityDependencyList

            if currLine.split()[0] != '-':
                priorityFlag = 0
                for currPriority in priorityDependencyList:
                    if currPriority == currLine.split()[0]:
                        printDbg("turning on priorityFlag upon seeing: " + currPriority, debug)
                        priorityFlag = 1    
                        break        # break for loop.                        

            # Create vnic if priorityFlag is on and non-priority line and testColumn is not X.

            if priorityFlag == 1 and currLine.split()[0] == '-' and currLine.split()[logicalIdIndex] != 'x' and currLine.split()[logicalIdIndex] != '-':
                vnicPlacementNo = currLine.split()[logicalIdIndex]
                printDbg("setting vnicPlacementNo to: " + str(vnicPlacementNo), debug)
            else:
                counter += 1   
                continue
                
            if vnicPlacementNo != 0:
                #ethName = "pcieVnic" + str(vnicPlacementNo)
                ethNames = []
                vNicIdxRange = range(0, pVnics)

                for k in vNicIdxRange:
                    ethNames.append("pcieVnic-" + str(vnicPlacementNo) + "-" + str(k))

                printDbg("setting ethNames to ", debug)
                print ethNames
                self.testVnics.append(ethNames)
            else:
                counter += 1
                continue

            printDbg("Found vnicPlacementNo | assigned vNicName ethNames: " + str(vnicPlacementNo) + " | " + str(ethNames), debug)

            for ethName in ethNames:
                ret = cli_with_ret(self.ucsmSsh, 'top', self.fiHostName)
                time.sleep(1)
                ret = cli_with_ret(self.ucsmSsh, 'scope org', self.fiHostName)
                time.sleep(1)
                ret = cli_with_ret(self.ucsmSsh, "scope service-profile " + pBlade.spName, self.fiHostName)
                time.sleep(1)
                ret = cli_with_ret(self.ucsmSsh, 'create vnic ' + ethName, self.fiHostName)
                time.sleep(1)
                ret = cli_with_ret(self.ucsmSsh, 'scope vnic ' + ethName, self.fiHostName)
                time.sleep(1)
                ret = cli_with_ret(self.ucsmSsh, 'set identity mac-pool default', self.fiHostName)
                time.sleep(1)
                ret = cli_with_ret(self.ucsmSsh, 'set vcon ' + vnicPlacementNo, self.fiHostName)
                time.sleep(1)
                ret = cli_with_ret(self.ucsmSsh, 'create eth-if default', self.fiHostName)
                time.sleep(1)
                ret = cli_with_ret(self.ucsmSsh, 'scope eth-if default', self.fiHostName)
                time.sleep(1)

                # if CONFIG_VNIC_INTERNET_VLAN is specified, then vlan other than default is need to be set
                # for access to corp/internet.
    
                vNicInternetVlan = str(getGlobal('CONFIG_VNIC_INTERNET_VLAN'))
    
                if vNicInternetVlan and vNicInternetVlan != 'default':
                    printDbg("creating additional eth-if " + str(vNicInternetVlan))
    
                    ret = cli_with_ret(self.ucsmSsh, 'create eth-if ' + vNicInternetVlan, self.fiHostName)
                    time.sleep(1)
                    ret = cli_with_ret(self.ucsmSsh, 'scope eth-if ' + vNicInternetVlan, self.fiHostName)
                    time.sleep(1)
        
                ret = cli_with_ret(self.ucsmSsh, 'set default-net yes', self.fiHostName)
                time.sleep(1)
                ret = cli_with_ret(self.ucsmSsh, 'commit', self.fiHostName)
                time.sleep(1)
                pcieVnics.append(ethName)
        
                counter += 1

        # All test pcie sp vnic-s are created at this point. Delete the dummy vnics and return the 
        # newly create pcie sp instant back to calling function.

        printDbg("TestVnics created: " + str(len(self.testVnics)), debug)
        printSeq(self.testVnics)

        # Delete dummy vnic now.

        printDbg("Deleting dummy vnic", debug)

        ret = cli_with_ret(self.ucsmSsh, 'top', self.fiHostName)
        time.sleep(1)
        ret = cli_with_ret(self.ucsmSsh, 'scope org', self.fiHostName)
        time.sleep(1)
        ret = cli_with_ret(self.ucsmSsh, "scope service-profile " + pBlade.spName, self.fiHostName)
        time.sleep(1)
        ret = cli_with_ret(self.ucsmSsh, 'delete vnic dummy', self.fiHostName)
        time.sleep(1)
        ret = cli_with_ret(self.ucsmSsh, 'commit', self.fiHostName)
        time.sleep(1)

        # Delete and re-create boot-policy with vnic name.

        printDbg("Deleting boot-policy " + pBlade.spName, debug)

        lFi2.mSp.delBootPolicy(pFi, pBlade.spName)
        lFi2.mSp.setBootPolicy(pFi, pBlade.spName, vNics[0])

        printDbg("Done setting up boot policy")

        # Change boot-policy.
        
        printDbg("Returning list of vnics created: ")
        printSeq(self.testVnics)
        
        return lFi2.mSp

    # This function is a wrapper function for pcieGetPcieFunctionList in that it calls
    # it pRetry number of times. 
    # req:      None
    # input:    pBlade    - blade instance.
    #           pFp       - file pointer to pcie-setting file.
    #           pRetry    - number of retries to make.
    # return    list of all functions obtained from pcie-setting file based on priority.
    #           EXIT_ERR if failed to obtain the functions list. 

    def pcieGetPcieFunctionListRetry(self, pFi, pFp, pRetry = 3):
        if validateFcnInput([pFi, pFi.mSp, pFi.mSp.mBlade, pFi.mSp.bmcSsh, pFp]) == EXIT_ERR:
            printErr("Input validation failed.")
            return EXIT_ERR

        for i in range(0, pRetry):
            stat = self.pcieGetPcieFunctionList(pFi, pFp)

            if stat:
                return stat

            printErr("failed to get function list. Retrying")

            bmcUser = getGlobal('CONFIG_BMC_LOGIN_USER')
            bmcPw = getGlobal('CONFIG_BMC_LOGIN_PW')
            pFi.mSp.bmcSsh  = sshReConnect(pFi.mSp.mBlade.bmcSsh, pFi.mSp.bmcSsh.args[3], bmcUser, bmcPw)

        printDbg("pcieGetPcieFunctionListRetry failed with " + str(pRetry) + " retries.")
        return EXIT_ERR 
    
    # This function returns pcie functions list for selected priority for given blade model.
    # req:      None
    # input:    pBlade    - blade instance.
    #           pFp       - file pointer to pcie-setting file.
    # return    list of all functions obtained from pcie-setting file based on priority.
    #           EXIT_ERR if failed to obtain the functions list. 

    def pcieGetPcieFunctionList(self, pFi, pFp):
        skipBlock = ""
        functionList = []
        lineTokens = []
        priorityDependencyList = []
        allPriorities = []
        busInfo = []

        debug = 0
        lineNo = 0
        foundPriority = 0
        foundPriority1 = 0
        foundMainPriority = 0

        line = ""
        currLine = ""

        pFp.seek(0)

        # collect all priorities including main priority and dependent priorities.
 
        printDbg("first iteration. Collecting all priorities", debug)

        priorityDependencyList = self.pcieCollectAllDependentPriorities(pFi.mSp, pFp)

        printDbg("DependencyList: " + str(priorityDependencyList), debug)

        if priorityDependencyList == None:            
            printErr("no priority found. returning empty list.")
            return EXIT_ERR

        # Do the second iteration for collecting pcie address for devices for all priorities.

        printDbg("doing the second iteration for dependency list priorities...", debug)

        pFp.seek(0)
        lineNo = 0
    
        while 1:
            line = pFp.readline()

            if not line:
                break
            currLine = line
            currPriority = currLine.split()[0]
        
            # If current priority does not march any of these in the priorityDependencyList, turn off the flag: foundPriority1.
            # First assume it is not found.
            # filter non-priority line
        
            if currPriority != "-":
                printDbg("currPriority: " + str(currPriority), debug)
                foundPriority1 = 0

                # For each priority in dependency list, see if current priority match any of them.

                printDbg("length of priorityDependencyList: " + str(len(priorityDependencyList)), debug)
                
                for i in range (0, len(priorityDependencyList)):
                    if currPriority  == priorityDependencyList[i]:
                        foundPriority1 = 1

                        printDbg("found matching priority in the dependency list:" + str(currPriority), debug)
                
                if not foundPriority1:
                    printDbg("foundPriority flag is set to 0, lineNo:  " + str(lineNo), debug)
                    foundPriority = 0 
                        
            # if priority flag is turned on, append the list

            if currPriority == "-":
                if foundPriority == 1:
                    pcieFunction = currLine.split()[2]
                    printDbg("appending PCIe device: " + str(pcieFunction), debug)

                    functionList.append(pcieFunction)

                    # If current function is marked as a pciBridge then add downstream devices
            
                    if currLine.split()[3] == "y" or currLine.split()[3] == "d":
                        printInfoToFile("-----------------------------------")
                        printInfoToFile("Enumerating the bridge: " + str(pcieFunction), debug)

                        busInfo = self.pcieBridgeGetBusNumbers(pFi, pcieFunction)
                        printInfoToFile("bus info: " + str(busInfo), debug)

                        stat = self.pcieEnumerateDownstreamDevices(pFi, busInfo, functionList)

                        if stat == EXIT_ERR:
                            printErr("can not enumerate bridge: " + str(pcieFunction))
                            return EXIT_ERR

            # set priority flag to 1 at the end of loop, since device numbers are 1 line below the priority line.
     
            if currPriority != "-":
                for i in range (0, len(priorityDependencyList)):
                    if currPriority == priorityDependencyList[i]:
                        if debug:
                            printDbg("foundPriority flag is set to 0 " +  str(lineNo), debug)

                        foundPriority = 1

            lineNo += 1

        if debug:
            printDbg("returning list (size): ", str(len(functionList)))
            printSeq(functionList, 10)
        return functionList                

    # This function returns the column index of test logicalId after scanning from pcie-setting file. 
    # The column index is used to gather the test data and flags related to that specific test 
    # defined by the logicalId.
    # req:      None
    # input:    pBlade    - blade instance.
    #           pHandle   - file pointer to pcie-setting file.
    #           pLogicalId - logical ID of test. 
    #           pFlag     - 0 if expected result is to be gathered, 1 if skipFlag is to be gathered.
    # return:   logicalIdIndex (column index) if success.
    #           EXIT_ERR if failed to obtain the column index (logicalIdIndex) based on logicalID

    def pcieGetFunctionLogicalIdIndex(self, pBlade, pHandle, pLogicalId, pFlag):

        firsline  = ""
        debug = 0
        logicalIdIndex = ""

        pHandle.seek(0)
        firstLine = pHandle.readline()

        if firstLine:        
            printDbg("firstLine / len: " + firstLine + str(len(firstLine.split())), debug)

            for i in range (4, len(firstLine.split())):
                printDbg("index:value " + str(i) + "/" + firstLine.split()[i], debug)
    
                if pLogicalId == firstLine.split()[i].strip():
                    printDbg("found matching logicalId at column: " + str(i))
             
                    logicalIdIndex = i
    
                    # get expected result if 0, testcase skipFlag if 1
                
                    if pFlag == 0:
                        logicalIdIndex += 1

                    break            
        else:
            printErr("Unable to read first line...")
            return EXIT_ERR

        if logicalIdIndex != "":
            printDbg("LogicalIdIndex found (grabbing the column from): " + str( logicalIdIndex))
        else:
            printErr("Failed to find logicalIdIndex for " + pLogicalId)
            return EXIT_ERR
    
        return logicalIdIndex

    # This function is a wrapper function of pcieGetPcieFunctionTestData in that it calls 
    # it pRetry of times. 
    # req:      None.
    # input:    pBlade      - blade instance.
    #           pHandle     - file pointer to pcie-setting file.
    #           pPriority   - priority.
    #           pLogicalId  - logical ID of test.
    #           pFlag       - specifies whether to return current expected result or PASS.
    #           pRetry      - number of tries. 
    # return    list of all functions obtained from pcie-setting file based on priority.
    #           EXIT_ERR if any error.
    #           - testData if success.

    def pcieGetPcieFunctionTestDataRetry(self, pFi, pFp, pPriority, pLogicalId, pFlag, pRetry = 3):
        for i in range(0, pRetry):
            stat = self.pcieGetPcieFunctionTestData(pFi, pFp, pPriority, pLogicalId, pFlag)
       
            if stat:
                return stat

            printErr("failed to get function list. Retrying")
            bmcUser = getGlobal('CONFIG_BMC_LOGIN_USER')
            bmcPw = getGlobal('CONFIG_BMC_LOGIN_PW')
            pFi.mSp.bmcSsh  = sshReConnect(pFi.mSp.mBlade.bmcSsh, pFi.mSp.bmcSsh.args[3], bmcUser, bmcPw)

        printDbg("pcieGetPcieFunctionTestDataRetry failed with " + str(pRetry) + " retries.")
        return EXIT_ERR 

    # This function returns the list of test case data back to caller.
    # Most of time it is an expected result list but can be a skipFlags.
    # req:      None.
    # input:    pBlade    - blade instance.
    #           pHandle   - file pointer to pcie-setting file.
    #           pPriority - priority.
    #           pLogicalId - logical ID of test.
    #           pFlag     - specifies whether to return current expected result or PASS.
    # return    list of all functions obtained from pcie-setting file based on priority.
    #           EXIT_ERR if any error.
    #           - testData if success.

    def pcieGetPcieFunctionTestData(self, pFi, pHandle, pPriority, pLogicalId, pFlag):
        skipBlock = 0
        functionList = []
        lineTokens = []
        priorityDependencyList = []
        debug = 0
        busInfo = []

        #printDbg("pHandle: " + str(pHandle), debug)
        printDbg("pLogicalId: " + str(pLogicalId), debug)
        printDbg("pPriority/len: " + str(pPriority) + "/" + str(len(pPriority)))
        printDbg("pFlag " + str(pFlag))
        
        lineNo = 0
        foundPriority = 0
        foundPriority1 = 1
        firstLine = ""
        logicalIdIndex = 0
        line = ""
        currLine = ""
        expectedResultList = []
       
        # Find the index of the column with value matching the logicalID. There expected to be only
        # one match otherwise it is an error condition.
        # Beware that currently the code does not check against this condition and will simply returns the first match!!!
 
        logicalIdIndex = self.pcieGetFunctionLogicalIdIndex(pFi.mSp.blade, pHandle, pLogicalId, pFlag)        
        pHandle.seek(0)
    
        if not logicalIdIndex:
            printErr("Cound not find test case " +  str(pLogicalId) + " in the setting file.")
            return EXIT_ERR

        # Collect all priorities.

        priorityDependencyList = self.pcieCollectAllDependentPriorities(pFi.mSp.blade, pHandle)

        if debug:
            printDbg("DependencyList: ")
            printSeq(priorityDependencyList)

        if priorityDependencyList == None:
            printDbg("No priority found, returning empty list", debug)
            return EXIT_ERR

        # read the pcie-setting file.

        pHandle.seek(0)
        lineNo = 0

        while 1:
            line = pHandle.readline()
            if not line:
                break
        
            currLine = line
            currPriority = currLine.split()[0]
        
            # if current priority does not match any of these in the priorityDependencyList, turn off the pFlag.
            # First assume it is not found

            if currPriority != "-":
                printDbg("CurrPriority " + currPriority, debug)
            
                foundPriority1 = 0

                for i in range (0, len(priorityDependencyList)):
                    if currPriority == priorityDependencyList[i]:
                        printDbg("Setting foundPriority1 flag to 1 at line" + str(lineNo), debug)    
                        foundPriority1 = 1
                   
                if not foundPriority1:
                    printDbg("setting foundPriority flag to 0 at line " + str(lineNo), debug)
            
                    foundPriority = 0

            # if priority flag is turned on, append the list.
         
            if currPriority == "-":
                if foundPriority1 == 1:
                    currResult = "" 

                    # if expected result is requested: if row line is '-' then expected
                    # result for current row(pcie function) is PASS
                    # If any other value, that value is the expected result.
            
                    if pFlag == 0: 
                        if currLine.split()[logicalIdIndex] != "-":
                            currResult = currLine.split()[logicalIdIndex]
                        else:
                            currResult = "PASS"

                    # if flag is set, then return whatever value is in the expected result column.
                    
                    elif  pFlag == 1:
                        currResult = currLine.split()[logicalIdIndex]
                    else:
                        printErr("pFlag must be either 0 or 1.")
                        return EXIT_ERR

                    printDbg("Appending to expectedResultList: " + currResult, debug)

                    expectedResultList.append(currResult)

                    # If current function is marked as a pciBridge then add downstream devices too.
                    # If current row is set to only 'y', then enumeration will happen. If it is set 
                    # other values, even though it is a pcie bridge, enumeration will not happen.
            
                    printDbg("Enumerating the bridge.", debug)

                    if currLine.split()[3] == "y":
                        busInfo = self.pcieBridgeGetBusNumbers(pFi, currLine.split()[2])

                        if self.pcieEnumerateDownstreamDevices(pFi, busInfo, expectedResultList, currResult) == None:
                            printErr("Error enumerating downstream devices")
                            return EXIT_ERR

            # Set priority flag to 1 to end of loop, since device numbers are 1 line below priority line
        
            if currPriority == "-":
                for i in range (0, len(priorityDependencyList)):
                    if currPriority == priorityDependencyList[i]:
                        if debug:
                            printDbg("P-found flag set to 1 at line "  + str(lineNo), debug)
                    
                        foundPriority = 1
            lineNo += 1

        # Set priority flag to 1 to end of loop, since device numbers are 1 line below priority line.

        if currPriority != "-":
            for i in range (0, len(priorityDependencyList)):
                if currPriority == priorityDependencyList[i]:
                    if debug:
                        printDbg("setting foundPriority flag to 1 at line " + str(lineNo), debug)
        
                    foundPriority = 1

        if pFlag == 0:
            printDbg("returning expectedResultList (size)" + str(len(expectedResultList)), debug)
        else:
            printDbg("returning flags (size): " + str(len(expectedResultList)), debug)

        printSeq(expectedResultList, 10)  

        return expectedResultList

    # This function will scan pcie-setting file and collect all dependent priorities based on the
    # main priority value.
    # req:      None
    # input:    pBlade    - blade instance.
    #           pFp       - file pointer for setting file.
    # return:   EXIT_ERR if failure to get the list for any reason.
    #           priority list (main + dependency) if successful.
    #           EXIT_ERR if failure.
    
    def pcieCollectAllDependentPriorities(self, pSp, pFp):
        priorityDependencyList = []
        foundMainPriority = ""
        line = ""
        currLine = ""
        currPriority = ""
        lineNo = 0
        debug = 0

        if pFp == None:
            printErr("File pointer is None.")
            return EXIT_ERR

        # read through each line and collect the priorities. 

        pFp.seek(0)
    
        while 1:
            line = pFp.readline()                               
            line = line.strip()

            if not line:
                break

            currLine = line
            printDbg("line: " + str(line), debug)
            currPriority = (currLine.split()[0]).strip()       

            # If current row's value is not '-', then it is a priority Line.
            # if priority line and its value is COMMON we collect, also if it is the 
            # requested priority also will collect.

            if currPriority != "-":                           
                printDbg("currPriority: " + str(currPriority), debug)

                # add common priorit to dependency list

                if currPriority == "COMMON":
                    printDbg("Adding common as priority...", debug)

                    priorityDependencyList.append("COMMON")

                # Check if it is main priority:

                if self.priority.lower() == currPriority.lower():
            
                    printDbg("found main priority: adding " + str(self.priority) + " to dependency list", debug)
                    foundMainPriority = 1
                
                    priorityDependencyList.append(self.priority)
                    
                    # If current line's 2nd column is not -, then current main priority has a dependency prioritie(s)
                    # separated by '/', add each of these to priority list.
    
                    if currLine.split()[1] != '-':
                        for j in range( 0, len( (currLine.split()[1]).split('/') ) ):
                            priorityDependencyList.append((currLine.split()[1]).split('/')[j])
                    
                            printDbg("adding " + str((currLine.split()[1]).split('/')[j]), debug)
                else:
                    printDbg("compare failed: priority: " + self.priority + " / currPriority: " + str(currPriority), debug)
                                                             
            lineNo += 1    
    
        # If main priority is not found return EXIT_ERR or return the priorities collected.

        if not foundMainPriority:
            printErr("Unable to find main priority, exiting...")
            return EXIT_ERR
        else:
            printDbg("priorities collected:\n " + str(priorityDependencyList))
            return priorityDependencyList    

    # This function will walk through pcie function's configuration space capability linked list
    # looking for specified capability based on the capability code (capCode).
    # req:      None
    # input:    pBlade  - blade instance.
    #           pcieFunction - pcie function from which to scan the capability and found the capability code.
    #           capCode - capability to search "NN" format for nonext cap, "NNNN" format for ext-d cap.
    #           pExtCap  - flag to indicate whether it is in extended capability.
    #           - 0 - not an extended capability
    #           - 1 - search for extended capability
    # return    value of NN (nonextCap) or NNNN (extCap) of register offset for capability register.
    #           EXIT_ERR - if any read error encountered.

    def pcieFindCapability(self, pFi, pcieFunction, capCode, pExtCap=0):
        pcieBdf = 0
        debug = 0
        rxNextCapOfs = ""
        rxNextCapOfsList = ""
        rxCapCode = ""    

        if validateFcnInput([pFi, pcieFunction, capCode]) == EXIT_ERR:
            printErr("Input validation failed.")
            return EXIT_ERR

        printDbg("Entered.")

        # Check whether it is extended capability search. If so, use 4 bytes instead of 2 bytes for reading capability code.

        if debug: 
            printDbg("pExtCap: " + str(pExtCap), debug)
            printDbg("(len(capCode)): " + str(len(capCode)), debug)

        if pExtCap == 0:
            if len(capCode) != 2:
                printErr("if pExtCap == 0, capCode must be 2 bytes in length")

        if pExtCap == 1:
            if len(capCode) != 4:
                printErr("if pExtCap == 1, capCode must be 4 bytes in length")
    
        # Read register 0x34, start of capability chain
        # in loop traverse through next capability till it is found.

        pcieBdf = pcieFunction.split('-')
    
        printDbg("looking for capability code " + str(capCode) + " from " + str(pcieFunction), debug)
    
        # Read the next capability register offset: conversion extract past: and into 0xNNN format.
        # capability register start from Rx34 which contains offset to next Cap register.
        # offset at the next cap register is as follows: 00-cap code 01-offset to next cap register.
    
        # For stdCap, Rx34 has pointer to next Cap, for pExtCap, Rx100 itself is nextCap, so read it only for
        # stdCap is specified. After rxNextCapOfs is set, we will have a nextOffset to start the loop.

        if pExtCap == 0:
            rxNextCapOfs = self.read_reg_byte(pFi.mSp, pcieFunction, "034") # should return NN
            rxNextCapOfs = "0" + rxNextCapOfs
        else:
            rxNextCapOfs = "100"

        if debug:    
            printDbg("first offset1: " + str(rxNextCapOfs), debug)
            
        # Loop by walking through the capabilities,
        #  unless value is 0x000 /end of capability/ or 0x0ff /non-existent function or register value/

        counter = 0
    
        while rxNextCapOfs != "000":                                            # 000 keep looping
            printDbg("loop Count: " + str(counter) + " rxNextCapOfs: " + str(rxNextCapOfs))
            if rxNextCapOfs.strip() == None or rxNextCapOfs.strip() == "":
                printErr("Failed to set rxNextCapOfs: " + str(rxNextCapOfs))
                return EXIT_ERR

            # Read capability code at current capability offset.

            if pExtCap == 0:    
                rxCapCode = self.read_reg_byte(pFi.mSp, pcieFunction, rxNextCapOfs) # should return NN
            else:
                rxCapCode = self.read_reg_word(pFi.mSp, pcieFunction, rxNextCapOfs) # should return NNNN
        
            if debug:
                printDbg("rxCapCode 1: " + str(rxCapCode), debug)
            
            # if match with the requested capability code, then return the offset of current capability.
            
            if rxCapCode.lower() == capCode.lower():
                printDbg("Found match at " + str(rxNextCapOfs), debug)
                return rxNextCapOfs
            
            # If no match, read next register to get nextCapability offset.
    
            if debug:
                printDbg("rxNextCapOfs preincrement: " + str(rxNextCapOfs), debug)
    
            rxNextCapOfsList = []

            try:            
                if pExtCap == 0:
                    rxNextCapOfs = "%03x" % (int(rxNextCapOfs, 16) + 0x01)
                else:
                    rxNextCapOfs = "%03x" % (int(rxNextCapOfs, 16) + 0x02)
            except Exception as msg:
                printErr("Error converting rxNextCapOfs to integer.")
                return EXIT_ERR            

            if debug:
                printDbg("rxNextCapOfs post-increment: " + str(rxNextCapOfs), debug)
    
            # Read the next capability code from the offset obtained and convert to 0xNNN format.
    
            if pExtCap == 0:
                rxNextCapVal = self.read_reg_byte(pFi.mSp, pcieFunction, rxNextCapOfs) # will return "NN" in hex.

                if rxNextCapVal.upper() == "FF":
                    return "00"

                rxNextCapOfs = "0" + rxNextCapVal
            else:
                rxNextCapVal = self.read_reg_word(pFi.mSp, pcieFunction, rxNextCapOfs) # will return "NNNN" in hex.

                if rxNextCapVal.upper() == "FFFF":
                    return "0000"

                rxNextCapOfs = rxNextCapVal[:3] # should return "123" if "1234" 

            counter += 1

            # By this time both normal and extended cap offset should have NNN format.

        # if reached here, then capability code was not foung during loop, so return 0.

        if debug:
            printErr("Finished loop, did not find the request Capability code " + str(capCode) + " in function: " + str(pcieFunction), debug)

            if pExtCap:
                printDbg("returning 0000", debug)
                return "0000"
            else:
                printDbg("returning 00", debug)
                return "00"

    # Enumerates any downstream devices given the bus information which contains secondary and subordinary buses.
    # The function has two purposes:
    # 1. Get the pcie device list if pSymbol is None (default).
    # 2. Get the same number of pSymbol list as if were called with pSymbol = None if pSymbol is not None.
    # Therefore, second purpose is for iterating over pcie device list but instead will return the same number of symbol list.
    # 
    # req:      None
    # input:    pBlade    - blade instance.
    #           pBusInfo  - bus info triple list contains primary, downstream and subordinate bus No-s to enumerate through.
    #           pDeviceList - pDeviceList to append the enumerated functions.
    #           pSymbol - if None, then iterate pcie device functions and add the pcie address
    #                   - if other values, iterate pcie device functions but add the symbols.
    # return    SUCCESS if enumeration is successful.
    #           EXIT_WARN - if no error, but did not enumerate and append any device.
    #           EXIT_ERR if any failure.

    def pcieEnumerateDownstreamDevices(self, pFi, pBusInfo, pDeviceList, pSymbol = None):
        rx00 = ""
        pcieFunction = ""
        debug = 0
        debugL2 = 0
        countEnum = None

        if pBusInfo == None:
            printErr("pBusInfo is None")
            return EXIT_ERR

        printDbg("Entry", debug)
        printDbg("pBusInfo: ", debug)
        printSeq(pBusInfo)

        if pBusInfo[1] == None or pBusInfo[2] == None:
            printErr("pBusInfo has invalid data: ")
            printSeq(pBusInfo)
            return EXIT_ERR

        try:
            int(pBusInfo[1], 16)
        except:
            printErr("pBusInfo[1] can not be converted to integer")
            return EXIT_ERR
    
        try:
            int(pBusInfo[2], 16)
        except:
            printErr("pBusInfo[2] can not be converted to integer")
            return EXIT_ERR

        #if pSp.mBlade.bootEfiShell(self.ucsmSsh, self.bmcSsh) == EXIT_ERR:
        #if pFi.mSp.mBlade.bootEfiShell(pFi.ucsmSsh, pFi.mSp.bmcSsh) == EXIT_ERR:

        if pFi.mSp.bootEfiShellThruBp(pFi) == EXIT_ERR:
            printErr("Failed to boot to efi shell..")
            return EXIT_ERR

        countEnum = 0

        # Enumerate all devices and functions between secondary and subordinate bus-s.
        # Each device has 256 functions but in this case, we scan only up to 8 functions
        # per device for practicality. 

        for currentBus in range( int(pBusInfo[1], 16), int(pBusInfo[2], 16)+1 ):
            printDbg("(2) Enumerating bus: " + str(hex(currentBus)), debug)
            for currentDev in range(0, 8):
                for currentFnc in range(0, 16): # must be 255 but will do 32 for now!!!!

                    try:
                        #pcieFunction = "-".join(("{:02x}".format(currentBus), "{:02x}".format(currentDev), "{:02x}".format(currentFnc)))
                        pcieFunction = "-".join(( "%02x" % (currentBus),  "%02x" % (currentDev), "%02x" % (currentFnc) ))
                 
                    except Exception as msg:
                        printDbg("Can not join currentBus, currentDev, currentFnc: " + str(currentBus) + ":" + \
                            str(currentDev) + ":" + str(currentFnc) + ", continuing...", debugL2)
                        continue

                    printDbg("pcieFunction: " + str(pcieFunction), debug)

                    # If vid/did is valid, then add to the deviceList otherwise move on to next pcie device.

                    rx00 = self.read_reg_dword(pFi.mSp, pcieFunction, "000")

                    if rx00 == EXIT_ERR:
                        printErr("Unable to read the rx value for " + str(pcieFunction) + ", leaving.")
                        return EXIT_ERR
                    if rx00 == "FFFFFFFF":
                        break
                    else:
                        printDbg("VID/DID valid for pcie Bus/dev/fnc: " + str(pcieFunction) + ": " + str(rx00), debug)

                        if pSymbol == None:
                            printDbg("Appending downstream PCIe device: " + str(pcieFunction))
                            pDeviceList.append(pcieFunction)
                            printDbg("Inserting downstream device: " + pcieFunction, debug)
                        else:
                            printDbg("Appending result " + str(pSymbol) + " for " + str(pcieFunction))
                            pDeviceList.append(pSymbol)
                        countEnum += 1

        # if countEnum is zero, then nothing has been enumarated.

        if countEnum == 0:
            printWarn(str(pBusInfo) + ": No devices found downstream of this bridge during enumeration.")
            return EXIT_WARN

        return SUCCESS        

    # This function tests the specific pcieFunction to see whose classcodes match the classCode parameter passed onto it.
    # req:  None
    # input:    pBlade    - blade instance.
    #           pcieFunction - pcie function address
    #           pClassCodeName - classCode to match, must be in 0xNN format.
    # return    SUCCESS - if classCode match
    #           EXIT_ERR if not.

    def pcieIsClassCode(self, pFi, pcieFunction, pClassCodeName):
        debug = 0
        classCode = ""

        # Verify class code is in hex 0xNN format.

        if re.search('x', pClassCodeName) == None:
            printErr("pClassCodeName must be in NxNN format.")

        # boot to efi Shell. 

        #if pFi.mSp.mBlade.bootEfiShell(self.ucsmSsh, pFi.mSp.bmcSsh) == EXIT_ERR:

        if pFi.mSp.bootEfiShellThruBp(pFi) == EXIT_ERR:
            printErr("Failed to boot to efi shell.")
            return EXIT_ERR

        # Get the class code from the pcie function.

        classCode = self.read_reg_byte(pFi.mSp, pcieFunction, "00b")
        pClassCodeName = pClassCodeName.split('x')[1]

        # Compare the class code and return the appropriate return value based on compare result.

        if pClassCodeName == classCode:
            printDbg(str(pcieFunction) + " is match: " + str(pClassCodeName) + " : " + str(classCode), debug)
            return SUCCESS
        else:
            printDbg("class code mismatch(classCode expected|classCode read): " + str(pClassCodeName) + " : "  + str(classCode))
            return EXIT_ERR

    # All pcie read_reg_dword/word/byte function take following format:
    # read_reg_dword/word/byte(self, pBlade, "BB-DD-FF", RRR)
    # return format for read_reg_dword/word/byte is NNNNNNNN, NNNN, NN respectively in hex.
    # req:      None
    # input:    server - blade object instance.
    #           pcie_address - address of pcie device to read in "BB-DD-FF" format.
    #           pcie_reg - register No. to read in "RRR" format.
    # return:   NNNNNNNN, NNNN, NN in hex for read value.
    #           EXIT_ERR on error.

    def read_reg_dword(self, pSp, pcie_address, pcie_reg):
        debug = 1

        printVars([pcie_address, pcie_reg])

        # Check for alignment:
        # if 0 4 8 read dword and return immediately.
        # if 1 5 9 read dword1=pcie_reg-1 dword2+dword1+4 and return dword[1:3] dword[0]
        # if 2 6 10 read dword1 dword2 and return dword[2:3] dword[0:1]
        # if 3 7 11 read dword1 dword2 and return dword[3] dword[0:2]

        rem = int(pcie_reg,16) % 4

        if rem  == 0:
            printDbg("dword aligned OK.", debug)
            outp = self.read_reg(pSp, pcie_address, pcie_reg, "4")
            return outp

        pcie_reg1 = str(hex(int(pcie_reg, 16) - rem))[2:]
        pcie_reg2 = str(hex(int(pcie_reg1, 16) + 4))[2:]
        printDbg("pcie_reg1: " + str(pcie_reg1), debug)
        printDbg("pcie_reg2: " + str(pcie_reg2), debug)
    
        if rem != 0:
            printDbg("dword misalign by 1.", debug)
            outp1 = self.read_reg(pSp, pcie_address, pcie_reg1, "4")
            outp2 = self.read_reg(pSp, pcie_address, pcie_reg2, "4")
            printDbg("Returning: " + str(outp1[2:]) + str(outp2[:1]))
            return str(outp1[2:]) + str(outp2[:1])

        if rem == 1:
            printDbg("dword misalign by 1.", debug)
            outp = self.read_reg(pSp, pcie_address, pcie_reg, "4")
            outp2 = self.read_reg(pSp, pcie_address, pcie_reg2, "4")
            printDbg("Returning: " + str(outp[2:]) + str(outp2[:1]))
            return str(outp[2:]) + str(outp2[:1])

        if rem  == 2:
            printDbg("dword misalign by 2.", debug)
            pcie_reg = str(hex(int(pcie_reg, 16) - 2))[2:]
            outp = self.read_reg(pSp, pcie_address, pcie_reg, "4")
            outp2 = self.read_reg(pSp, pcie_address, pcie_reg2, "4")
            printDbg("Returning: " + str(outp[2:]) + str(outp2[:1]))
            return str(outp[4:]) + str(outp2[:3])

        if rem  == 3:
            printDbg("dword misalign by 3.", debug)
            pcie_reg = str(hex(int(pcie_reg, 16) - 3))[2:]
            outp = self.read_reg(pSp, pcie_address, pcie_reg, "4")
            outp2 = self.read_reg(pSp, pcie_address, pcie_reg2, "4")
            printDbg("Returning: " + str(outp[2:]) + str(outp2[:1]))
            return str(outp[6:]) + str(outp2[:5])

    def read_reg_word(self, pSp, pcie_address, pcie_reg):
        outp = self.read_reg(pSp, pcie_address, pcie_reg, "2")
        return outp

    def read_reg_byte(self, pSp, pcie_address, pcie_reg):
        outp = self.read_reg(pSp, pcie_address, pcie_reg, "1")
        return outp

    def read_reg(self, pSp, pcie_address, pcie_reg, pSize, pReconn = 1):
        debug = 0
        counter = 0
        pUcsmSsh = None
        lBmcSsh = None

        if validateFcnInput([pSp.bmcSsh, pcie_address, pcie_reg, pSize]) == EXIT_ERR:
            printErr("Input validation failed.")
            return EXIT_ERR

        self.read_cmd = ("mm -pcie 0", re.sub('-','', pcie_address), pcie_reg, " -w ", str(pSize) ," -n")
        self.read_cmd_string = "".join(self.read_cmd)
        printDbg("command string: " + str(self.read_cmd_string), debug)

        while 1:
            outp = cli_with_ret(pSp.bmcSsh, self.read_cmd_string, "", "efiShell")
            time.sleep(1)

            # if cli command output is error, try rebooting the blade and reconnecting to bmc.

            # The read_reg function is so frequently used, we want this to be stable.
            # if cli_with_ret call above is resulted in error, would like to retry few times.

            if outp == EXIT_ERR or outp == EXIT_ERR_NO_PROMPT:

                printErr("Failed to read pcie address.")
                return EXIT_ERR

                '''
                # Reconnect to bmc.
                
                printErr("Unable to read. Retry by re-connecting bmc.")

                bmcUser = getGlobal('CONFIG_BMC_LOGIN_USER')
                bmcPw = getGlobal('CONFIG_BMC_LOGIN_PW')
        
                try:
                    self.bmcSsh = sshLogin(self.bmcSsh.args[3], bmcUser, bmcPw)
                except AttributeError:
                    printErr("Attrib error. self.bmccSsh might not have been initialized.")

                # Reset the blade.

                fiMgmtIp = getGlobalTmp("fi-mgmt-ip")

                # Setting fi management user and password as hardcoded. This is not a good practice!
                # Consider putting into config file!!!!

                fiUser = "admin"
                fiPassword = "Nbv12345"

                if fiMgmtIp != EXIT_ERR:
                    pUcsmSsh = sshLogin(fiMgmtIp, fiUser, fiPassword)
    
                    if pUcsmSsh:
                        #if  pSp.mBlade.bootEfiShell(pUcsmSsh, self.bmcSsh) == EXIT_ERR:
                        if pFi.mSp.bootEfiShellThruBp(pFi) == EXIT_ERR:
                            printErr("Failed to boot to efi shell.")
                            return EXIT_ERR
                    else:
                        printErr("reset server is unssucessful because unable to get ucsm ssh login working")
                        return EXIT_ERR
                else:
                    printErr("reset server is unssucessful because unable to get ucsm ssh login working")
                    return EXIT_ERR
    
                counter += 1

                if counter >= 2:
                    printErr("Retry exhausted")
                    return EXIT_ERR
                '''
            else:

                ''' 
                not sure of this.??? KEEP IT FOR A WHILE and after some time, if not needed, delete it. 
                if re.search("mm:", outp):
                    printWarn("Retry with reboot, counter: " + str(counter) + ". Unable to execute. Command: " + str(self.read_cmd_string))
                    counter += 1

                    #if server.bootEfiShell(pUcsmSsh, self.bmcSsh) == EXIT_ERR:
                    if pFi.mSp.bootEfiShellThruBp(pFi) == EXIT_ERR:                   
                        printErr("Failed to boot to efi shell.")
                        return EXIT_ERR

                    if counter >= 3:
                        printErr("Retry exhausted executing " + str(self.read_cmd_string))
                        return None
                else:
                '''
                printDbg("outp(1): " + str(outp), debug)
                outp = str(outp).strip()
                printDbg("outp(2): " + str(outp), debug)
                outpref = outp[-int(pSize)*2:]
                printDbg("outp(3): " + str(outp), debug)
                return outpref
    
    # All read_mem_dword/word/byte function take following format:
    # read_mem_dword/word/byte(self, pBlade, "", address)
    # It supported both dword aligned and non-aligned address read.
    # req:      None
    # input:    server - blade object instance.
    #           address - address of memory to read.
    # return:   NNNNNNNN, NNNN, NN in hex format for read value.
    #           the data type for return is <str> although appearance format is hex.
    #           To parse to integer, caller of the function should be perform int(<return>, 16).
    #           EXIT_ERR on error.

    def read_mem_dword(self, server, address):
        debug = 0
        lIntAddress = None
        outp = None
        outp1 = None
        outp2 = None

        # Convert to integer.

        lIntAddress = int(address, 16)

        # For dword-aligned read.

        if lIntAddress & 0x03 == 0x00:
            printDbg("dword aligned read, returning " + str(outp1), debug)
            outp1 = self.read_mem(server, address, "4")
            return outp1
        else:

            # For non-dword aligned read, more processing needed.
            # First normalize the address to dword aligned and perform two subsequent reads:
            # normalized address + normalized address + 4

            printDbg("non-dword aligned read.", debug)

            lIntAddressAlign = hex(lIntAddress & 0xfffffffc)
            address2 = hex(int(lIntAddressAlign, 16) + 4)

            printDbg("address2, second read: "  + str(address2), debug)

            outp1 = self.read_mem(server, lIntAddressAlign, "4")
            outp2 = self.read_mem(server, address2, "4")

            printDbg("outp1, outp2: " + str(outp1) + ":" + str(outp2), debug)
            
            # Based on the mis-alignment, grab the appropriate bytes from two subsequent reads.

            if lIntAddress & 0x03 == 0x01:
                outp = outp1[2:] + outp2[:2]
            elif lIntAddress & 0x03 == 0x02:
                outp = outp1[4:] + outp2[:4]
            elif lIntAddress & 0x03 == 0x03:
                outp = outp1[6:] + outp2[:6]
            else:
                printErr("unknown non-dword aligned value. Not sure what to do: " + str(lIntAddress & 0x03))
                return EXIT_ERR

            printDbg("returning non-dword aligned value: " + str(outp), debug)

        return outp

    def read_mem_word(self, server, address):

        # To supported non-word aligned read, simply perform two subsequent read_mem_byte 
        # and return the concatenation of return values.

        debug = 0
        intAddress = int(address, 16)
        outp1 = self.read_mem_byte(server, address)
        printDbg("outp1: " + str(outp1), debug)
        outp2 = self.read_mem_byte(server, str(hex(int(address, 16) + 1)))
        printDbg("outp2: " + str(outp2), debug)
        outp = outp2 + outp1
        printDbg("return value: " + str(outp), debug)
        return outp

    def read_mem_byte(self, server, address):
        debug = 0
        printDbg("entry, address: " + str(address), debug)

        # Align the address on 4-byte boundary and determine the mis-alignment value.

        lIntAddress = int(address, 16) & 0xfffffffc
        lIntMisAlign = int(address, 16) & 0x3

        printDbg("lIntAddress, lIntMisAlign: " + str(hex(lIntAddress)) + ", " + str(hex(lIntMisAlign)), debug)

        # Read the dword aligned address. Once that is obtained, shift  8 bits times misAlignment value to 
        # obtain the proper byte. Do * 0xff to filter out the rest of bits. 

        address = str(hex(lIntAddress)).split('x')[-1]
        outp = self.read_mem_dword(server, address)
        lOutp = int(outp, 16) >> lIntMisAlign * 8
        lOutp = lOutp & 0xff

        printDbg("lOutp: " + str( "%02x" % lOutp ), debug)

        outp = str("%02x" % lOutp)
        return outp

    #   Helper function for all of following functions: read_mem_dword/word/byte(self, pBlade, "", address)
    #   req:    None
    #   input:  server - blade object instance.
    #           address - address of memory to read.
    #           pSize - size of memory read.
    #   return: NNNNNNNN in hex format for read value.
    #           the data type for return is <str> although appearance format is hex.
    #           To parse to integer, caller of the function should be perform int(<return>, 16).
    #           EXIT_ERR on error.

    def read_mem(self, server, address, pSize):
        time.sleep(1)
        debug = 0

        # Construct the command.

        self.read_cmd = ("mm -MEM ", str(address), " -w 4 -n")
        self.read_cmd_string = "".join(self.read_cmd)

        printDbg("command string: " + str(self.read_cmd_string), debug)

        # Send to efi shell terminal.

        outp = cli_with_ret(self.bmcSsh, self.read_cmd_string, "", "efiShell")

        if outp:
            printDbg("outp(1): " + str(outp), debug)
    
            if re.search("Too few arguments", outp):
                printErr("Error sending command or getting result.")
                return EXIT_ERR
        else:
            printErr("outp is None")
            return EXIT_ERR

        # Start removing garbages and filter only the desired hex digits. 

        outp = str(outp).strip()
        printDbg("outp(2): " + str(outp), debug)

#       outpref = outp[-int(pSize)*2:] # This does not work out on M5. Below is perhaps more robust solution 
#       However needs to be thoroughly tested for backward compatibility on M4 or before blades.

        outpref = outp.split(' ')[-1].split('x')[-1].strip()
        outpref = outpref[0:8]
        printDbg("outpref|len: " + str(outpref) + " : " + str(len(outpref)), debug)
        return outpref

    # Finds the primary, secondary and subordinate busses for the pciBridge device.
    # req:  None
    # input:    pBlade - blade instance
    #           pPciBridge - pcie bridge whose secondary and subordinate bus numbers are to be returned.
    #           pReConn - if reconnection to SOL is needed (default=yes).
    # return    list containing primary, secondary and subordinate busses.
    #           EXIT_ERR: for any error.

    def pcieBridgeGetBusNumbers(self, pFi, pPciBridge, pReconn = 1):
        debug = 0
        range1 = ['','','']
        CONFIG_RETRY_READ = 1

        printDbg("entry...", debug)

        if validateFcnInput([pFi, pFi.mSp, pFi.mSp.mBlade, pFi.mSp.bmcSsh]) == EXIT_ERR:
            printErr("Input validation failed.")
            return EXIT_ERR
        
        print type(range1)

        # Boot to efi shell.

        if pFi.mSp.bootEfiShellThruBp(pFi) == EXIT_ERR:
            printErr("Failed to boot to efi shell.")
            return EXIT_ERR

        counter = 0

        # Start reading the pcie config rx for primary, secondary and subordinate busses.
        # This is frequently used function, therefore we need to try at least 5 attemps
        # in case read is not successful before giving up.

        for i in range(0, CONFIG_RETRY_READ):
            printDbg("bus No. read loop No. " + str(i), debug)
            range1[0] = self.read_reg_byte(pFi.mSp, pPciBridge, "018")
            range1[1] = self.read_reg_byte(pFi.mSp, pPciBridge, "019")
            range1[2] = self.read_reg_byte(pFi.mSp, pPciBridge, "01a")
            printDbg("Done reading bus No.-s for loop " + str(i), debug)
    
            try:
                int(range1[0], 16)
                int(range1[1], 16)
                int(range1[2], 16)
            except (ValueError, NameError, TypeError):
                for i in sys.exc_info():
                    print i
                printErr("Unable to read the bus numbers retry No. " + str(counter))
                print range1
                range1 = ['','','']
                printDbg("bus range after reset: ", debug)
                print range1
                counter += 1
                
                if counter > CONFIG_RETRY_READ:
                    printErr("Unable to read the bus numbers for 5 times, giving up.")
                    return EXIT_ERR 
                continue 
            break
    
        printDbg("Range found: primary, seconday and subordinate: ", debug)

        if debug:
            print type(range1)
            printSeq(range1)
        return range1
        
