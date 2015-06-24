#! /usr/bin/env python
import os, sys, glob, re, shutil, time, threading
from commands import getstatusoutput
import cmd

def runThreadMatrix(basedir, logger, allLog, threadID, workflow, args=''):
    workdir = os.path.join(basedir, "thread" + str(threadID))
    matrixCmd = 'cd '+workdir+' ; runTheMatrix.py -l ' + str(workflow)+' '+args
    try:
        if not os.path.isdir(workdir):
            os.makedirs(workdir)
    except Exception, e:
        print "runPyRelVal> ERROR during test PyReleaseValidation, workflow "+str(workflow)+" : can't create thread folder: " + str(e)
    try:
        ret, outX = getstatusoutput(matrixCmd)
        if ret:
            print "runPyRelVal> ERROR during test PyReleaseValidation, workflow "+str(workflow)+" : runTheMatrix exit with code: " + str(ret)
        if outX: print outX
    except Exception, e:
        print "runPyRelVal> ERROR during test PyReleaseValidation, workflow "+str(workflow)+" : caught exception: " + str(e)
    try:
        logFile = open(os.path.join(workdir,'runall-report-step123-.log'), 'r')
    except Exception, e:
        print "runPyRelVal> ERROR during test PyReleaseValidation, workflow "+str(workflow)+" : did not produce valid runall-report, quit: " + str(e)
        return
    for line in logFile:
        if re.match("^"+str(workflow)+"_", line) is not None:
            try:
                with open(allLog, "a") as allLogs:
                    allLogs.write(line)
                    allLogs.close()
            except:
                print "runPyRelVal> ERROR during test PyReleaseValidation, workflow "+str(workflow)+" : caught exception: " + str(e)
    logFile.close()
    shutil.move(os.path.join(workdir,'runall-report-step123-.log'), os.path.join(workdir,'runall-Thread'+str(threadID)+'.log'))
    outfolder = [file for file in os.listdir(workdir) if re.match("^" + str(workflow) + "_", file)][0]
    ret, out=getstatusoutput("cd " + os.path.join(workdir,outfolder) + " ; find . -name '*.root' -o -name '*.py' -type f | xargs rm -rf")
    if ret: print ret
    logger.updateRelValMatrixPartialLogs(workdir, outfolder)
    shutil.move(os.path.join(workdir,outfolder), ".")
    shutil.rmtree(workdir)
    
    return

class PyRelValsThread(object):
    def __init__(self, jobs, basedir):
        self.StepsPerJob = 4
        self.jobs = jobs
        self.basedir = basedir

    def startWorkflows(self, logger, add_args=''):
        allLog = "runall-report-step123-.log"
        try:
            open(os.path.join(self.basedir,allLog), 'a').close()
        except Exception, e:
            print "runPyRelVal> ERROR during test PyReleaseValidation : caught exception: " + str(e)
        workflowsCmd = "runTheMatrix.py -n | grep -E '[0-9].*\.[0-9][0-9]?' | sort -nr | awk '{print $1}'"
        cmsstat, workflows = getstatusoutput(workflowsCmd)
        if not cmsstat:
            workflows = workflows.split("\n")
        else:
            print "runPyRelVal> ERROR during test PyReleaseValidation : could not get output of " + workflowsCmd
            return
        threads = []
        while(len(workflows) > 0):
            if(len([t for t in threads if t.is_alive()]) < self.jobs):
                try:
                    t = threading.Thread(target=runThreadMatrix, args=(self.basedir, logger, allLog, len(threads)+1, workflows.pop(), add_args))
                    t.start()
                    threads.append(t)
                except Exception, e:
                    print "runPyRelVal> ERROR threading matrix : caught exception: " + str(e)
            else:
                 time.sleep(5)
        for t in threads:
            t.join()
        self.parseLog()
        return
  
    def parseLog(self):
        logData = {}
        logRE = re.compile('^([1-9][0-9]*\.[0-9]+)[^/]+/step([1-9])_.*\.log$')
        for logFile in glob.glob(self.basedir+'/[1-9]*/step[0-9]*.log'):
            m = logRE.match(logFile)
            if not m: continue
            wf = m.group(1)
            step = int(m.group(2)) - 1
            if step >= self.StepsPerJob: continue
            if not logData.has_key(wf):
                logData[wf] = {'events' : [], 'failed' : [], 'warning' : []}
                for s in range(0, self.StepsPerJob):
                    for k in logData[wf].keys(): logData[wf][k].append(-1)
            warn = 0
            err = 0
            rd = 0
            inFile = open(logFile)
            for line in inFile:
                if '%MSG-w' in line: warn += 1
                if '%MSG-e' in line: err += 1
                if 'Begin processing the ' in line: rd += 1
            inFile.close()
            logData[wf]['events'][step] = rd
            logData[wf]['failed'][step] = err
            logData[wf]['warning'][step] = warn

        from pickle import Pickler
        outFile = open(os.path.join(self.basedir,'runTheMatrixMsgs.pkl'), 'w')
        pklFile = Pickler(outFile)
        pklFile.dump(logData)
        outFile.close()
        return
                
