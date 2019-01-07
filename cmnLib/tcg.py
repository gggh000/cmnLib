import time
from security import *
from saLibrary import *
import saLibrary
import re
import math
import collections

txtConfigRxSpace =  0xfed30000
txtPublicSpace =    0xfed30000
txtPrivateSpace =   0xfed20000
txtDeviceSpace =    0xfed40000
fitPointer =        0xffffffc0
loc0 = 0xfed40000
loc1 = 0xfed41000
loc2 = 0xfed42000
loc3 = 0xfed43000
loc4 = 0xfed44000

#   Returns the register definions for TXT BIOSACM errorcode. This is conditional format based on the value
#   of TXT.ACM_STATUS[62][61] registers.
#   For more information, refer to TXT_BootGuard_BIOS_Spec_558294_rev2 p103 Table A-13/14.

#   input:
#   pAcmStatus - TXT ACM status value. 
#   if TXT.ACM_STATUS[62] = 1 returns Table A-13 register sets - Intel TXT has uCode or ACM error during startup.
#   if TXT.ACM_STATUS[61] = 1 returns Table A-14 register sets - Indicates that a bootGuard error has occurred.
#   Format: NNNN, where each N is a hex value.

#   return:
#   pBlade - blade instant.
#   pPcie_inst - pcie reader instant.
#   EXIT_ERR - in any error condition.

def getTxtRegistersErrorCode328h(pFi, pPcieInst, pAcmStatus61h, pAcmStatus62h):

    if pAcmStatus61h == None and pAcmStatus62h == None:
        printErr("Both ACM status bit 61 and 62 are None.")
        return EXIT_ERR

    if pAcmStatus61h >= 1and pAcmStatus62h <= 1:
        printErr("Both ACM status bit 61 and 62 are 1 or above .")
        return EXIT_ERR

#   lTxtErrorCodeDict = {}
    lTxtErrorCodeDict = collections.OrderedDict()
    
    # Construct struct in case of Intel TXT ucode or ACM during startup.

    if pAcmStatus62h:
        printDbg("BIT62 is set, returning A-13 table.")

        txtRxErrCode328hBitSizes = \
        [4, 5, 5, 1, 9, 1, 1]

        txtRxErrCode328hBitOffsets = \
        [0, 4, 10, 15, 16, 30, 31 ]
        
        txtRxErrCode328hRxOffsets = \
        [328, 328, 328, 328, 328, 328, 328\
        ]

        txtRxErrCode328hRxNames = \
        [
        "AC module type", \
        "Class Error", \
        "Major Error Code", \
        "Minor Error Code/Progress Code Invalid", \
        "Minor Error Code and Progress Code", \
        "External", \
        "Valid"
        ]

    # Construct struct in case of bootGuard Error.
            
    elif pAcmStatus61h:
        printDbg("BIT61 is set, returning A-14 table.")

        txtRxErrCode328hBitSizes = \
        [4, 5, 5, 1, 9, 1, 1]

        txtRxErrCode328hBitOffsets = \
        [0, 4, 10, 15, 16, 30, 31 ]
        
        txtRxErrCode328hRxOffsets = \
        [328, 328, 328, 328, 328, 328, 328\
        ]

        txtRxErrCode328hRxNames = \
        [
        "AC module type", \
        "Class Error", \
        "Major Error Code", \
        "Minor Error Code/Progress Code Invalid", \
        "Minor Error Code and Progress Code", \
        "External", \
        "Valid"
        ]
            
    else:
        printErr("Unsupported pAcmStatus input value: " + str(pAcmStatus))
        return EXIT_ERR

    lTxtErrCodeDict = getHelpMmioRegisters(\
        pFi,\
        txtRxErrCode328hBitSizes, \
        txtRxErrCode328hBitOffsets, \
        txtRxErrCode328hRxOffsets, \
        txtRxErrCode328hRxNames, \
        pPcieInst)

    return lTxtErrCodeDict

#   Returns well-known TXT registers and their status in iterarable format.

#   input: 
#   pBlade - blade instant.
#   pPcie_inst - pcie reader instant.

#   return:
#   dictionary containing the key: name of register and value: current value of registers.

