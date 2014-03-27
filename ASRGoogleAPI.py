"""
ASRGoogleAPI

An ASR instance wrapper built around Google Speech Recognition API.

Dependencies: SpeechRecord

Copyright (c) 2014 All Right Reserved, Liam Wickins

Please see the LICENSE file for more information.

THIS CODE AND INFORMATION ARE PROVIDED "AS IS" WITHOUT WARRANTY OF ANY 
KIND, EITHER EXPRESSED OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE
IMPLIED WARRANTIES OF MERCHANTABILITY AND/OR FITNESS FOR A
PARTICULAR PURPOSE.
"""

from SpeechRecord import SpeechRecord
import threading
import os
import sys
import subprocess
import json
import requests

class ASRGoogleAPI(threading.Thread):

  MAXRECTIME = 15          # 15s is the max. permitted duration by Google
  RATE = 16000             # 16KHz is only rate supported by Google
  INITIALTIMEOUT = 10      # How long to wait before aborting start
  DEFAULTTIMEOUT = 2       # How long to wait before aborting end
  MINLENGTH = 4            # Minimum number of frames in recording to submit

  def __init__(self, callback, timeout=DEFAULTTIMEOUT, tag='google'):
    self.queue = []
    self.event = threading.Event()
    self.stop = False
    self.isPlaying = False
    self.counter = 0
    self.pending = False
    self.flushing = False
    self.timeout = timeout
    self.callback = callback
    self.tag = tag
    self.rec = SpeechRecord(rate=self.RATE, callback=self.__RecordingComplete)
    threading.Thread.__init__(self)
    self.start()

  def __StartNewRecording(self):
    self.pending = True
    #print "* Started new recording"
    self.rec.StartRecord(maxSeconds=self.MAXRECTIME,
                         timeout=self.timeout,
                         initTimeout=self.INITIALTIMEOUT)
 
  def __RecordingComplete(self):
    self.pending = False
    info = self.rec.GetRecordingInfo()
    #print "* Recording complete:", info[0], "frames"
    if (info[0] >= self.MINLENGTH and self.isPlaying):
      filename = "__ASRGoogleAPI__" + str(self.counter) + ".flac"
      self.rec.WriteFileAndClose(filename)
      self.counter += 1
      self.__Enqueue(filename)
      #print "* Queued:", filename
      self.event.set()
    if (self.isPlaying):
      self.__StartNewRecording()

  def __GoogleAPITransaction(self, filename):

    url = 'https://www.google.com/speech-api/v1/recognize?client=chromium&lang=en-QA&maxresults=10'
    headers = { 'Content-Type': 'audio/x-flac; rate='+str(self.RATE)+';' }
    fd = open(filename, 'r')
    files = { 'file': (filename, fd) }
    r = requests.post(url, files=files, headers=headers)
    fd.close()
    text = r.text

    try:
      resp = json.loads(text)
      if ('status' in resp.keys() and resp['status'] == 0):
        if ('hypotheses' in resp.keys() and len(resp['hypotheses']) > 0):
          return [resp['hypotheses'][i]['utterance'].upper() for i in range(0,len(resp['hypotheses']))]
    except:
      print "Was not able to process API response:", sys.exc_info()[0]
      print "Raw text for debug:", text

    return None

  def __Enqueue(self, filename):
    self.queue += [filename]
    #print "* Queue contents: ", self.queue

  def __Dequeue(self):
    if (len(self.queue) > 0):
      head = self.queue[0]
      self.queue = self.queue[1:]
      return head
    return None

  def __Remove(self, filename):
    os.remove(filename)

  def Flush(self):
    self.flushing = True

  def run(self):
    while (not self.stop):
      self.event.wait()
      self.event.clear()
      #print "* Woken up to check the queue"
      while (True):
        filename = self.__Dequeue()
        #print "* Got the following:", filename
        if (filename):
          if (self.isPlaying and not self.flushing):
            resp = self.__GoogleAPITransaction(filename)
            if (resp and self.callback):
              self.callback('result', self.tag, resp)
          #else:
            #print "* Ignoring since isPlaying:", self.isPlaying
          self.__Remove(filename)
        else:
          self.flushing = False
          break
 
  def IsPlaying(self):
    return self.isPlaying

  def Play(self):
    if (self.isPlaying is False):
      self.isPlaying = True
      self.__StartNewRecording()

  def Pause(self):
    self.isPlaying = False

  def Exit(self):
    self.Pause()
    self.stop = True
    self.event.set()
    self.join()

