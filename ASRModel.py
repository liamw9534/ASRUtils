"""
ASRModel

A toolbox of functions wrapped around CMU SPHINX to make it easier to
create, update and train ASR models.

Dependencies: pocketsphinx, sphinxtrain, espeech, mbrola, pyaudio
              lmtool hosted at speech.cs.cmu.edu

Copyright (c) 2014 All Right Reserved, Liam Wickins

Please see the LICENSE file for more information.

THIS CODE AND INFORMATION ARE PROVIDED "AS IS" WITHOUT WARRANTY OF ANY 
KIND, EITHER EXPRESSED OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE
IMPLIED WARRANTIES OF MERCHANTABILITY AND/OR FITNESS FOR A
PARTICULAR PURPOSE.
"""
import os, errno, shutil, uuid, subprocess, re, glob
from SpeechRecord import *

class ASRModelExceptionEnvironmentNotSetup:
  pass

class ASRModel:

  MODELS = "ASRMODELS"
  VOICES = "/usr/share/mbrola/voices/"
  SPHINXTRAIN = "/usr/local/lib/sphinxtrain/"
  WORDALIGN = "/usr/local/lib/sphinxtrain/scripts/decode/word_align.pl"
  SPHINXLIBEXEC = "/usr/local/libexec/sphinxtrain/"
  CMUSPEECHURL = "http://www.speech.cs.cmu.edu/cgi-bin/tools/lmtool/run"
  LOGIOSTOOLS = "~/Projects/cmusphinx-code-12331-trunk/logios/Tools"
  DICTCMD = "MakeDict/make_pronunciation.pl"
  TRAINING = "/training/"
  MODEL = "/model/"
  OUTPUT = "/output/"
  TEXT = ".txt"
  WAV = ".wav"
  TRAN = ".transcription"
  CORPUS = ".corpus"
  TGZ = ".tar.gz"
  FILEIDS = ".fileids"
  DICT = ".dic"
  LM = ".lm"
  HYP = ".hyp"
  RATE = 16000   # Don't change this, SPHINX only uses 16k or 8k
  NEWLINE = "\n"
  DEBUGFILE = "debug.log"

  def __RandName(self):
    return str(uuid.uuid4().hex)

  def __init__(self, name, model=None):

    self.name = name
    self.cwd = os.getcwd()
    self.models = os.getenv(self.MODELS)
    if (not self.models): raise ASRModelExceptionEnvironmentNotSetup
    if (self.models[-1] != '/'): self.models += '/'
    self.root = self.models + self.name
    self.training = self.root + self.TRAINING
    self.fileids = self.training + self.name + self.FILEIDS
    self.corpus = self.training + self.name + self.CORPUS
    self.trans = self.training + self.name + self.TRAN
    self.output  = self.root + self.OUTPUT
    self.__mkdir(self.root)
    self.__mkdir(self.training)
    self.__mkdir(self.output)
    self.__mkdir(self.root+self.MODEL)
    self.logfile = open(self.output + self.DEBUGFILE, 'w')
    # If no model is given, create a default HMM model
    if (model is None):
      model = self.__CreateHmmModelFromTarball()
    self.model = self.root + self.MODEL + model + "/"
    self.dict = self.model + self.name + self.DICT
    self.lm = self.model + self.name + self.LM
    # Load all IDs from training data
    self.GetAllIds()
    # Make sure corpus file exists if not already created
    with open(self.corpus, 'a') as f: f.close()

  def __chdir(self, path):
    try:
      cwd = os.getcwd()
      os.chdir(path)
    except OSError as exc:
      raise
    return cwd

  def __mkdir(self, path):
    try:
      os.makedirs(path)
    except OSError as exc:
      if exc.errno == errno.EEXIST and os.path.isdir(path):
        pass
      else:
        raise

  def __SendumpConvert(self):

    sendumpIn = self.model + 'sendump'
    mixOut = self.model + 'mixture_weights'
    sendumpCmd = self.SPHINXTRAIN + 'python/cmusphinx/sendump.py'
    cmd = [ 'python', sendumpCmd, sendumpIn, mixOut ]
    self.__RunCmd(cmd, debug=True)
 
  def __MdefConvert(self):

    mdefIn = self.model + 'mdef'
    mdefOut = mdefIn + self.TEXT
    cmd = [ 'pocketsphinx_mdef_convert', '-text', mdefIn, mdefOut ]
    self.__RunCmd(cmd, debug=True)

  def __CreateHmmModelFromTarball(self):
  
    model = "hub4wsj_sc_8k"
    tarball = self.models + model + self.TGZ
    cmd = [ 'tar', '-zxvf', tarball ]
    last = self.__chdir(self.root + self.MODEL)
    self.__RunCmd(cmd, debug=True)
    self.__chdir(last)
    return model

  def ListModels(self):

    path = self.root + self.MODEL
    return os.listdir(path)

  def PlayEntry(self, id):

    f = self.training + id + self.WAV
    if (os.path.exists(f)):
      # This relies on 'sox' being installed on local machine
      # FIXME: use pyaudio to play this instead
      cmd = [ 'play', f ]
      self.__RunCmd(cmd, debug=True)
      return True
    return False

  def FindSubstring(self, text):

    k = 0
    hits = []
    with open(self.corpus, 'r') as f:
      for line in f:
        res = text in line
        if (res):
          hits.append((k, line.strip()))
        k += 1
    return hits

  def FindContainsOrderedWords(self, text):

    k = 0
    hits = []
    words = text.split(' ')
    with open(self.corpus, 'r') as f:
      for line in f:
        nextpos = 0
        for w in words:
          pos = line[nextpos:].find(w)
          if (pos >= 0):
            nextpos += len(w)
          else:
            break
        if (pos >= 0):
          hits.append((k, line.strip()))
          k += 1
    return hits

  def FindStartsWith(self, text):

    k = 0
    hits = []
    with open(self.corpus, 'r') as f:
      for line in f:
        res = line.startswith(text)
        if (res):
          hits.append((k, line.strip()))
        k += 1
    return hits

  def Find(self, regexp):

    k = 0
    hits = []
    with open(self.corpus, 'r') as f:
      for line in f:
        res = re.findall(regexp, line)
        if (res):
          hits.append((k, line.strip()))
        k += 1
    return hits

  def DeleteCorpus(self):
    with open(self.corpus, 'w') as f: f.close()

  def DeleteModel(self, id):

    f = self.root + self.MODEL + id
    print "Deleting", id
    if (os.path.exists(f)):
      shutil.rmtree(f)
      return True
    else:
      return False

  def DeleteEntry(self, id):

    f = self.training + id + self.TEXT
    if (os.path.exists(f)):
      os.remove(f)
      f = self.training + id + self.WAV
      if (os.path.exists(f)):
        os.remove(f)
      return True
    return False

  def __TextToWaveFile(self, path, sent):

    rate = 115
    voice = 'mb-en1'
    mbvoice = self.VOICES + 'en1'
    pho = '/tmp/tmp.pho'
    # This relies on 'espeak' to generate phonics output
    # which is then used by 'mbrola' text-to-voice software.
    cmd = [ 'espeak', '-s', str(rate), '-v', voice, '"'+sent+'"', '--pho',
            '--phonout', pho ]
    self.__RunCmd(cmd, debug=True)
    cmd = ['mbrola', mbvoice, pho, path ]
    self.__RunCmd(cmd, debug=True)

  def AutoAddUtterancesFile(self, path, numEntries=None):
    new = []
    k = 0
    with open(path, 'r') as f:
      for line in f:
        if (numEntries is not None and k == numEntries): break
        new.append(self.AutoAddUtterance(line.strip()))
        k += 1
      f.close()
    return new

  def AddUtterancesFile(self, path, numEntries=None):
    new = []
    k = 0
    with open(path, 'r') as f:
      for line in f:
        if (numEntries is not None and k == numEntries): break
        u = self.AddUtterance(line.strip())
        if (u is not None):
          new.append(u)
        k += 1
      f.close()
    return new

  def AutoAddUtterance(self, sent):

    id = self.AddSentence(sent)
    path = self.root + self.TRAINING + id + self.WAV
    self.__TextToWaveFile(path, sent)
    return id

  def AddUtterance(self, sent):

    sr = SpeechRecord(rate=self.RATE)
    sr.StartRecord()
    print "**** Recording:", sent
    sr.WaitRecordComplete()
    info = sr.GetRecordingInfo()
    if (info[0] > 0):     # Only save the file if it has data
      id = self.AddSentence(sent)
      path = self.root + self.TRAINING + id + self.WAV
      sr.WriteFileAndClose(path)
      sr.Exit()
      return (info, id)
    print "**** No sound detected!"
    return None

  def AddSentence(self, sent, id=None):

    if (id is None):
      id = self.__RandName()
    path = self.root + self.TRAINING + id + self.TEXT
    with open(path, 'w') as f:
      f.write(sent.upper())
      f.close() 
    return id

  def UpdateTraining(self):
    self.GetAllIds()
    self.__WriteFileids()
    self.__WriteTranscriptions()

  def BuildModel(self, name=None):
    self.__MakeAdaptDir(name)
    self.__BuildDict()
    self.__MakeAcousticFeatures()
    self.__CollectStatistics()
    self.__MLLRTransform()
    self.__MAPAdapt()
    self.__MakeSendump()
    self.model = self.adapt   # Transition to new model

  def TestModel(self, name=None, path=None):

    # If no test directory is given, simply use the training directory
    # as a self-test of how good the model is...
    if (path is None or name is None):
      name = self.name
      path = self.training
      fileids = self.fileids
      hyp = self.training + self.name + self.HYP
    else:
      fileids = path + "/" + name + self.FILEIDS
      hyp = self.training + self.name + self.HYP

    cmd = [ 'pocketsphinx_batch', '-adcin', 'yes', '-cepdir', 
            path, '-cepext', self.WAV, '-ctl', fileids,
            '-lm', self.lm, '-dict', self.dict, '-hmm', self.model,
            '-hyp', hyp ]
    self.__RunCmd(cmd, debug=True)
    cmd = [ self.WORDALIGN, self.trans, hyp ] 
    resp = self.__RunCmd(cmd)
    return resp[0]

  def ReadSentence(self, id):

    path = self.root + self.TRAINING + id + self.TEXT
    with open(path, 'r') as f:
      sent = f.read()
      f.close() 
      return sent

  def GetTrainingSize(self):
    return len(self.idList)

  def GetCorpusSize(self):
    k = 0 
    with open(self.corpus, 'r') as f:
      for line in f:
        k = k + 1
    return k

  def GetAllIds(self):

    path = self.training
    self.textFiles = [f for f in os.listdir(path) if f.endswith(self.TEXT)]
    self.waveFiles = [f for f in os.listdir(path) if f.endswith(self.WAV)]
    self.idList = [self.__GetIdFromFile(f) for f in self.textFiles]
    return self.idList
 
  def AddCorpus(self, sent):

    with open(self.corpus, 'a') as f:
      f.write(sent.upper()+self.NEWLINE)
      f.close()

  def AddFileToCorpus(self, path):

    k = 0
    with open(self.corpus, 'a') as f:
      with open(path, 'r') as r:
        for line in r:
          k += 1
          f.write(line.upper())
        r.close()
      f.close()
    return k

  def __GetIdFromFile(self, path):
    return path[:-4]
    
  def __WriteTranscriptions(self):

    with open(self.trans, 'w') as f:
      for w in self.waveFiles:
        id = self.__GetIdFromFile(w)
        with open(self.training+id+self.TEXT, 'r') as r:
          sent = r.read()
          trans = "<s> " + sent + " </s> (" + id + ")"
          r.close()
        f.write(trans + self.NEWLINE)
      f.close() 

  def __WriteFileids(self):

    with open(self.fileids, 'w') as f:
      for w in self.waveFiles:
        # Only wave files are admissible for SPHINX training
        id = self.__GetIdFromFile(w)
        f.write(id + self.NEWLINE)
      f.close()

  def __RunCmd(self, cmd, debug=False):

    #print ">>>> Command:", ' '.join(cmd)
    if (not debug):
      task = subprocess.Popen(cmd, stderr=subprocess.PIPE, stdout=subprocess.PIPE)
      stdout = task.stdout.read()
      stderr = task.stderr.read()
      task.wait()
      #print ">>>> Stdout:", stdout
      #print ">>>> Stderr:", stderr
      return (stdout, stderr)
    else:
      with open(os.devnull, 'w') as devnull:
        task = subprocess.Popen(cmd, stdout=self.logfile, stderr=devnull)
        task.wait()

  def __MakeAcousticFeatures(self):

    featParams = self.model + 'feat.params'
    cmd = [ 'sphinx_fe', '-argfile', featParams,
            '-samprate', str(self.RATE), '-c', self.fileids,
            '-di', self.training, '-do', self.training, '-ei', 'wav',
            '-eo', 'mfc', '-mswav', 'yes' ] 
    self.__RunCmd(cmd, debug=True)

  def __CollectStatistics(self):

    mdef = self.model + "mdef.txt"
    bwCmd = self.SPHINXLIBEXEC + 'bw'

    last = self.__chdir(self.training)
    cmd = [ bwCmd, '-hmmdir', self.model[:-1], '-moddeffn', mdef,
            '-ts2cbfn', '.semi.', '-feat', '1s_c_d_dd',
            '-svspec', '0-12/13-25/26-38', '-cmn', 'current',
            '-agc', 'none', '-dictfn', self.dict, '-ctlfn', self.fileids,
            '-lsnfn', self.trans, '-accumdir', self.output[:-1] ]
    self.__RunCmd(cmd, debug=True)
    self.__chdir(last)

  def __MLLRTransform(self):

    means = self.model + "means"
    variances = self.model + "variances"
    mllrCmd = self.SPHINXLIBEXEC + 'mllr_solve'
    mllrOut = self.output + 'mllr_matrix'
    cmd = [ mllrCmd, '-meanfn', means, '-varfn', variances,
           '-outmllrfn', mllrOut, '-accumdir', self.output[:-1] ]
    self.__RunCmd(cmd, debug=True)

  def __MakeAdaptDir(self, name):

    if (name is None):
      id = self.__RandName()
    else:
      id = name
    self.adapt = self.root + self.MODEL + id + "/"
    shutil.copytree(self.model, self.adapt)

  def __MAPAdapt(self):

    means = self.model + "means"
    var = self.model + "variances"
    mw = self.model + "mixture_weights"
    tm = self.model + "transition_matrices"
    ameans = self.adapt + "means"
    avar = self.adapt + "variances"
    amw = self.adapt + "mixture_weights"
    atm = self.adapt + "transition_matrices"
    mapCmd = self.SPHINXLIBEXEC + 'map_adapt'
    
    cmd = [ mapCmd, '-meanfn', means, '-varfn', var,
            '-mixwfn', mw, '-tmatfn', tm, '-accumdir', self.output[:-1],
            '-mapmeanfn', ameans, '-mapvarfn' , avar,
            '-mapmixwfn', amw, '-maptmatfn', atm ]
    self.__RunCmd(cmd, debug=True)

  def __MakeSendump(self):

    mdef = self.adapt + "mdef.txt"
    mw = self.adapt + "mixture_weights"
    sendump = self.adapt + "sendump"
    mkCmd = self.SPHINXLIBEXEC + 'mk_s2sendump'
    cmd = [ mkCmd, '-pocketsphinx', 'yes', '-moddeffn', mdef,
            '-mixwfn', mw, '-sendumpfn', sendump ]
    self.__RunCmd(cmd, debug=True)

  def __BuildDict(self):

    nval = 3    # Only 3-gram model is supported at the moment
    wfreq = self.training + self.name + '.wfreq'
    context = self.training + self.name + '.ccs'
    cmd = [ 'text2wfreq', '<', self.corpus, '>', wfreq ]
    #self.__RunCmd(cmd, debug=False)
    os.system(' '.join(cmd))
    vocab = self.adapt + self.name + '.vocab'
    cmd = [ 'wfreq2vocab', '<', wfreq, '>', vocab ]
    #self.__RunCmd(cmd, debug=False)
    os.system(' '.join(cmd))
    cmd = [ "echo '<s>'", '>>', vocab ]
    os.system(' '.join(cmd))
    #self.__RunCmd(cmd, debug=False)
    cmd = [ "echo '</s>'", '>>', vocab ]
    os.system(' '.join(cmd))
    #self.__RunCmd(cmd, debug=False)
    idngram = self.training + self.name + '.idngram'
    cmd = [ 'text2idngram', '-n', str(nval), '-idngram', idngram, '-vocab', vocab,
            '<', self.corpus ]
    os.system(' '.join(cmd))