def getTxtRegisters(pFi, pPcieInst):
    debug = 0
    counter = None
    lTxtDict = collections.OrderedDict()
    lTxtDictRx = collections.OrderedDict()
    
    txtRxBitSizes = \
    [1, 1, 1, 1, 1, 1,\
    0,\
    1, 1, 1,\
    8, 1, 1, 1, 1, 1,\
    1,\
    16, 16, 16, 16,\
    1,\
    32,\
    32,\
    32,\
    32,\
    32,\
    1, 9, 11,\
    255,\
    1,\
    ]

    txtRxBitOffsets = \
    [0, 1, 6, 7, 15, 16,\
    0,\
    15, 30, 31,\
    0, 59, 60, 61, 62, 63,\
    31,\
    0, 16, 32, 48,\
    31,\
    0,\
    0,\
    0,\
    0,\
    0,\
    0, 4, 20,\
    0,\
    1,\
    ]

    txtRxOffsets = \
    [0, 0, 0, 0, 0, 0, \
    8,\
    0x30, 0x30, 0x30,\
    0x0a0, 0x0a0, 0x0a0, 0x0a0, 0x0a0, 0x0a0, \
    0x100,\
    0x110, 0x110, 0x110, 0x110,\
    0x200,\
    0X218,\
    0x278,\
    0x290,\
    0x300,\
    0x308,\
    0x330, 0x330, 0x330,\
    0x400,\
    0x8f0,\
    ]

    txtRxNames = [\
    "TXT.STS.SENTER.DONE.STS",\
    "TXT.STS.SEXIT.DONE.STS",\
    "TXT.STS.MEM-CONFIG-LOCK.STS",\
    "TXT.STS.PRIVATE-OPEN.STS",\
    "TXT.STS.LOCALITY1.OPEN.STS",\
    "TXT.STS.LOCALITY2.OPEN.STS",\
    
    "TXT.ESTS.TXT_RESET.STS",\
    
    "TXT.ERRORCODE.Sw.source: 0=ACM, 1=MLE",\
    "TXT.ERRORCODE.Error.cause: CPU=0, software=1",\
    "TXT.ERRORCODE.Error.Validity: Invalid=0, Valid=1",\

    "TXT.ACMSTATUS.BIOS-ACM-lockConfig-CPU-No",\
    "TXT.ACMSTATUS.BIOS-trusted, 1=Y, 0=N",\
    "TXT.ACMSTATUS.TXT-dis-by-TXT-policy",\
    "TXT.ACMSTATUS.bTg-start-Error-occurred",\
    "TXT.ACMSTATUS.TXT-uCode-or-ACM-error-occurred",\
    "TXT.ACMSTATUS.TXT-meas-of-type7-or-IBB-measurement-occurred",\
    
    "TXT.VER.FSBIF: chipset is debug fused=0, prod fused=1",\

    "TXT.DIDVID.VID",\
    "TXT.DIDVID.DID",\
    "TXT.DIDVID.RID",\
    "TXT.DIDVID.ID-EXT",\

    "TXT.VER.QPIIF: chipset is debug fused=0, prod fused=1",\

    "TXT.SINIT.BASE",\

    "TXT.SINIT.SIZE",\

    "TXT.MLE.JOIN.BASE",\

    "TXT.HEAP.BASE",\

    "TXT.HEAP.SIZE",\

    "TXT.DPR(DMA-protected-range).Lock(bit19:0)",\
    "TXT.DPR(DMA-protected-range).Size",\
    "TXT.DPR(DMA-protected-range).Top",\

    "TXT.PUBLIC.KEY",\

    "TXT.E2STS.0=nosecret, 1=secret in mem."\
    ]

    lTxtDict = getHelpMmioRegisters(\
        pFi,\
        txtRxBitSizes, \
        txtRxBitOffsets, \
        txtRxOffsets, \
        txtRxNames, \
        pPcieInst)
    return lTxtDict

#   Helper function for returning the dictionary built by reading the 4 register parameters.
#   Used by functions that reads MMIO registers: getTxtRegisters, getTxtRegistersErrorCode328h.

