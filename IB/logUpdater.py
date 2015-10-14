#!/usr/bin/env python
 
import os, sys, time, threading

scriptPath = os.path.dirname( os.path.abspath(sys.argv[0]) )
if scriptPath not in sys.path:
    sys.path.append(scriptPath)

from BuilderBase import BuilderBase, ActionError


# ================================================================================

class LogUpdater(BuilderBase):

    def __init__(self, dirIn=None, doCopy=True):

        BuilderBase.__init__(self)
    
        if dirIn:
            if not os.path.exists(dirIn):
                raise "ERROR: build dir ", dirIn, 'does not exist.'

        self.buildDir = dirIn
        self.release = None
        self.webTargetDir = None
	self.doCopy = doCopy
 
        return
    
    # --------------------------------------------------------------------------------

    def setRelease(self, rel, cycle, stamp):

        self.release  = rel
        self.relCycle = cycle
        self.stamp    = stamp
        
        from makeWebLog import WebLogger
        
        try:
            wl = WebLogger(self.stamp[:3], self.relCycle, self.dryRun) # pass in "day" as this may be late
            wl.prepare(self.release, self.relCycle+'-'+self.stamp, self.tcTag)
            self.webTargetDir = wl.getWebLogDir()
        except Exception, e:
            print "ERROR: Caught exception when getting info from  weblogger : " + str(e)

        return
    
    # --------------------------------------------------------------------------------

    def updateUnitTestLogs(self):
        
        print "\n--> going to copy unit test logs to", self.webTargetDir, '... \n'
        # copy back the test and relval logs to the install area
        # check size first ... sometimes the log _grows_ to tens of GB !!
        testLogs = ['unitTestLogs.zip','unitTests-summary.log','unitTestResults.pkl']
        for tl in testLogs:
            self.copyLogs(tl, '.', self.webTargetDir,False,self.cmsswBuildDir)
	return

     # --------------------------------------------------------------------------------

    def updateGeomTestLogs(self):
        
        print "\n--> going to copy Geom test logs to", self.webTargetDir, '... \n'
        testLogs = ['dddreport.log', 'domcount.log']
        for tl in testLogs:
            self.copyLogs(tl, '.', self.webTargetDir,False,self.cmsswBuildDir)
            self.copyLogs(tl, '.', os.path.join( self.webTargetDir, 'testLogs'),False,self.cmsswBuildDir)

        return

    # --------------------------------------------------------------------------------

    def updateDupDictTestLogs(self):
        
        print "\n--> going to copy dup dict test logs to", self.webTargetDir, '... \n'
        testLogs = ['dupDict-*.log']
        for tl in testLogs:
            self.copyLogs(tl, '.', self.webTargetDir,False,self.cmsswBuildDir)
            self.copyLogs(tl, '.', os.path.join( self.webTargetDir, 'testLogs'),False,self.cmsswBuildDir)

        return

   # --------------------------------------------------------------------------------

    def updateLogFile(self,fileIn,subTrgDir=None):
        
        desdir =  self.webTargetDir
        if subTrgDir: desdir = os.path.join(desdir, subTrgDir)
        print "\n--> going to copy "+fileIn+" log to ", desdir, '... \n'
        self.copyLogs(fileIn,'.', desdir,False,self.cmsswBuildDir)

        return

    # --------------------------------------------------------------------------------

    def updateCodeRulesCheckerLogs(self):
        
        print "\n--> going to copy cms code rules logs to", self.webTargetDir, '... \n'
        self.copyLogs('codeRules', '.',self.webTargetDir,True,self.cmsswBuildDir)

        return

    # --------------------------------------------------------------------------------

    def updateRelValMatrixLogs(self):

        print "\n--> going to copy pyrelval matrix logs to", self.webTargetDir, '... \n'
        subDir = 'pyRelval/'
        self.copyLogs('pyRelValMatrixLogs.zip' , subDir, self.webTargetDir,  True,self.cmsswBuildDir)
        self.copyLogs('runall*.log', subDir, os.path.join(self.webTargetDir, 'pyRelValMatrixLogs/run'),False,self.cmsswBuildDir)
        self.copyLogs('*.pkl'      , subDir, os.path.join(self.webTargetDir, 'pyRelValMatrixLogs/run'),False,self.cmsswBuildDir)

        return
        
    # --------------------------------------------------------------------------------
    
    def updateRelValMatrixPartialLogs(self, partialSubDir, dirToSend):
        
        destination = os.path.join(self.webTargetDir,'pyRelValPartialLogs') 
        print "\n--> going to copy pyrelval partial matrix logs to", destination, '... \n'
        self.copyLogs(dirToSend, partialSubDir, destination,  True,self.cmsswBuildDir)
        self.copyLogs('runall*.log', partialSubDir, destination,  True,self.cmsswBuildDir)

        return
        
    # --------------------------------------------------------------------------------


    def updateAddOnTestsLogs(self):

        print "\n--> going to copy addOn logs to", self.webTargetDir, '... \n'
        self.copyLogs('addOnTests.log' ,'.',self.webTargetDir, False,self.cmsswBuildDir)
        self.copyLogs('addOnTests.zip' ,'addOnTests/logs',self.webTargetDir, True,self.cmsswBuildDir)
        self.copyLogs('addOnTests.pkl' ,'addOnTests/logs',os.path.join(self.webTargetDir, 'addOnTests/logs'), True,self.cmsswBuildDir)

        return
        
    # --------------------------------------------------------------------------------

    def updateIgnominyLogs(self):

        print "\n--> going to copy ignominy logs to", self.webTargetDir, '... \n'
        testLogs = ['dependencies.txt.gz','products.txt.gz','logwarnings.gz','metrics']
        for tl in testLogs:
            self.copyLogs(tl, 'igRun', os.path.join( self.webTargetDir, 'igRun'),False,self.cmsswBuildDir)

        return
        
    # --------------------------------------------------------------------------------

    def updateProductionRelValLogs(self,workFlows):

        print "\n--> going to copy Production RelVals logs to", self.webTargetDir, '... \n'
        wwwProdDir = os.path.join( self.webTargetDir, 'prodRelVal')
        self.copyLogs('prodRelVal.log' ,'.',wwwProdDir, False,self.cmsswBuildDir)
        for wf in workFlows:
            self.copyLogs('timingInfo.txt' ,'prodRelVal/wf/'+wf,os.path.join( wwwProdDir,'wf', wf), False,self.cmsswBuildDir)

        return
        
    # --------------------------------------------------------------------------------

    def updateBuildSetLogs(self,appType='fwlite'):

        print "\n--> going to copy BuildSet logs to", self.webTargetDir, '... \n'
        wwwBSDir = os.path.join( self.webTargetDir, 'BuildSet')
	if self.doCopy: self.doCmd("rm -rf "+wwwBSDir+"/"+appType)
        self.copyLogs(appType ,'BuildSet',wwwBSDir, True,self.cmsswBuildDir)
        return
        
    # --------------------------------------------------------------------------------

    def copyLogs(self, what, logSubDir, tgtDirIn, useTar=False, fromDir=None):

        if not self.doCopy: return
	tgtDir = tgtDirIn

        if not os.path.exists(tgtDir) and not self.dryRun:
            try:
                if not 'slc7_amd64' in tgtDir:
                  os.makedirs(tgtDir)
            except:
                print "ERROR: could not create tgtDir for logs: "+tgtDir
                pass

        import stat
	if not fromDir:
	    fromDir = self.buildDir
	
	fromDir = os.path.join(fromDir, self.release, logSubDir)
        fromFile = os.path.join(fromDir, what)
        logSize = -1
        if '*' not in fromFile: # don't try this for wildcards
            try:
                info = os.stat(fromFile)
                logSize = info[stat.ST_SIZE]
            except Exception, e:
                print "WARNING: could not stat logFile "+fromFile+' got:'+str(e)
                print "         probably a wildcard, ignoring erroor ... "
                pass        # do nothing here, probably it was a wildcard.
            
        cmd = "cp -r "+fromFile+' '+tgtDir+'/.'
        if useTar:
            cmd = "cd "+fromDir+"; tar cf - "+what+' | (cd '+tgtDir+'; tar xf - ) '

        try:
            if not 'slc7_amd64' in tgtDir:
              self.doCmd(cmd)
        except Exception, e:
            print "Ignoring exception during copyLogs:", str(e)
            pass

        tgtDir = tgtDir.replace("/afs/cern.ch/cms/sw/ReleaseCandidates/","")
        ssh_opt="-o CheckHostIP=no -o ConnectTimeout=60 -o ConnectionAttempts=5 -o StrictHostKeyChecking=no -o BatchMode=yes -o PasswordAuthentication=no"
        cmssdt_ser="cmsbuild@cmssdt01.cern.ch"
        cmd ="ssh -Y "+ssh_opt+" "+cmssdt_ser+" mkdir -p /data/sdt/buildlogs/"+tgtDir+"; scp "+ssh_opt+" -r "+fromFile+" "+cmssdt_ser+":/data/sdt/buildlogs/"+tgtDir+"/"
        try:
            self.doCmd(cmd)
        except Exception, e:
            print "Ignoring exception during copyLogs:", str(e)
            pass

        return

    # --------------------------------------------------------------------------------

    def updateWeb(self, only):


        return
    


