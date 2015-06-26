#!/usr/bin/env python
 
import os, sys, time, threading,platform, glob, re
from commands import getstatusoutput
try:
  scriptPath = os.path.dirname(os.path.abspath(__file__))
except Exception, e :
  scriptPath = os.path.dirname( os.path.abspath(sys.argv[0]) )
if scriptPath not in sys.path:
  sys.path.append(scriptPath)

from BuilderBase import BuilderBase, ActionError
import checkLogFile
import config
# ================================================================================
def runCmd (cmd):
  while cmd.endswith(";"): cmd=cmd[:-1]
  print "Running cmd> ",cmd
  ret, out = getstatusoutput(cmd)
  if out: print out
  return ret
  
from threading import Thread

class IBThreadBase(Thread):
    def __init__(self, deps= []):
        Thread.__init__(self)
        self.deps = deps
        return

    def run(self):
        for dep in self.deps:
            if dep: dep.join()
        return

# ================================================================================
class UnitTester(IBThreadBase):
    def __init__(self, startDirIn, Logger, deps= []):
        IBThreadBase.__init__(self, deps)
        self.startDir = startDirIn
	self.logger = Logger
        return
    
    # --------------------------------------------------------------------------------

    def checkTestLogs(self):
        try:
	    self.checkUnitTestLog()
	except:
	   pass 
	try:
            self.splitUnitTestLogs()
        except Exception, e:
            print "ERROR splitting unit test logs :", str(e)
        return
    
    # --------------------------------------------------------------------------------

    def checkUnitTestLog(self):
        import checkTestLog
        print "unitTest>Going to check log file from unit-tests in ", self.startDir
        try:
	    runCmd("rm -rf "+self.startDir+"/unitTestLogs")
	except:
	    pass
        tlc = checkTestLog.TestLogChecker(self.startDir+"/unitTests-summary.log", True)
        tlc.check(self.startDir+"/unitTests.log")
        return
    
    # --------------------------------------------------------------------------------

    def splitUnitTestLogs(self):
        import splitUnitTestLog
        print "unitTest>Going to split log file from unit-tests in ", self.startDir
        tls = splitUnitTestLog.LogSplitter(self.startDir+"/unitTests-summary.log", True)
        tls.split(self.startDir+"/unitTests.log")
        runCmd('cd '+self.startDir+'; zip -r unitTestLogs.zip unitTestLogs')
        return
    
    # --------------------------------------------------------------------------------

    def run(self):
        IBThreadBase.run(self)
        if platform.system() == 'Darwin':
            print 'unitTest> Skipping unit tests for MacOS'
            return
        try:
            if os.path.exists(os.path.join(self.startDir,".SCRAM",os.environ['SCRAM_ARCH'],"InstalledTools/cmssw")):
                cmd = "cd "+self.startDir+"; eval `scram tool info cmssw 2>&1 | grep CMSSW_BASE=`"
                cmd += "; find src -mindepth 1 -maxdepth 1 -type d | xargs -I '{}' find '{}' -maxdepth 1 -mindepth 1 -type d > localpkgs.txt; echo Local Packages; cat localpkgs.txt"
                cmd += "; grep SCRAMSTORENAME_TEST tmp/"+os.environ['SCRAM_ARCH']+"/MakeData/DirCache.mk | grep _INIT_FUNC > alltests.txt"
                cmd += "; for pkg in `cat localpkgs.txt`; do grep -v \"$pkg/\" alltests.txt > basetests.txt; mv basetests.txt alltests.txt; done"
                cmd += "; BASE_TESTS=`cat alltests.txt | sed -e 's|_INIT_FUNC.*||'`"
                cmd += "; echo Tests from Release: $BASE_TESTS; for t in $BASE_TESTS ; do ln -s $CMSSW_BASE/test/"+os.environ['SCRAM_ARCH']+"/$t test/"+os.environ['SCRAM_ARCH']+"/$t; done"
                print ">>Running command to create test symlinks\n>> ",cmd
                err, cmd = getstatusoutput(cmd)
        except Exception, e : pass
        try:
            cmd = "cd "+self.startDir+"; sed -i -e 's|testing.log; *$(CMD_rm)  *-f  *$($(1)_objdir)/testing.log;|testing.log;|;s|test $(1) had ERRORS\") *\&\&|test $(1) had ERRORS\" >> $($(1)_objdir)/testing.log) \&\&|' config/SCRAM/GMake/Makefile.rules; "
            cmd += " if which timeout 2>/dev/null; then TIMEOUT=timeout; fi ; "
            cmd += '${TIMEOUT+timeout 3h} scram b -f -k -j 3 unittests >unitTests1.log 2>&1 '
            print 'unitTest> Going to run '+cmd
            ret = runCmd(cmd)
            if ret != 0:
                print "ERROR when running unit-tests: cmd returned " + str(ret)
        except Exception, e :
            print "ERROR during runtests : caught exception: " + str(e)
            pass
        try:
            testLog = self.startDir+'/tmp/'+os.environ['SCRAM_ARCH']+'/src/'
            logFile = self.startDir+'/unitTests.log'
            runCmd('rm -f %s; touch %s' % (logFile,logFile))
            for packDir in glob.glob(testLog+'*/*'):
                pack = packDir.replace(testLog,'')
                runCmd("echo '>> Entering Package %s' >> %s" % (pack,logFile))
                packDir += '/test'
                if os.path.exists(packDir):
                    err, testFiles = getstatusoutput ('find '+packDir+' -maxdepth 2 -mindepth 2 -name testing.log -type f')
                    for lFile in testFiles.strip().split('\n'):
                        if lFile: runCmd("cat %s >> %s" % (lFile, logFile))
                runCmd("echo '>> Leaving Package %s' >> %s" % (pack,logFile))
                runCmd("echo '>> Tests for package %s ran.' >> %s" % (pack,logFile))
        except Exception, e: pass
        self.checkTestLogs()
        self.logger.updateUnitTestLogs()
        return