#   Format guidelines:
#   <nameSet>BitSizes - sizes of bits field that are being iterated. If those bits belong to one register offset
#   it is written in one line to improve readibility. If multiple bits cross Register offsets, write it in the same line
#   in which the bits of same registers are written. This format should not affect any functionality, it is purely
#   for readbility.

#   <nameSet>BitOffsets - Offsets of each bits. Each one of them should correspond to <nameSet>BitSizes. 
#   <nameSet>RxOffsets - Register offsets. 
#   <nameSet>txtRxNames - Literal names of registers.

#   input:
#   pRxBitSize - bit size list.
#   pRxBitOffsets - bit offset list.
#   pRxOffsets - register offset list.
#   pRxNames - register name list. 

#   return:
#   dictionary containing the key: name of register and value: current value of registers.

def getHelpMmioRegisters(pFi, pRxBitSizes, pRxBitOffsets, pRxOffsets, pRxNames, pPcieInst, pBaseAddr = txtPublicSpace):
    debug = 1

    lTxtDict = collections.OrderedDict()
    lTxtDictRx = collections.OrderedDict()

    if debug:
        printBarSingle()
        print len(pRxBitSizes), ": ", pRxBitSizes
        printBarSingle()
        print len(pRxBitOffsets), ": ", pRxBitOffsets
        printBarSingle()
        print len(pRxOffsets), ": ", pRxOffsets
        printBarSingle()
        print len(pRxNames), ": ", pRxNames
        printBarSingle()

    printWarn("If registers are more than 32-bit long, any bits over 32-bits are discarded due to \
    limited supported for mem read operation. Future implementation may support up to 256-bit read.")

    # Iterate over each register and use a read mem operation to get register value.
    # Use Bit offsets and Bit sizes to get the actual field values.

    minAll = min(pRxNames, pRxOffsets, pRxBitOffsets, pRxBitSizes)

    for i in range(0, len(minAll)):
        if debug:
            printBarSingle()

        printDbg("iteration: " + str(i) + " for " + str(pRxNames[i]), debug)
        rxValue = pPcieInst.read_mem_dword(pFi.mSp.mBlade, hex(pRxOffsets[i] + pBaseAddr).split('x')[-1])
        printDbg("rxValue read: " + str(rxValue), debug)
        printDbg("bit offsets(shift), bit sizes(AND mask): " + str(pRxBitOffsets[i]) + ", " + str(pRxBitSizes[i]))
            
        printDbg("AND mask: " + str(hex(min(0xffffffff, int(math.pow(2, pRxBitSizes[i])-1)))), debug)
        rxValue = int(rxValue, 16) >> pRxBitOffsets[i] & ( int(  min(0xffffffff, math.pow(2, pRxBitSizes[i])-1)  ) )

        printDbg("rxValue after bitshift: " + str(hex(rxValue)), debug)

        dicKeyName = "R"+str(hex(pRxOffsets[i])) + "["+str(hex(pRxBitOffsets[i]))[2:]+":"+\
            str(hex(pRxBitOffsets[i]+pRxBitSizes[i]))[2:] + "]"
        printDbg("dicKeyName: " + dicKeyName)

        lTxtDict[pRxNames[i]] = rxValue
        lTxtDictRx[pRxNames[i]] = dicKeyName

        printBarSingle()
        print len(lTxtDict), ": ", lTxtDict
        printBarSingle()
        print len(lTxtDictRx), ": ", lTxtDictRx

    for i in range(0, len(minAll)):
        printDbg(str(pRxNames[i]).ljust(60) + ": " + str(lTxtDictRx[pRxNames[i]]).ljust(20) + ", "+ str(hex(lTxtDict[pRxNames[i]])))

    return [lTxtDict, lTxtDictRx, pRxNames]

#   Return FIT (firmware interface table) entry for the blade under test.
#   Typical FIT entries include uCode, ACM, BootGuard and others.
#
#   input:
#   pPcie_inst - pcie_inst which holds ssh connection.
#   pBlade - blade instance which holds server info
#   pType - type of FIT entry found.
#
#   return:
#   <list>:<int> - memory address of fit entry if found multiples times or one time.
#   EXIT_ERR - if not found or any other error.

