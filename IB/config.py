from commands import getstatusoutput
from sys import platform
from os import environ
import re

# --------------------------------------------------------------------------------
# helper function(s)
weekDays = ('mon', 'tue', 'wed', 'thu', 'fri', 'sat', 'sun')

def getDQMReferenceBuild(tmpspec_path=None):
    dqmref = None
    try:
        from glob import glob
        if tmpspec_path:
            spec = glob(tmpspec_path)[0]
        else:
            spec = glob(environ["CMS_PATH"]+'/tmp*/tmpspec-cmssw-dqm-reference-deployer')[0]
        err, res = getstatusoutput ("grep '%define  *pkgversion  *CMSSW_' "+spec+" | awk '{print $3}'")
        if not err: dqmref = res
    except: pass
    return dqmref

def date2daystamp(dateStr):
    from datetime import date
    regex = re.compile('^(\d\d\d\d)-(\d\d)-(\d\d)-(\d\d)\d*$')
    m = regex.match(dateStr)
    if m: return weekDays[date(int(m.group(1)),int(m.group(2)),int(m.group(3))).weekday()]+'-'+m.group(4)
    return None
    
def updateReleaseInfoFromTc(configuration,release, arch=environ["SCRAM_ARCH"]):
    url = "'https://cmstags.cern.ch/tc/public/ReleaseExternalsXML?release="+release+"&architecture="+arch+"'"
    cmd = 'wget --no-check-certificate  -nv -o /dev/null -O- '+url
    error, result = getstatusoutput ('which wget')
    if error: cmd = 'curl -L -k --stderr /dev/null '+url
    error, result = getstatusoutput (cmd)
    if error:
        print result
        return
    regex = re.compile('^\s*<external\s+external="([^"]+)"\s+tag="([^"]+)"\s*/>\s*$')
    rxBoolFalse = re.compile('^(f|false|0|)$', re.I)
    for line in result.split('\n'):
        m = regex.match(line)
        if m:
            var = m.group(1).strip()
            val = m.group(2).strip()
            if val == '-': val=''
            if configuration.has_key(var):
                vtype = type(configuration[var])
                if vtype == type(True):
                    if rxBoolFalse.match(val): val = False
                    else: val = True
                elif vtype == type([]):
                    if val: val = val.split(',')
                    else:   val = []
            else: print 'ERROR: ---> Tag Collector Invalid key :',var
            if var == 'RelValArgs': val = val + ' --nproc %s ' % cmsRunProcessCount
            print '---> Tag Collector: ',var,'=',val
            configuration[var]=val
    return

def getHostDomain():
    site = ''
    if environ.has_key('INTBUILD_SITELOCAL'): site = 'localhost.localdomain.com'
    else:
      import socket
      site = socket.getfqdn()
    fqdn = site.split('.')
    return fqdn[0], fqdn[-2]+'.'+fqdn[-1]

def getDomain():
    return getHostDomain()[1]

def getHostName():
    return getHostDomain()[0]

def _getCPUCount():
    cmd = ""
    if platform == "darwin":
      cmd = "sysctl -n hw.ncpu"
    elif platform.startswith("linux"):
      cmd = "cat /proc/cpuinfo | grep '^processor' | wc -l"
    error, count = getstatusoutput(cmd)
    if error:
      print "Warning: unable to detect cpu count. Using 4 as default value"
      out = "4"
    if not count.isdigit():
      return 4
    return int(count)

def _memorySizeGB():
    cmd = ""
    if platform == "darwin":
      cmd = "sysctl -n hw.memsize"
    elif platform.startswith("linux"):
      cmd = "free -t -m | grep '^Mem: *' | awk '{print $2}'"
    error, out = getstatusoutput(cmd)
    if error:
      print "Warning: unable to detect memory info. Using 8GB as default value"
      return 8
    if not out.isdigit():
      return 8
    from math import ceil
    count = int(ceil(float(out)/1024))
    if count == 0: count =1
    return count

MachineMemoryGB = _memorySizeGB()
MachineCPUCount = _getCPUCount()

def _compilationProcesses():
    count = MachineCPUCount * 2
    if MachineMemoryGB<count: count = MachineMemoryGB
    return count

def _cmsRunProcesses():
    count = int(MachineMemoryGB/2)
    if count==0: count =1
    if MachineCPUCount<count: count = MachineCPUCount
    return count

compilationPrcoessCount = _compilationProcesses()
cmsRunProcessCount = _cmsRunProcesses()
# --------------------------------------------------------------------------------
# site-specific info:

# fall-back in case CMS_PATH is not defined:
siteInfo = { getDomain() : { 'cmsPath' : None, 'installDir' : None }}
siteInfo['cern.ch']  = {'cmsPath'     : '/afs/cern.ch/cms',
                        'installDir'  : '/afs/cern.ch/cms/sw/ReleaseCandidates/',
                       }