#    cmd = [ "echo '<S>'", '>', context ]
#    os.system(' '.join(cmd))
#    cmd = [ "echo '</S>'", '>>', context ]
#    os.system(' '.join(cmd))
    binlm = self.training + self.name + '.binlm'
#    cmd = [ 'idngram2lm', '-context', context, '-n', str(nval), '-idngram', idngram, '-vocab', vocab,
    cmd = [ 'idngram2lm', '-n', str(nval), '-idngram', idngram, '-vocab', vocab,
            '-binary', binlm ]
    os.system(' '.join(cmd))
    #self.__RunCmd(cmd, debug=False)
    cmd = [ 'binlm2arpa', '-binary', binlm, '-arpa', self.adapt + self.name + '.lm' ]
    os.system(' '.join(cmd))
    #self.__RunCmd(cmd, debug=False)
    mkdict = self.LOGIOSTOOLS + '/' + self.DICTCMD
    cmd = [ mkdict, '-tools', self.LOGIOSTOOLS, '-dictdir', self.adapt,
            '-words', self.name + '.vocab', '-dict', self.name + '.dic' ]
    os.system(' '.join(cmd))

    # Setup new directories
    self.dict = self.adapt + self.name + self.DICT
    self.lm = self.adapt + self.name + self.LM

  def __BuildDictOnline(self):

    # Setup new directories
    self.dict = self.adapt + self.name + self.DICT
    self.lm = self.adapt + self.name + self.LM

    # This is all done using online service by sending the entire corpus
    # We use CURL to build a HTTP FORM POST request
    # FIXME: Would be better to do this offline using 'logios'
    corpus = "corpus=@" + self.corpus
    cmd = [ 'curl', '-F', corpus, self.CMUSPEECHURL ]
    r = self.__RunCmd(cmd)
    # The response should have the 'Location:' of the result
    loc = re.findall('Location: (.*)\r', r[0])[0]
    cmd = [ 'curl', loc ]
    r = self.__RunCmd(cmd)
    # The output file is encoded in the HTML in bold text, pull it out
    ident = re.findall('<b>(\d+)</b>', r[0])[0]
    dictUrl = loc + ident + ".dic"
    lmUrl = loc + ident + ".lm"
    # We only need the .lm and .dic files, so fetch those
    cmd = [ 'curl', dictUrl, '-o', self.dict ]
    self.__RunCmd(cmd, debug=True)
    cmd = [ 'curl', lmUrl, '-o', self.lm ]
    self.__RunCmd(cmd, debug=True)

  def __repr__(self):
    return repr(self.__dict__)