def getFitEntry(pBlade, pPcie_inst, pType):
    debug = 0
    fitSize = None
    fitAddress = None
    fitAddressesFound = []
    i = 0

    if validateFcnInput([pType]) == EXIT_ERR:
        printErr("Input validation has failed.")
        return EXIT_ERR

    # Get FIT address from FIT fixed pointer.

    fitAddress = pPcie_inst.read_mem_dword(pBlade, hex(fitPointer).split('x')[-1])

    if fitAddress:
        printDbg("FIT address: " + str(fitAddress))
    else:
        printErr("Unable to obtain FIT address.")
        return EXIT_ERR

    printDbg("Obtaining FIT size...", debug)

    fitSizeAddress = str(hex(int(fitAddress, 16) + 8))
    printDbg("fitSizeAddress: " + str(fitSizeAddress), debug)
    fitSize = pPcie_inst.read_mem_byte(pBlade, fitSizeAddress)

    if fitSize:
        printDbg("FIT size (no. of entries in FIT: " + str(fitSize))
    else:
        printErr("Unable to obtain FIT size.")

    fitAddressWalker = fitAddress
    fitTypeWalker = fitAddressWalker

    for i in range(0, int(fitSize, 16)):
        if debug:
            printBarSingle()

        printDbg("\nIteration: " + str(i), debug)
        fitAddressWalker = hex(int(fitAddressWalker, 16) + 16)          # walk to next entry.
        fitTypeWalker = hex(int(fitAddressWalker, 16) + 14)             # increment by 14 to get to type field.

        fitEntryAddress = pPcie_inst.read_mem_dword(pBlade, fitAddressWalker)
        fitEntryType  = pPcie_inst.read_mem_byte(pBlade, fitTypeWalker)

        printDbg("Current entry address, type: " + str(fitEntryAddress) + ", " + str(fitEntryType), debug)

        if int(fitEntryType, 16) == pType:
            printDbg("found matchin entry at " + str(fitEntryAddress))
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

#   Return matching FIT (firmware interface table) entries for the blade under test.
#   Typical FIT entries include uCode, ACM, BootGuard and others.
#
#   input:
#   pPcie_inst - pcie_inst which holds ssh connection.
#   pBlade - blade instance which holds server info
#   pTypes - type of FIT entries to scan.
#
#   return:
#   <dictionary>:<type|address> - memory address of fit entry if found multiples times or one time.
#   EXIT_ERR - if not found or any other error.

def getFitEntries(pBlade, pPcie_inst, pTypes):
    debug = 0
    fitSize = None
    fitAddress = None
    fitAddressesFound = {}
    i = 0

    printDbg("Types: ")
    printSeq(pTypes)
    for i in pTypes:
        printDbg("type of " + str(i) + ": " + str(type(i)))

    if validateFcnInput([pTypes]) == EXIT_ERR:
        printErr("Input validation has failed.")
        return EXIT_ERR

    # Get FIT address from FIT fixed pointer.

    fitAddress = pPcie_inst.read_mem_dword(pBlade, hex(fitPointer).split('x')[-1])

    if fitAddress:
        printDbg("FIT address: " + str(fitAddress))
    else:
        printErr("Unable to obtain FIT address.")
        return EXIT_ERR

    printDbg("Obtaining FIT size...", debug)

    fitSizeAddress = str(hex(int(fitAddress, 16) + 8))
    printDbg("fitSizeAddress: " + str(fitSizeAddress), debug)
    fitSize = pPcie_inst.read_mem_byte(pBlade, fitSizeAddress)

    if fitSize:
        printDbg("FIT size (no. of entries in FIT: " + str(fitSize))
    else:
        printErr("Unable to obtain FIT size.")

    fitAddressWalker = fitAddress
    fitTypeWalker = fitAddressWalker

    for i in range(0, int(fitSize, 16)):
        if debug:
            printBarSingle()

        printDbg("\nIteration: " + str(i), debug)
        fitAddressWalker = hex(int(fitAddressWalker, 16) + 16)          # walk to next entry.
        fitTypeWalker = hex(int(fitAddressWalker, 16) + 14)             # increment by 14 to get to type field.

        fitEntryAddress = pPcie_inst.read_mem_dword(pBlade, fitAddressWalker)
        fitEntryType  = pPcie_inst.read_mem_byte(pBlade, fitTypeWalker)

        printDbg("Current entry address, type: " + str(fitEntryAddress) + ", " + str(fitEntryType), debug)

        if int(fitEntryType, 16) in pTypes:
            printDbg("found matchin entry  " + str(fitEntryType) + " at " + str(fitEntryAddress), debug)
            index = pTypes.index(  int(fitEntryType, 16)  )
            printDbg("index: " + str(index), debug)
            typeFound = pTypes[index]
            printDbg("pType found: " + str(typeFound), debug)
            fitAddressesFound[typeFound] = fitEntryAddress

        if fitEntryAddress == "FFFFFFFF":
            printDbg("skipping.", debug)
        else:
            printDbg("FIT entry address|type: " + str(fitEntryAddress) + ", " + str(fitEntryType), debug)

    if len(fitAddressesFound.keys()):
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