# ================================================================================

class AddOnTester(IBThreadBase):
    def __init__(self, startDirIn, Logger, deps= []):
        IBThreadBase.__init__(self, deps)
        self.startDir  = startDirIn
        self.logger = Logger
        return
    
    def run(self):
        IBThreadBase.run(self)
        try:
            cmd  = 'cd '+self.startDir+'; rm -rf addOnTests; addOnTests.py 2>&1 >addOnTests.log '
            print 'addOnTests: in: ', os.getcwd()
            print ' ... going to execute:',cmd
            ret = runCmd(cmd)
            if ret != 0:
                print "ERROR when running addOnTests: cmd returned " + str(ret)
        except Exception, e :
            print "ERROR during addOnTests : caught exception: " + str(e)
            print "      cmd as of now   : '" + cmd + "'"
            pass
        runCmd('cd '+self.startDir+'/addOnTests/logs; zip -r addOnTests.zip *.log')
        self.logger.updateAddOnTestsLogs()
        return

# ================================================================================

class PyRelVals(IBThreadBase):
    def __init__(self, startDirIn, Logger, cmd, deps= []):
        IBThreadBase.__init__(self, deps)
        self.startDir  = startDirIn
        self.logger = Logger
        self.cmd = cmd
        return
    
    def run(self):
        IBThreadBase.run(self)
        experimental = re.match("^slc7_", os.environ["SCRAM_ARCH"]) is not None
	experimental = False
        if(experimental): # Enable experimental partial logging
            from runPyRelValThread import PyRelValsThread
            pyrelval = PyRelValsThread(8, 'pyRelval')
        try:
            if(experimental): # Enable experimental partial logging
                try:
                    add_arg = re.sub('"\s*$',"",re.sub('^\s*"',"",self.cmd.split("--args ")[1]))
                except IndexError:
                    add_arg = ""
                self.cmd = 'true'
            runCmd('cd '+self.startDir+'; rm -rf pyRelval; mkdir pyRelval; cd pyRelval; '+ self.cmd + ' 2>&1 > runall.log')
            if(experimental): # Enable experimental partial logging
                pyrelval.startWorkflows(self.logger, add_arg)
        except Exception, e :
            print "runTests> ERROR during test PyReleaseValidation : caught exception: " + str(e)
            pass
        try:
            runCmd("cd " + self.startDir + "/pyRelval ; zip -r pyRelValMatrixLogs.zip `find . -mindepth 2 -maxdepth 2 -name '*.log' -o -name '*.xml' -o -name 'cmdLog' -type f | sed -e 's|^./||'`")
            self.logger.updateRelValMatrixLogs()
        except Exception, e :
            print "runTests> ERROR during test PyReleaseValidation : caught exception: " + str(e)
            pass
        return

# ================================================================================

class DQMOfflineTests(IBThreadBase):
    def __init__(self, startDirIn, Logger, deps= []):
        IBThreadBase.__init__(self, deps)
        self.startDir  = startDirIn
        self.logger = Logger
        return
    
    def run(self):
        IBThreadBase.run(self)
        try:
            cmd = 'cd '+self.startDir+'; '+os.path.join(scriptPath, 'runDQMOfflineTests.py') + ' -r ' + self.startDir + ' -p ' + os.environ['SCRAM_ARCH']
            runCmd(cmd)
        except Exception, e:
            print "ERROR: Caught exception during runDQMOfflineTests : " + str(e)
        return

# ================================================================================

class DQMRefReports(IBThreadBase):
    def __init__(self, startDirIn, Logger, cmd, deps= []):
        IBThreadBase.__init__(self, deps)
        self.startDir  = startDirIn
        self.logger = Logger
        self.cmd = cmd
        return
    
    def run(self):
        IBThreadBase.run(self)
        try:
            runCmd("mkdir -p "+self.logger.webTargetDir+"/pyRelValMatrixLogs/run ;"+self.cmd)
        except Exception, e :
            print "DQMRefReport> ERROR during test DQMRefReport : caught exception: " + str(e)
            pass
        return