siteInfo['fnal.gov'] = {'cmsPath'     : '/uscms/home/cms_admin/SL4',
                        'installDir'  : '/uscms_data/d1/cms_admin/integration',
                       }
if ('cern.ch' in getDomain()) and (platform == "darwin"):
    siteInfo['cern.ch']['installDir'] = None
    siteInfo['cern.ch']['cmsPath'] = None
########################################################################################################
# --------------------------------------------------------------------------------
# default configuration info for each release cycle ...

relCycles = []
Configuration = {}
defaultConfiguration = {}
defaultConfiguration['compilingProcesses'] = compilationPrcoessCount
defaultConfiguration['createTcRelease']    = True
defaultConfiguration['CMSDIST']            = None             #Please update Tag collecotr with proper tag for each SCRAM_ARCH
defaultConfiguration['PKGTOOLS']           = None             #Please update Tag collecotr with proper tag for each SCRAM_ARCH
defaultConfiguration['INTBUILD']           = 'branches/production'          #Please update Tag collecotr if a different tags needs to be used
defaultConfiguration['sendDevMail']        = False
defaultConfiguration['runRelVal']          = True
defaultConfiguration['RelValArgs']         = "--useInput all --nproc %s" % cmsRunProcessCount
defaultConfiguration['defaultAptPackages'] = []
defaultConfiguration['defaultIBPackages']  = ['cmssw-dqm-reference-deployer','local-cern-siteconf']
defaultConfiguration['RelMonParameters']   = {
                                              "threshold"    : "0.00001",
                                              "statTest"     : "Chi2",
                                              "doPngs"       : True,
                                              "doComparison" : True,
                                              "doReport"     : True,
                                              "no_successes" : True,
                                              "black_list"   : ["AlCaReco@1"],
                                              "success_percentage" : "0.2",
                                             }

if getDomain() != 'cern.ch': defaultConfiguration['createTcRelease'] = False

def setDefaults(cycle, tcTag=None):
  global relCycles,Configuration
  if Configuration.has_key(cycle): return
  if not tcTag: tcTag = 'CMSSW_'+cycle.replace('.','_')+'_X'
  from copy import deepcopy
  relCycles.append(cycle)
  Configuration[cycle] = deepcopy(defaultConfiguration)
  Configuration[cycle]['releaseTag'] = tcTag
  Configuration[cycle]['tagCollTag'] = tcTag
  threaded = ""
  if '_THREADED_' in environ['CMSSW_VERSION']:
      threaded = " --customise FWCore/Concurrency/dropNonMTSafe.dropNonMTSafe "
  if '_ROOT6_' in environ['CMSSW_VERSION']:
      threaded = " --customise FWCore/Concurrency/dropNonMTSafe.dropNonMTSafe "
  if (platform == "darwin") and not re.match('CMSSW_([0-4]_\d+|5_[0-1])_.*',tcTag):
      Configuration[cycle]['RelValArgs'] += " --command '-n 1 "+threaded+"'"
  if cycle.startswith('4.2'):
    Configuration[cycle]['RelValArgs'] = Configuration[cycle]['RelValArgs'].replace("--useInput all","")
  if cycle.startswith('7.'):
    prefix = ""
    if "slc6" in environ["SCRAM_ARCH"]:
      prefix = "--prefix 'timeout 3600 '"
    Configuration[cycle]['RelValArgs'] += " --job-reports --command \\\""+threaded+" --customise Validation/Performance/TimeMemorySummary.customiseWithTimeMemorySummary " + prefix + " \\\" --das-options '--cache " + environ["CMSBUILD_BUILD_DIR"] + "/das-cache.file' "
    if "ROOT6" in cycle:
      Configuration[cycle]['RelValArgs'] += " -j 6 "
    if "ASAN" in cycle:
      import multiprocessing
      Configuration[cycle]['RelValArgs'] += " -j %s " % (multiprocessing.cpu_count() / 2,)
    if "THREADED" in cycle:
      Configuration[cycle]['RelValArgs'] += " -t 4 -j %s " % (int(MachineMemoryGB/3))
  if re.match( '^CMSSW_6_2_X_SLHC_|^CMSSW_6_2_SLHCDEV_X_', environ['CMSSW_VERSION'] ):
    Configuration[cycle]['RelValArgs'] += " -w upgrade -l 10000,10200,10400,11200,11400,11600,11800,12000,12800,13000 "

####################################################################################
# ---------------------------------------------------------------------------------#
# call setDefaults('cycle') and then override configuration for a release cycle if #
# default values need changes                                                      #
####################################################################################