def getFitEntryAcm(pBlade, pPcie_inst, pType):
    lAddressAcmList = None
    lAddressAcm = None
    lAcmDict = {}
    currFieldSize = None
    index1 = None
    debug = 0

    matchingEntries = []

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
        printDbg(str(i) + ": " + str(lAcmDict[i]))
    return lAcmDict

# txt defines the intel txt registers
# as mentioned in intel-txt-software-development-guide.pdf, the Intel TXT configuration registers are a subset of chipset registers and mapped
# into two regions of memory, representing public and private configuration spaces. Rx-s in the private space can only be accessed after a MLE 
# has been executed and before the TXT.CMD.CLOSE-PRVATE command has been issued.
# Private space are mapped to fed20000h
# Public space are mepped to fed30000h

class txt:

    originalVnicsBootPolicy = []
    
    txtConfigRxSpace =  0xfed30000
    txtPublicSpace =    0xfed30000
    txtPrivateSpace =   0xfed20000
                
    # following register definitions are offset relative from txtPublicSpace (fed30000).
    
    txtStsOfs = 0x00
    txtStsSz = 64
    BIT_SENTER_DONE_STS = 0
    BIT_SEXIT_DONE_STS = 1
    #...
    BIT_LOC1_OPEN_STS = 15
    BIT_LOC2_OPEN_STS = 16
     
    txtEstsOfs = 0x08
    txtEstsSz = 1
    BIT_TXT_RESET = 0
    
    txtErrorCode = 0x30
    txtErrorCode328 = 0x328
    
    BIT_SW_SOURCE = 15
    BIT_SW_CPU = 30
    BIT_VALID = 31

    txtCmdReset = 0x38
    
    txtCmdClosePrivate = 0x48
    txtVerFsbIf = 0x100
    txtDidVid = 0x110
    txtVerQpiIf = 0x200
    txtCmdUnlockMemConfig = 0x218
   
    txtSinitBase = 0x270
    txtSinitSize = 0x278
    txtMleJoinBase = 0x290
    txtHeapBase = 0x300
    txtHeapSize = 0x308
    txtDpr = 0x330
    txtCmdOpenLoc1 = 0x380
    txtCmdCloseLoc1 = 0x388
    txtCmdOpenLoc2 = 0x390
    txtCmdCloseLoc2 = 0x398
    txtPublicKeyHashAcm32Byte = 0x400
    txtCmdSecretsByte = 0x8e0
    txtCmdNoSecretsByte = 0x8e8
    txtE2Sts = 0x8f0
    
    txtDeviceSpace = 0xfed40000

    loc0 = 0xfed40000
    loc1 = 0xfed41000
    loc2 = 0xfed42000
    loc3 = 0xfed43000
    loc4 = 0xfed44000
    
    def __init__(self, pUcsmSsh = None, pBmcSsh = None, pFiHostName = None, pPriority = None):
        printDbg("init entry:")
    
    # script that exit abnormally and prematurely, yet leave the SP in original condition.
    # pUcsmSsh - handle to ucsm ssh session
    # pSp - sp instant
    # pBlade - blade instant.

    def getSinitInfo():
        printDbg("entry:")
        return None