# ================================================================================

class IgnominyTests(IBThreadBase):
    def __init__(self, startDirIn, Logger, deps= []):
        IBThreadBase.__init__(self, deps)
        self.startDir  = startDirIn
	self.logger = Logger
        return
    
    def run(self):
        IBThreadBase.run(self)
        try:
            cmd = 'cd '+self.startDir+'; '
            cmd += 'rm -rf igRun; mkdir igRun; cd igRun;'
            cmd += 'ignominy -f -A -i -g all -j 4 $CMSSW_RELEASE_BASE > ignominy.log 2>&1 '
            print 'Ignominy> Going to run '+cmd
            ret = runCmd(cmd)
            if ret != 0:
                 print "ERROR when running Ignominy: cmd returned " + str(ret)
        except Exception, e :
            print "ERROR during ignominy : caught exception: " + str(e)
            print "      cmd as of now   : '" + cmd + "'"
            pass
	
	cmd   = 'cd '+self.startDir+'/igRun; gzip dependencies.txt products.txt logwarnings '
	try:
	    runCmd(cmd)
        except Exception, e :
            print "ERROR during ignominy : caught exception: " + str(e)
            print "      cmd as of now   : '" + cmd + "'"
            pass
        self.logger.updateIgnominyLogs()
	cmd  = 'cd '+self.startDir+'/igRun; gunzip dependencies.txt.gz products.txt.gz logwarnings.gz ; '
	cmd += 'touch igDone'
	try:
            runCmd(cmd) 
	except:
            pass
        return

# ================================================================================

class AppBuildSetTests(IBThreadBase):
    def __init__(self, startDirIn, Logger, cmsdist, deps = [], appType='fwlite'):
        IBThreadBase.__init__(self, deps)
        self.startDir  = startDirIn
        self.logger = Logger
        self.cmsdist = cmsdist
        self.appType  = appType
        self.appDir =   startDirIn+'/BuildSet/'+appType
        return

    def setStatus(self,status,message):
        outFile = open(self.appDir+'/index.html','w')
        outFile.write("<html><head></head><body><b>"+message+"</b></body></html>\n")
        outFile.close()
        outFile = open(self.appDir+'/status','w')
        outFile.write(status)
        outFile.close()
        print message
        return
        
    def run(self):
        IBThreadBase.run(self)
        script = scriptPath+'/buildSetTest.py'

        logFile =  self.startDir+'/'+self.appType+'BuildSet.log'
        cmd  = script+' --release '+self.startDir+' --ignominy '+self.startDir+'/igRun --cmsdist '+self.cmsdist
        cmd += ' --application '+self.appType+' > '+logFile+' 2>&1 '
        try:
            ret = runCmd(cmd)
        except:
            pass

	if not os.path.exists(self.appDir+'/status'):
            inFile = open(logFile)
            message = ''
            for x in inFile.readlines(): message += x
            inFile.close()
            self.setStatus('error',message)

        runCmd('cat '+logFile+' ; cp '+logFile+' '+self.appDir)
        self.logger.updateBuildSetLogs(self.appType)
        return

# ================================================================================

class LibDepsTester(IBThreadBase):
    def __init__(self, startDirIn, Logger, deps= []):
        IBThreadBase.__init__(self, deps)
        self.startDir  = startDirIn
	self.logger = Logger
        return
    
    def run(self):
        IBThreadBase.run(self)
        cmd = 'cd '+self.startDir+' ; '+scriptPath+'/checkLibDeps.py --plat '+os.environ['SCRAM_ARCH']+' > chkLibDeps.log 2>&1'
        try:
            ret = runCmd(cmd)
            if ret != 0:
                print "ERROR when running lib dependency check: cmd returned " + str(ret)
        except:
            print "ERROR during lib dependency check : caught exception: " + str(e)
            print "      cmd as of now   : '" + cmd + "'"

        self.logger.updateLogFile("chkLibDeps.log")
        self.logger.updateLogFile("libchk.pkl",'new')
	return

# ================================================================================