# ================================================================================

def usage():
    print "usage:", os.path.basename(sys.argv[0]), " --buildDir <buildDir> --rel <release> --cycle <cycle> --stamp <timestamp> [--only <listOfThings>] [--dryRun]"
    return

# ================================================================================

def main():

    import getopt
    options = sys.argv[1:]
    try:
        opts, args = getopt.getopt(options, 'h', 
                                   ['help','buildDir=', 'release=', 'dryRun','only=','cycle=','stamp='])
    except getopt.GetoptError, msg:
        print msg
        usage()
        sys.exit(-2)

    buildDir = None
    rel      = None
    dryRun   = False
    only     = None
    cycle    = None
    stamp    = None
    
    for o, a in opts:
        if o in ('-h', '--help'):
            usage()
            sys.exit()

        if o in ('--buildDir',):
            buildDir = a

        if o in ('--release',):
            rel = a

        if o in ('--dryRun',):
            dryRun = True

        if o in ('--only',):
            only = a

        if o in ('--cycle',):
            cycle = a

        if o in ('--stamp',):
           stamp = a


    if not cycle or not stamp or not rel or not buildDir:
        usage()
        sys.exit(-1)

    lu = LogUpdater(buildDir)
    lu.setRelease(rel, cycle, stamp)
    if dryRun:
        lu.setDryRun()

    try:
        lu.updateWeb(only)
    except Exception, e:
        print "ERROR: Caught exception during updating logs : " + str(e)

    return

# ================================================================================

if __name__ == "__main__":

    main()
