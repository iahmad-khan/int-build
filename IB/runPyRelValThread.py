#! /usr/bin/env python
import os, sys, glob, re, shutil, time, threading
from commands import getstatusoutput
import cmd

def runThreadMatrix(basedir, logger, workflow, args=''):
  workdir = os.path.join(basedir, workflow)
  matrixCmd = 'cd '+workdir+' ; runTheMatrix.py -l ' + workflow +' '+args
  try:
    if not os.path.isdir(workdir):
      os.makedirs(workdir)
  except Exception, e: 
    print "runPyRelVal> ERROR during test PyReleaseValidation, workflow "+str(workflow)+" : can't create thread folder: " + str(e)
  try:
    print "Running>> ",matrixCmd
    ret, outX = getstatusoutput(matrixCmd)
    if ret:
      print "runPyRelVal> ERROR during test PyReleaseValidation, workflow "+str(workflow)+" : runTheMatrix exit with code: " + str(ret)
    if outX: print outX
  except Exception, e:
    print "runPyRelVal> ERROR during test PyReleaseValidation, workflow "+str(workflow)+" : caught exception: " + str(e)
  outfolders = [file for file in os.listdir(workdir) if re.match("^" + str(workflow) + "_", file)]
  if len(outfolders)==0: return
  outfolder = outfolders[0]
  ret, out=getstatusoutput("cd " + os.path.join(workdir,outfolder) + " ; find . -name '*.root' -o -name '*.py' -type f | xargs rm -rf")
  if ret: print ret
  logger.updateRelValMatrixPartialLogs(workdir, outfolder)
  ret, out=getstatusoutput("rm -rf " + os.path.join(basedir,outfolder) + " ; mv "+os.path.join(workdir,outfolder)+" "+basedir)
  ret, out=getstatusoutput("mv "+os.path.join(workdir,"runall-report-step*.log")+" "+os.path.join(basedir,outfolder,"workflow.log"))
  shutil.rmtree(workdir)
  return

class PyRelValsThread(object):
  def __init__(self, jobs, basedir):
    self.jobs = jobs
    self.basedir = basedir

  def startWorkflows(self, logger, workflows='', add_args=''):
    workflowsCmd = "runTheMatrix.py -n "+workflows+" | grep -E '^[0-9].*\.[0-9][0-9]?' | sort -nr | awk '{print $1}'"
    cmsstat, workflows = getstatusoutput(workflowsCmd)
    if not cmsstat:
      workflows = workflows.split("\n")
    else:
      print "runPyRelVal> ERROR during test PyReleaseValidation : could not get output of " + workflowsCmd
      return
    threads = []
    jobs = self.jobs
    m=re.search(".* (-j|--nproc)(=| )(\d+) "," "+add_args)
    if m: jobs=int(m.group(3))
    print "Running ",jobs," in parallel"
    while(len(workflows) > 0):
      threads = [t for t in threads if t.is_alive()]
      print "Active Threads:",len(threads)
      if(len(threads) < jobs):
        try:
          t = threading.Thread(target=runThreadMatrix, args=(self.basedir, logger, workflows.pop(), add_args))
          t.start()
          threads.append(t)
        except Exception, e:
          print "runPyRelVal> ERROR threading matrix : caught exception: " + str(e)
      else:
        time.sleep(5)
    for t in threads: t.join()
    self.update_runall(os.path.join(self.basedir,"runall-report-step123-.log"),os.path.join(self.basedir,'*','workflow.log'))
    self.parseLog()
    return

  def update_runall(self,outFileName,inFileReg):
    outFile    = open(os.path.join(self.basedir,"runall-report-step123-.log"),"w")
    status_ok  = []
    status_err = []
    len_ok  = 0
    len_err = 0
    for logFile in glob.glob(self.basedir+'/*/workflow.log'):
      inFile = open(logFile)
      for line in inFile:
        print line
        if re.match(".* tests passed, .*",line):
          res = line.strip().split(" tests passed, ")
          res[0] = res[0].split()
          res[1]=res[1].replace(" failed","").split()
          len_res = len(res[0])
          if len_res>len_ok:
            for i in range(len_ok,len_res): status_ok.append(0)
            len_ok = len_res
          for i in range(0,len_res):
            status_ok[i]=status_ok[i]+int(res[0][i])
          len_res = len(res[1])
          if len_res>len_err:
            for i in range(len_err,len_res): status_err.append(0)
            len_err = len_res
          for i in range(0,len_res):
            status_err[i]=status_err[i]+int(res[1][i])
        else:  outFile.write(line)
      inFile.close()
    outFile.write(" ".join(str(x) for x in status_ok)+" tests passed, "+" ".join(str(x) for x in status_err)+" failed\n")
    outFile.close()

  def parseLog(self):
    logData = {}
    logRE = re.compile('^([1-9][0-9]*\.[0-9]+)[^/]+/step([1-9])_.*\.log$')
    max_steps = 0
    for logFile in glob.glob(self.basedir+'/[1-9]*/step[0-9]*.log'):
      m = logRE.match(logFile)
      if not m: continue
      wf = m.group(1)
      step = int(m.group(2)) - 1
      if step>max_steps: max_steps=step
      if not logData.has_key(wf):
        logData[wf] = {'steps': {}, 'events' : [], 'failed' : [], 'warning' : []}
        logData[wf]['steps'][step]=logFile
    for wk in logData:
      for k in logData[wf].keys():
        if k == 'steps': continue
        for s in range(0, max_steps):
          logData[wf][k].append(-1)
      for step in logData[wf]['steps']:
        warn = 0
        err = 0
        rd = 0
        inFile = open(logData[wf]['steps'][step])
        for line in inFile:
          if '%MSG-w' in line: warn += 1
          if '%MSG-e' in line: err += 1
          if 'Begin processing the ' in line: rd += 1
        inFile.close()
        logData[wf]['events'][step] = rd
        logData[wf]['failed'][step] = err
        logData[wf]['warning'][step] = warn
        del logData[wf]['steps']

    from pickle import Pickler
    outFile = open(os.path.join(self.basedir,'runTheMatrixMsgs.pkl'), 'w')
    pklFile = Pickler(outFile)
    pklFile.dump(logData)
    outFile.close()
    return