class DirSizeTester(IBThreadBase):
    def __init__(self, startDirIn, Logger, deps= []):
        IBThreadBase.__init__(self, deps)
        self.startDir  = startDirIn
	self.logger = Logger
        return
    
    def run(self):
        IBThreadBase.run(self)
        cmd = 'cd '+self.startDir+'; '+scriptPath+'/checkDirSizes.py '
        try:
            ret = runCmd(cmd)
            if ret != 0:
	        print "ERROR when running DirSizeTester: cmd returned " + str(ret)
        except ActionError, e:
            print "Caught ActionError when running checkDirSizes.py (platform :" +os.environ['SCRAM_ARCH']+ ") : " + str(e)
	
        cmd = 'cd '+self.startDir+'; storeTreeInfo.py --checkDir src --outFile treeInfo-IBsrc.json '
        try:
            ret = runCmd(cmd)
            if ret != 0:
	        print "ERROR when running DirSizeTester: cmd returned " + str(ret)
        except ActionError, e:
            print "Caught ActionError when running storeTreeInfo.py (platform :" +os.environ['SCRAM_ARCH']+ ") : " + str(e)
            pass

        self.logger.updateLogFile(self.startDir+"/dirSizeInfo.pkl","testLogs")
        self.logger.updateLogFile(self.startDir+"/treeInfo-IBsrc.json","testLogs")
	return

# ================================================================================

class ReleaseProductsDump(IBThreadBase):
    def __init__(self, startDirIn, Logger, deps= []):
        IBThreadBase.__init__(self, deps)
        self.startDir  = startDirIn
	self.logger = Logger
        return
    
    def run(self):
        IBThreadBase.run(self)
        logDir =  os.path.join(self.startDir,'logs', os.environ['SCRAM_ARCH'])
        if not os.path.exists(logDir): os.makedirs(logDir)
	
        rperrFileName = os.path.join( logDir, 'relProducts.err')
        
        cmd = 'cd '+self.startDir+'; RelProducts.pl > ReleaseProducts.list  2> '+ rperrFileName
        try:
            ret = runCmd(cmd)
	    if ret != 0:
	        print "ERROR when running ReleaseProductsChecks: cmd returned " + str(ret)
        except ActionError, e:
            print "Caught ActionError when running RelProducts.pl (platform :" +os.environ['SCRAM_ARCH']+ ") : " + str(e)
            pass
	self.logger.updateLogFile(self.startDir+"/ReleaseProducts.list")
	self.logger.updateLogFile(rperrFileName, "logs/"+os.environ['SCRAM_ARCH'])
	return

# ================================================================================

class BuildFileDependencyCheck(IBThreadBase):
    def __init__(self, startDirIn, Logger, deps= []):
        IBThreadBase.__init__(self, deps)
        self.startDir  = startDirIn
	self.logger = Logger
        return
    
    def run(self):
        IBThreadBase.run(self)
        logDir =  os.path.join(self.startDir,'logs',os.environ['SCRAM_ARCH'])
        if not os.path.exists(logDir): os.makedirs(logDir)
        dverrFileName = os.path.join( logDir, 'depsViolations.err')
        
        depDir =  os.path.join(self.startDir,'etc/dependencies')
        if not os.path.exists(depDir): os.makedirs(depDir)
	depFile = os.path.join(depDir, 'depsViolations.txt')
       
        cmd = 'cd '+self.startDir+'; ReleaseDepsChecks.pl --detail > '+depFile+'  2> '+ dverrFileName
        try:
            ret = runCmd(cmd)
	    if ret != 0:
	        print "ERROR when running BuildFileDependencyCheck: cmd returned " + str(ret)
        except ActionError, e:
            print "Caught ActionError when running ReleaseDepsChecks.pl (platform :" +os.environ['SCRAM_ARCH']+ ") : " + str(e)
        
        cmd = 'cd '+self.startDir+'; '+scriptPath+'/splitDepViolationLog.py --log '+depFile
        try:
            ret = runCmd(cmd)
	    if ret != 0:
	        print "ERROR when running BuildFileDependencyCheck: cmd returned " + str(ret)
        except ActionError, e:
            print "Caught ActionError when running splitDepViolationLog.py: " + str(e)
            pass

	bdir = os.path.join(depDir,"depViolationLogs")
	try:
	  import fnmatch
	  for root, dirnames, filenames in os.walk(bdir):
	    for filename in fnmatch.filter(filenames, 'depViolation.log'):
	      pkg = "/".join(root.replace(bdir,"").split('/')[1:3])
	      log = os.path.join(bdir, pkg, "log.txt")
	      ret = runCmd("touch "+log+"; cat "+os.path.join(root, filename)+" >> "+log)
	except ActionError, e:
	  pass

	self.logger.updateLogFile(self.startDir+"/depViolationSummary.pkl","testLogs")
	self.logger.updateLogFile(dverrFileName, "logs/"+os.environ['SCRAM_ARCH'])
	self.logger.updateLogFile(depFile, "etc/dependencies/")
	self.logger.updateLogFile(bdir, "etc/dependencies/")
	return


# ================================================================================

