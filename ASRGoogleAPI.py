"""
ASRGoogleAPI

An ASR instance wrapper built around Google Speech Recognition API.

Dependencies: ..

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

  MAXRECTIME = 15

  def __init__(self, callback, timeout=2, tag='google'):
    self.queue = []
    self.event = threading.Event()
    self.stop = False
    self.isPlaying = False
    self.counter = 0
    self.pending = 0
    self.flushRequest = False
    self.timeout = timeout
    self.callback = callback
    self.tag = tag
    self.rec = SpeechRecord(rate=16000, callback=self.__RecordingComplete)
    threading.Thread.__init__(self)
    self.start()

  def __StartNewRecording(self):
    self.pending += 1
    #print "Started new recording. Pending:", self.pending
    self.rec.StartRecord(maxSeconds=self.MAXRECTIME,
                         timeout=self.timeout,
                         initTimeout=0.5)
 
  def __RecordingComplete(self):
    self.pending -= 1
    #print "Recording complete. Pending:", self.pending, "Flush:", self.flushRequest
    info = self.rec.GetRecordingInfo()
    #print "* Recording complete:", info[0], "frames"
    if (info[0] > 0 and not self.flushRequest):
      filename = "__ASRGoogleAPI__" + str(self.counter) + ".flac"
      self.rec.WriteFileAndClose(filename)
      self.counter += 1
      self.__Enqueue(filename)
      self.event.set()
    if (self.pending == 0):
      self.flushRequest = False
    if (self.IsPlaying()):
      self.__StartNewRecording()

  def __GoogleAPITransaction(self, filename):

    url = 'https://www.google.com/speech-api/v1/recognize?client=chromium&lang=en-QA&maxresults=10'
    headers = { 'Content-Type': 'audio/x-flac; rate=16000;' }
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
    self.flushRequest = True

  def run(self):
    while (not self.stop):
      self.event.wait()
      self.event.clear()
      #print "* Woken up to check the queue"
      while (True):
        filename = self.__Dequeue()
        #print "* Got the following:", filename
        if (filename):
          if (self.isPlaying and not self.flushRequest):
            resp = self.__GoogleAPITransaction(filename)
            if (resp and self.callback):
              self.callback('result', self.tag, resp)
          self.__Remove(filename)
        else:
          break
 
  def IsPlaying(self):
    return self.isPlaying

  def Play(self):
    if (not self.isPlaying):
      self.isPlaying = True
      self.__StartNewRecording()

  def Pause(self):
    self.isPlaying = False

  def Exit(self):
    self.Flush()
    self.Pause()
    self.stop = True
    self.event.set()
    self.join()

