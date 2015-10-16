#! /usr/bin/env python
import os, sys, glob, re, shutil, time, threading

def doCmd(cmd, dryRun=False, inDir=None):
    if not inDir:
        print "--> "+time.asctime()+ " in ", os.getcwd() ," executing ", cmd
    else:
        print "--> "+time.asctime()+ " in " + inDir + " executing ", cmd
        cmd = "cd " + inDir + "; "+cmd

    sys.stdout.flush()
    sys.stderr.flush()
    start = time.time()
    ret = 0
    while cmd.endswith(";"): cmd=cmd[:-1]
    if dryRun:
        print "DryRun for: "+cmd
    else:
        from commands import getstatusoutput
        ret, outX = getstatusoutput(cmd)
        if outX: print outX

    stop = time.time()
    print "--> "+time.asctime()+" cmd took", stop-start, "sec. ("+time.strftime("%H:%M:%S",time.gmtime(stop-start))+")"
    sys.stdout.flush()
    sys.stderr.flush()
    return ret

def runThreadMatrix(basedir, logger, workflow, args=''):
  workdir = os.path.join(basedir, workflow)
  matrixCmd = 'runTheMatrix.py -l ' + workflow +' '+args
  try:
    if not os.path.isdir(workdir):
      os.makedirs(workdir)
  except Exception, e: 
    print "runPyRelVal> ERROR during test PyReleaseValidation, workflow "+str(workflow)+" : can't create thread folder: " + str(e)
  wftime = time.time()
  try:
    ret = doCmd(matrixCmd, False, workdir)
  except Exception, e:
    print "runPyRelVal> ERROR during test PyReleaseValidation, workflow "+str(workflow)+" : caught exception: " + str(e)
  wftime = time.time() - wftime
  outfolders = [file for file in os.listdir(workdir) if re.match("^" + str(workflow) + "_", file)]
  if len(outfolders)==0: return
  outfolder = os.path.join(basedir,outfolders[0])
  wfdir     = os.path.join(workdir,outfolders[0])
  ret = doCmd("rm -rf " + outfolder + "; mkdir -p " + outfolder)
  ret = doCmd("find . -mindepth 1 -maxdepth 1 -name '*.xml' -o -name '*.log' -o -name '*.py' -o -name 'cmdLog' -type f | xargs -i mv '{}' "+outfolder+"/", False, wfdir)
  ret = doCmd("mv "+os.path.join(workdir,"runall-report-step*.log")+" "+os.path.join(outfolder,"workflow.log"))
  ret = doCmd("echo " + str(wftime) +" > " + os.path.join(outfolder,"time.log"))
  logger.updateRelValMatrixPartialLogs(basedir, outfolders[0])
  shutil.rmtree(workdir)
  return

class PyRelValsThread(object):
  def __init__(self, jobs, basedir, jobid="1of1"):
    self.jobs = jobs
    self.basedir = basedir
    self.jobid=jobid

  def startWorkflows(self, logger, add_args='', workflows=''):
    from commands import getstatusoutput
    add_args = add_args.replace('\\"','"')
    print "Extra Args>>",add_args
    workflowsCmd = "runTheMatrix.py -n "+workflows+" | grep -E '^[0-9].*\.[0-9][0-9]?' | sort -nr | awk '{print $1}'"
    print "RunTheMatrix>>",workflowsCmd
    cmsstat, workflows = getstatusoutput(workflowsCmd)
    print workflows
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
    ret, out = getstatusoutput("touch "+basedir+"/done."+self.jobid)
    logger.updateRelValMatrixPartialLogs(basedir, "done."+self.jobid)
    self.update_runall()
    self.parseLog()
    return

  def update_runall(self):
    outFile    = open(os.path.join(self.basedir,"runall-report-step123-.log"),"w")
    status_ok  = []
    status_err = []
    len_ok  = 0
    len_err = 0
    for logFile in glob.glob(self.basedir+'/*/workflow.log'):
      inFile = open(logFile)
      for line in inFile:
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
    logRE = re.compile('^.*/([1-9][0-9]*\.[0-9]+)[^/]+/step([1-9])_.*\.log$')
    max_steps = 0
    for logFile in glob.glob(self.basedir+'/[1-9]*/step[0-9]*.log'):
      m = logRE.match(logFile)
      if not m: continue
      wf = m.group(1)
      step = int(m.group(2))
      if step>max_steps: max_steps=step
      if not logData.has_key(wf):
        logData[wf] = {'steps': {}, 'events' : [], 'failed' : [], 'warning' : []}
      if not logData[wf]['steps'].has_key(step):
        logData[wf]['steps'][step]=logFile
    for wf in logData:
      for k in logData[wf]:
        if k == 'steps': continue
        for s in range(0, max_steps):
          logData[wf][k].append(-1)
      index =0
      for step in sorted(logData[wf]['steps']):
        warn = 0
        err = 0
        rd = 0
        inFile = open(logData[wf]['steps'][step])
        for line in inFile:
          if '%MSG-w' in line: warn += 1
          if '%MSG-e' in line: err += 1
          if 'Begin processing the ' in line: rd += 1
        inFile.close()
        logData[wf]['events'][index] = rd
        logData[wf]['failed'][index] = err
        logData[wf]['warning'][index] = warn
        index+=1
      del logData[wf]['steps']

    from pickle import Pickler
    outFile = open(os.path.join(self.basedir,'runTheMatrixMsgs.pkl'), 'w')
    pklFile = Pickler(outFile)
    pklFile.dump(logData)
    outFile.close()
    return