class CodeRulesChecker(IBThreadBase):
    def __init__(self, startDirIn, Logger, deps = []):
        IBThreadBase.__init__(self, deps)
        self.startDir  = startDirIn
	self.logger = Logger
        return
    
    def run(self):
        IBThreadBase.run(self)
        try:
            script = 'cd '+self.startDir+'; cmsCodeRulesChecker.py'
	    if not os.path.exists(script) :
                print ' ... no cmsCodeRulesChecker.py in release, checks not run ... '
                return
            
            print ' ... using cmsCodeRulesChecker.py from release ...'
            cmd  = 'cd '+ self.startDir +'; rm -rf  codeRules; mkdir codeRules; cd codeRules; '
	    cmd += script+' -d ../src -S . -html 2>&1 >CodeRulesChecker.log '
            print 'CodeRulesChecker: in: ', os.getcwd()
            print ' ... going to execute:',cmd
            ret = runCmd(cmd)
            if ret != 0:
                print "ERROR when running CodeRulesChecker: cmd returned " + str(ret)

        except Exception, e :
            print "ERROR during runtests : caught exception: " + str(e)
            print "      cmd as of now   : '" + cmd + "'"
            pass
        self.logger.updateCodeRulesCheckerLogs()
	return


# ================================================================================
class RunMatirxCmd(IBThreadBase):
    def __init__(self, startDirIn, args, deps = []):
        IBThreadBase.__init__(self, deps)
        self.startDir  = startDirIn
	self.args = args
        return
    
    def run(self):
        IBThreadBase.run(self)
        try:
            cmd = "rm -rf "+self.startDir+"; mkdir -p "+self.startDir+"; cd "+self.startDir+"; runTheMatrix.py "+self.args+" > run.log 2>&1"
            print ' ... going to execute:',cmd
            runCmd(cmd)
        except Exception, e :
            pass
	return

class GenerateDQMRef(IBThreadBase):
    def __init__(self, startDirIn, deps = []):
        IBThreadBase.__init__(self, deps)
        self.startDir  = startDirIn + "/DQMRef"
        return
    
    def run(self):
        IBThreadBase.run(self)
        try:
            dqmrefargs=os.environ['CMS_PATH']+"/"+os.environ['SCRAM_ARCH']+"/cms/cmssw-dqm-reference-deployer/"+config.getDQMReferenceBuild()+"/etc/runTheMatrix.args"
            if not os.path.exists(dqmrefargs):
                print 'ERROR: DQM Ref data is not available:'+dqmrefargs
                return
            inArgs = open (dqmrefargs, 'r')
            thrds = []
            runCmd("rm -rf "+self.startDir)
            for line in inArgs.readlines():
                thrd = RunMatirxCmd(self.startDir+"/wfs_"+str(len(thrds)),line.rstrip()+" -j 2")
                thrd.start()
                thrds.append(thrd)
            inArgs.close()
            for thrd in thrds: thrd.join()
            for rfile in glob.glob(self.startDir+"/wfs_*/*HARVEST*/DQM_V*.root"):
                wfdir = self.startDir+"/data/"+re.sub("/DQM_V.+\.root","",re.sub(self.startDir+"/wfs_\d+/","",rfile))
                cmd   = "mkdir -p "+wfdir+" ; cp "+rfile+" "+wfdir
                runCmd(cmd)
            runCmd("rm -f "+self.startDir+"/wfs_*/*HARVEST*/*.root")
        except Exception, e :
            print "ERROR during GenerateDQMRef : caught exception: " + str(e)
            pass
	return

# ================================================================================

