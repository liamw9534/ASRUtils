"""
SpeechRecord

An audio speech recorder module based upon pyaudio and wave.

Copyright (c) 2014 All Right Reserved, Liam Wickins

Please see the LICENSE file for more information.

THIS CODE AND INFORMATION ARE PROVIDED "AS IS" WITHOUT WARRANTY OF ANY 
KIND, EITHER EXPRESSED OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE
IMPLIED WARRANTIES OF MERCHANTABILITY AND/OR FITNESS FOR A
PARTICULAR PURPOSE.
"""

import pyaudio
import wave
import sys
import array
import numpy as np
import threading
import subprocess
import os

def CalcRmsPower(data):
  """Computes the RMS level of the last chunk of sound"""
  if (len(data) > 0):
    nums = array.array('h', ''.join(data))
    sq = [i**2 for i in nums]
    return np.sqrt(np.sum(sq)/len(data))
  return 0

class SpeechRecord:

  # Default options suitable for voice sampling (can be overridden)
  FORMAT = pyaudio.paInt16   # 16-bit is generally good enough for speech
  CHANNELS = 1               # 1=>Mono, 2=>Stereo
  RATE = 8000                # Sample rate

  def __init__(self, format=FORMAT, channels=CHANNELS, rate=RATE,
               callback=None):
               
    """Establishes an audio stream and empties the frame buffer"""
    self.p = pyaudio.PyAudio()
    self.format = format
    self.rate = rate
    self.channels = channels
    self.chunk = self.rate/4
    self.__Flush()
    self.recordThread = None
    self.callback = callback
    self.recordEvent = threading.Event()

    # Open input stream to audio device
    self.stream = self.p.open(format=format,
                              channels=channels,
                              rate=rate,
                              input=True,
                              frames_per_buffer=self.chunk)

  # Meta class for background sound recording
  class __BackgroundRecordThread__(threading.Thread):

    def __init__(self, event, stream, parent, callback, rate, chunk, maxSeconds,
                 timeout, initTimeout):

      threading.Thread.__init__(self)
      self.event = event
      self.stream = stream
      self.rate = rate
      self.chunk = chunk
      self.parent = parent
      self.callback = callback
      self.completeEvent = event
      self.recordThread = None
      self.stop = False
      self.initTimeout=initTimeout
      self.timeout=timeout
      self.startdelay = 1
      self.maxSeconds=maxSeconds

    def Exit(self):
       self.stop = True
       self.join()

    def __RecordChunk(self):
      """Records a new chunk from the audio stream"""
      self.parent.frames.append(self.stream.read(self.chunk))

    def run(self):
      """Record an input wavefrom using an starting power detector and
         quiescence timeout
      """

      # Ignore the first part which might contain noise caused by a
      # key or mouse press
      #for i in range(0, int((self.rate * self.ignoreFirst) / self.chunk)):
      #  self.__RecordChunk()

      # Quickly calculate the ambient noise level
      self.__RecordChunk()
      rms = CalcRmsPower(self.parent.frames[-1:])
      #print "**** Ambient noise: ", rms
      minRmsThreshold = rms * 4
      self.parent.frames = []

      # Power detector
      recording = False
      for i in range(0, int((self.rate * self.initTimeout) / self.chunk)):
        if (self.stop):
          break
        self.__RecordChunk()
        rms = CalcRmsPower(self.parent.frames[-1:])
        if (rms > minRmsThreshold):
          # Truncate back to 'startdelay'
          k = int((self.rate * self.startdelay) / self.chunk)
          #print "Truncation:", k
          if (len(self.parent.frames) >= k):
            #print "Truncated back", k, "frames"
            self.parent.frames = self.parent.frames[-k:]
          recording = True
          print "**** Output detected:", rms
          break

      # Record until quiescent or stop request
      maxChunks = (self.timeout*self.rate) / self.chunk
      #print "maxChunks=", maxChunks
      if (recording):
        quiescentChunks = 0
        for i in range(0, int((self.rate * self.maxSeconds) / self.chunk)):
          self.__RecordChunk()
          rms = CalcRmsPower(self.parent.frames[-1:])
          if (rms <= minRmsThreshold):
            quiescentChunks += 1  # Things have gone quiet
            #print "Quiet for", quiescentChunks, "frames"
          else:
            quiescentChunks = 0                    # Ok, back again
            #print "Ok, again:", quiescentChunks
          if (quiescentChunks == maxChunks):
            # Remove last frames of silence
            if (len(self.parent.frames) >= maxChunks):
              self.parent.frames = self.parent.frames[:-maxChunks]
            break
          if (self.stop):
            #print "Stopped externally"
            break
        #print "Finished recording"
      else:
        # Flush record buffer
        self.parent.frames = []

      # Post completion event
      self.event.set()

      # Call user callback if defined
      if (self.callback):
        self.callback()

  def StartRecord(self, maxSeconds=60, timeout=2, initTimeout=3):

    # Clean up if already running
    self.StopRecord()

    # Flush buffer
    self.__Flush()

    # Start background thread
    self.recordThread = \
      self.__BackgroundRecordThread__(self.recordEvent, self.stream,
                                      self,
                                      self.callback,
                                      self.rate, self.chunk,
                                      maxSeconds,
                                      timeout, initTimeout)
    self.recordThread.start()

  def StopRecord(self):
    if (not self.IsRecordComplete()):
      self.recordThread.Exit()
      self.recordThread = None
      self.recordEvent.clear()

  def WaitRecordComplete(self, timeout=10):
    if (self.recordThread):
      if (self.recordEvent.wait(timeout)):
        self.recordEvent.clear()
        return True
      else:
        return False
    return True

  def IsRecordComplete(self):
    if (self.recordThread is None):
      return True
    else:
      return self.WaitRecordComplete(0)

  def GetRecordingInfo(self):
    sz = len(self.frames)
    if (sz >= 2):
      power = CalcRmsPower(self.frames[-2:])
    else:
      power = 0
    return (sz, power)

  def __Flush(self):
    self.frames = []

  def WriteFileAndClose(self, outputFileName='output.wav'):
    """Write everything recorded out to a wave file"""
    ext = outputFileName.split('.')[-1]
    if (ext != 'wav'):
      filename = '.'.join(outputFileName.split('.')[:-1]) + '.wav'
    else:
      filename = outputFileName

    wf = wave.open(filename, 'wb')
    wf.setnchannels(self.channels)
    wf.setsampwidth(self.p.get_sample_size(self.format))
    wf.setframerate(self.rate)
    wf.writeframes(b''.join(self.frames))
    wf.close()
    
    # Convert to different audio format (supported by sox)
    if (ext != 'wav'):
      cmd = ['sox', filename, '-t', ext, outputFileName ]
      with open(os.devnull, 'w') as devnull:
        task = subprocess.Popen(cmd, stdout=devnull, stderr=devnull)
        task.wait()
      os.remove(filename)    # Remove the origin .wav file

  def Exit(self):
    self.StopRecord()
    self.stream.stop_stream()
    self.stream.close()
    self.p.terminate()