class ReleaseTester(BuilderBase):

    def __init__(self, buildDir, releaseDir, appset, doInstall=True):

        BuilderBase.__init__(self)
        os.environ['STAGE_SVCCLASS']='t1transfer'
        os.environ['STAGE_HOST']='castorcms'
        os.environ['STAGER_TRACE']='3'
    
    	self.doInstall=doInstall
    	self.buildDir = buildDir
    	self.appset = appset
    	self.updateTimeStamp(self.buildDir)
    	
    	self.cmsswBuildDir = releaseDir
    	self.release = os.path.basename(releaseDir)
    	self.relTag = self.release
    	self.relCycle = self.release.replace("CMSSW_","").split("_X_",1)[0].replace("_",".")
	
        day,hour = self.stamp.split('-')
        
        self.threadList = {}
        self.maxThreads = 2 # one for unit-tests, one for addOnTests

        self.doRelVal = True
        self.logger = None
        self.RelValArgs = None
        config.setDefaults(self.relCycle)
        try:
            self.doRelVal   = config.Configuration[self.relCycle]['runRelVal']
            self.RelValArgs = config.Configuration[self.relCycle]['RelValArgs']
        except:
            pass
	
        return
    
    # --------------------------------------------------------------------------------

    def setupLogger(self, doInstall=True):

        if not self.logger:
	    from logUpdater import LogUpdater
            self.logger = LogUpdater(self.buildDir,doInstall)
            self.logger.setDryRun(self.dryRun)
            self.logger.setRelease(self.relTag, self.relCycle, self.stamp)

        return
    # --------------------------------------------------------------------------------

    def getDepThreads(self, jobs=[]):
        deps = []
        for job in jobs:
            if self.threadList.has_key(job) and self.threadList[job]: deps.append(self.threadList[job])
        return deps

    # --------------------------------------------------------------------------------

    def doTest(self, only=None):

	if not self.release :
            print "ReleaseTester> ERROR: no release specified !! "
            return 

        self.setupLogger(self.doInstall)
        self.runProjectInit()
        if not only or 'dirsize' in only:
            print '\n'+80*'-'+' dirsize \n'
            self.threadList['dirsize'] = self.runDirSize()

        if not only or 'depViolation' in only:
            print '\n'+80*'-'+' depViolation \n'
            self.threadList['ddepViolation'] = self.runBuildFileDeps()

        if not only or 'relProducts' in only:
            print '\n'+80*'-'+' relProducts \n'
            self.threadList['relProducts'] = self.runReleaseProducts()

        if not only or 'addon' in only:
            print '\n'+80*'-'+' addOnTests \n'
            self.threadList['addon'] = self.runAddOnTests()

        if not only or 'relvalcomp' in only:
            print '\n'+80*'-'+' relvalcomp \n'
            self.threadList['relvalcomp'] = self.runBuildReports()

        if not only or 'unit' in only:
            print '\n'+80*'-'+' unit \n'
            self.threadList['unit'] = self.runUnitTests()

	if not only or 'codeRules' in only:
            print '\n'+80*'-'+' codeRules \n'
            self.threadList['codeRules'] = self.runCodeRulesChecker()

        if not only or 'ignominy' in only:
            print '\n'+80*'-'+' ignominy \n'
            self.threadList['ignominy'] = self.runIgnominy()

        if not only or 'fwbuildset' in only:
            print '\n'+80*'-'+' FWLite BuildSet\n'
            self.threadList['fwbuildset'] = self.runFWLiteBuildSet(self.getDepThreads(['ignominy']))

        #if not only or 'onlbuildset' in only:
        #    print '\n'+80*'-'+' Online BuildSet\n'
        #    self.threadList['onlbuildset'] = self.runOnlineBuildSet(self.getDepThreads(['ignominy']))

        if not only or 'dqmoffline' in only:
            print '\n'+80*'-'+' DQMOfflineTest \n'
            self.threadList['dqmoffline'] = self.runDQMOfflineTests(self.getDepThreads(['unit']))

        if not only or 'relval' == only:
            print '\n'+80*'-'+' relval \n'
            self.threadList['relval'] = self.runPyRelVals(self.getDepThreads(['addon']))

        if not only or 'libcheck' in only:
            print '\n'+80*'-'+' libcheck\n'
            self.threadList['libcheck'] = self.checkLibDeps()

        if not only or 'geom' in only:
            print '\n'+80*'-'+' geom \n'
            self.threadList['geom'] = self.runGeomTests()

        if not only or 'pyConfigs' in only:
            print '\n'+80*'-'+' pyConfigs \n'
            self.threadList['pyConfigs'] = self.checkPyConfigs()

        if not only or 'dupDict' in only:
            print '\n'+80*'-'+' dupDict \n'
            self.threadList['dupDict'] = self.runDuplicateDictCheck()

	print 'TestWait> waiting for tests to finish ....'
	for task in self.threadList:
            if self.threadList[task]: self.threadList[task].join()
        print 'TestWait> Tests finished '
	return
    
    # --------------------------------------------------------------------------------

    def checkPyConfigs(self, deps = []):
        print "Going to check python configs in ", os.getcwd()
        cmd = 'cd src ; '+scriptPath+'/checkPyConfigs.py > ../chkPyConf.log 2>&1'
        try:
            self.doCmd(cmd,self.dryRun,self.cmsswBuildDir)
	    self.logger.updateLogFile("chkPyConf.log")
	    self.logger.updateLogFile("chkPyConf.log",'testLogs')
        except:
            pass
        return None
    
    # --------------------------------------------------------------------------------

    def checkLibDeps(self, deps = []):
        print "libDepTests> Going to run LibDepChk ... "
        thrd = None
        try:
            thrd = LibDepsTester(self.cmsswBuildDir,self.logger, deps)
            thrd.start()
        except Exception, e :
            print "ERROR during LibDepChk : caught exception: " + str(e)
        return thrd

    # --------------------------------------------------------------------------------

    def runProjectInit(self, deps = []):
        print "runProjectInit> Going regenerate scram caches ... "
        try:
            self.doCmd("scram build -r echo_CXX",self.dryRun,self.cmsswBuildDir)
        except Exception, e :
            print "ERROR during runProjectInit: caught exception: " + str(e)
        return None

    # --------------------------------------------------------------------------------

    def runCodeRulesChecker(self, deps = []):
        print "runCodeRulesTests> Going to run cmsCodeRulesChecker ... "
        thrd = None
        try:
            thrd = CodeRulesChecker(self.cmsswBuildDir,self.logger, deps)
            thrd.start()
        except Exception, e :
            print "ERROR during cmsCodeRulesChecker : caught exception: " + str(e)
        return thrd
    
    # --------------------------------------------------------------------------------

    def runDuplicateDictCheck(self, deps = []):
        print "runDuplicateDictTests> Going to run duplicateReflexLibrarySearch.py ... "
	script = 'duplicateReflexLibrarySearch.py'
	for opt in ['dup', 'lostDefs', 'edmPD']:
            cmd = script+' --'+opt+' 2>&1 >dupDict-'+opt+'.log'
	    try:
                self.doCmd(cmd,self.dryRun,self.cmsswBuildDir)
	    except Exception, e :
	        print "ERROR during test duplicateDictCheck : caught exception: " + str(e)
        self.logger.updateDupDictTestLogs()
	return None
    
    # --------------------------------------------------------------------------------

    def runGeomTests(self, deps = []):
        print "runGeomTests> Going to run domcount and dddreport tests ... "
	print "runGeomTests> Skipping Geom tests ...."
	return
        for exe in ['dddreport.sh', 'domcount.sh']:
	    exepath = './bin/'+os.environ['SCRAM_ARCH']+'/'+exe
	    log = exe[:-3]+'.log'
	    if os.path.exists(self.cmsswBuildDir+"/"+exepath):
                cmd = 'export CMSSW_RELEASE_BASE='+self.cmsswBuildDir+'; '
                cmd += 'sed -i -e "s|/bin/csh .*|/usr/bin/env bash|g" '+exepath+'; '
                cmd += 'sed -i -e "s|eval .scramv1.*||" '+exepath+'; '
                cmd += 'sed -i -e "s|/tmp/tmpcmsswdddxmlfileslist|tmpcmsswdddxmlfileslist|" '+exepath+'; '
		cmd += exepath+' 2>&1 > '+log
                try:
		    self.doCmd(cmd,self.dryRun,self.cmsswBuildDir)
                except Exception, e :
                    print "ERROR during running geom tests : caught exception: " + str(e)
                    pass
        self.logger.updateGeomTestLogs()
	return None
    
    # --------------------------------------------------------------------------------

    def runIgnominy(self, deps = []):
        print "ignominyTests> Going to run ignominy tests ... "
        thrd  = None
        try:
            thrd = IgnominyTests( self.cmsswBuildDir, self.logger, deps)
            thrd.start()
        except Exception, e :
            print "ERROR during run ignominytests : caught exception: " + str(e)
            pass
        return thrd
    
    # --------------------------------------------------------------------------------

    def runFWLiteBuildSet(self, deps = []):
        print "FWLiteBuildSet> Going to run FWLite BuildSet tests ... "
        thd  = None
        try:
            thd = AppBuildSetTests( self.cmsswBuildDir, self.logger, self.appset, deps , 'fwlite')
            thd.start()
        except Exception, e :
            print "ERROR during run FWLiteBuildSet : caught exception: " + str(e)
            pass
        return thd
    
    # --------------------------------------------------------------------------------

    def runOnlineBuildSet(self,deps = []):
        print "OnlineBuildSet> Going to run Online BuildSet tests ... "
        thd  = None
        try:
            thd = AppBuildSetTests( self.cmsswBuildDir, self.logger, self.appset, deps, 'online')
            thd.start()
        except Exception, e :
            print "ERROR during run OnlineBuildSet : caught exception: " + str(e)
            pass
        return thd

    # --------------------------------------------------------------------------------

    def runUnitTests(self, deps = []):
        print "runTests> Going to run units tests ... "
        thrd = None
        try:
            thrd = UnitTester( self.cmsswBuildDir,self.logger, deps )
            thrd.start()
        except Exception, e :
            print "ERROR during run unittests : caught exception: " + str(e)
            pass
        return thrd
    
    # --------------------------------------------------------------------------------

    def runDQMOfflineTests(self, deps = []):
        print "DQMOfflineTests> Going to run DQMOfflineTests ... "
        thrd = None
        try:
            thrd = DQMOfflineTests( self.cmsswBuildDir,self.logger, deps)
            thrd.start()
        except Exception, e :
            print "ERROR during  DQMOfflineTests: caught exception: " + str(e)
            pass
        return thrd

    # --------------------------------------------------------------------------------
        
    def runAddOnTests(self, deps=[]):

        print "runTests> Going to run addOnTests ... "
	thrd = None
        try:
            thrd = AddOnTester( self.cmsswBuildDir,self.logger, deps)
            thrd.start()
        except Exception, e :
            print "ERROR during runAddOnTests : caught exception: " + str(e)
            pass
        return thrd
    
    # --------------------------------------------------------------------------------
        
    def runDirSize(self, deps=[]):

        print "runTests> Going to run DirSize ... "
	thrd = None
        try:
            thrd = DirSizeTester( self.cmsswBuildDir,self.logger, deps)
            thrd.start()
        except Exception, e :
            print "ERROR during DirSize : caught exception: " + str(e)
            pass
        return thrd
    
    # --------------------------------------------------------------------------------
        
    def runReleaseProducts(self, deps=[]):

        print "runTests> Going to run ReleaseProducts ... "
	thrd = None
        try:
            thrd = ReleaseProductsDump( self.cmsswBuildDir,self.logger, deps)
            thrd.start()
        except Exception, e :
            print "ERROR during ReleaseProducts : caught exception: " + str(e)
            pass
        return thrd
    
    # --------------------------------------------------------------------------------
        
    def runBuildFileDeps(self, deps=[]):

        print "runTests> Going to run BuildFileDeps ... "
	thrd = None
        try:
            thrd = BuildFileDependencyCheck( self.cmsswBuildDir,self.logger, deps)
            thrd.start()
        except Exception, e :
            print "ERROR during RBuildFileDeps : caught exception: " + str(e)
            pass
        return thrd
    
    # --------------------------------------------------------------------------------

    def runPyRelVals(self, deps = []):
        if not self.doRelVal:
            print "runTests> Found request to NOT run python relvals"
            return None
        print "runTests> Going to run python relvals"
        cmd = scriptPath+'/runPyRelVal.py --nproc 8 '
        if self.RelValArgs: cmd += ' --args "'+self.RelValArgs+'" '
        thrd = None
        try:
          thrd = PyRelVals(self.cmsswBuildDir, self.logger,cmd , deps)
          thrd.start()
        except Exception, e :
            print "ERROR during pyRelVal : caught exception: " + str(e)
            pass
        return thrd

    # --------------------------------------------------------------------------------

    def runBuildReports(self, deps = []):
        print "DQMRefReport> Going to run python DQMRefReport"
        cmd = 'cd '+self.cmsswBuildDir+'; '+scriptPath+'/CompareBuildWithReference.py -b '+self.buildDir+' -s '+self.stamp+' -p '+ self.plat + ' -c ' + self.relCycle + ' -t ' + self.relTag + ' -r ' + self.cmsswBuildDir
        if self.dryRun: cmd = cmd + ' -d'
        thrd = None
        try:
            genRef = GenerateDQMRef(self.cmsswBuildDir)
            genRef.start()
            thrd = DQMRefReports(self.cmsswBuildDir, self.logger, cmd , deps+[genRef])
            thrd.start()
        except Exception, e :
            print "ERROR during DQMRefReport : caught exception: " + str(e)
            pass
        return thrd
    
    # --------------------------------------------------------------------------------

    def genReferenceManual(self, deps = []):
        try:
            if str(os.environ['SCRAM_ARCH']) == 'slc5_amd64_gcc462':
                cmd = 'scram b -f doxygen 2>&1 > genReferenceManual.log ;'
                cmd += 'chmod +w doc ;'
                cmd += 'scp -r doc cmsbuild@vocms12:/data/doxygen/'+self.relTag+' ;'
                cmd += 'scp '+self.relTag+'.index cmsbuild@vocms12:/data/doxygen/'+self.relTag+'/ ;'
                self.doCmd(cmd)
            else:
                print "build arch=" + str(os.environ['SCRAM_ARCH']) + ", we don't build reference manual for the arch"
        except Exception, e:
            print "ERROR: Caught exception during genReferenceManual : " + str(e)
        return  None

# ================================================================================

def usage():
    print "usage:", os.path.basename(sys.argv[0]), " [--appset <online/fwlite app set directory>] [--buildDir <buildDir>] [--releaseDir <dir>] [--dryRun]"
    return

# ================================================================================

def main():

    import getopt
    options = sys.argv[1:]
    try:
        opts, args = getopt.getopt(options, 'h', 
                                   ['help','releaseDir=','buildDir=','dryRun','only=','appset='])
    except getopt.GetoptError, msg:
        print msg
        usage()
        sys.exit(-2)

    buildDir = None
    rel = os.environ.get('CMSSW_BASE')
    dryRun = False
    only = None
    appset = None
    
    for o, a in opts:
        if o in ('-h', '--help'):
            usage()
            sys.exit()

        if o in ('--buildDir',):
            buildDir = a

        if o in ('--releaseDir',):
            rel = a

        if o in ('--dryRun',):
            dryRun = True

        if o in ('--only',):
            only = a

        if o in ('--appset',):
            appset = a
	    
    if not rel:
        print "No release specified !"
        sys.exit(0)
	
    if not buildDir:
        buildDir = rel

    if not appset:
        appset = buildDir+"/CMSDIST"
	
    os.environ['CMSINTBLD_RCDIR'] = buildDir
    os.chdir(rel)
    rb = ReleaseTester(buildDir,rel,appset)

    if dryRun:
        rb.setDryRun()

    try:
        rb.doTest(only)
    except Exception, e:
        print "ERROR: Caught exception during doTest : " + str(e)

    return

# ================================================================================

if __name__ == "__main__":

    main()
