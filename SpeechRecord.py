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

def CalcRmsPower(data):
  """Computes the RMS level of the last chunk of sound"""
  nums = array.array('h', ''.join(data))
  sq = [i**2 for i in nums]
  return np.sqrt(np.sum(sq)/len(data))

class SpeechRecord:

  # Default options suitable for voice sampling (can be overridden)
  FORMAT = pyaudio.paInt16   # 16-bit is generally good enough for speech
  CHANNELS = 1               # 1=>Mono, 2=>Stereo
  RATE = 8000                # Sample rate

  def __init__(self, format=FORMAT, channels=CHANNELS, rate=RATE):
               
    """Establishes an audio stream and empties the frame buffer"""
    self.p = pyaudio.PyAudio()
    self.format = format
    self.rate = rate
    self.channels = channels
    self.chunk = self.rate/4
    print "Chunk size = ", self.chunk
    self.frames = []
    self.recordThread = None
    self.recordEvent = threading.Event()

    # Open input stream to audio device
    self.stream = self.p.open(format=format,
                              channels=channels,
                              rate=rate,
                              input=True,
                              frames_per_buffer=self.chunk)

  # Meta class for background sound recording
  class __BackgroundRecordThread__(threading.Thread):

    def __init__(self, event, stream, frames, rate, chunk, maxSeconds):

      threading.Thread.__init__(self)
      self.event = event
      self.stream = stream
      self.rate = rate
      self.chunk = chunk
      self.frames = frames
      self.completeEvent = event
      self.recordThread = None
      self.stop = False
      self.initTimeout=3
      self.timeout=2
      self.startdelay=2
      self.maxSeconds=maxSeconds
      self.minRmsThreshold=1000

    def Exit(self):
       self.stop = True
       self.join()

    def __RecordChunk(self):
      """Records a new chunk from the audio stream"""
      self.frames.append(self.stream.read(self.chunk))

    def run(self):
      """Record an input wavefrom using an starting power detector and
         quiescence timeout
      """

      # Ignore the first part which might contain noise caused by a
      # key or mouse press
      #for i in range(0, int((self.rate * self.ignoreFirst) / self.chunk)):
      #  self.__RecordChunk()

      # Power detector
      recording = False
      for i in range(0, int((self.rate * self.initTimeout) / self.chunk)):
        if (self.stop):
          break
        self.__RecordChunk()
        rms = CalcRmsPower(self.frames[-1])
        if (rms > self.minRmsThreshold):
          # Truncate back to 'startdelay'
          k = int((self.rate * self.startdelay) / self.chunk)
          #print "Truncation:", k
          if (len(self.frames) >= k):
            #print "Truncated back", k, "frames"
            self.frames = self.frames[-k:]
          recording = True
          break

      # Record until quiescent or stop request
      maxChunks = (self.timeout*self.rate) / self.chunk
      #print "maxChunks=", maxChunks
      if (recording):
        quiescentChunks = 0
        for i in range(0, int((self.rate * self.maxSeconds) / self.chunk)):
          self.__RecordChunk()
          rms = CalcRmsPower(self.frames[-1])
          if (rms <= self.minRmsThreshold):
            quiescentChunks += 1  # Things have gone quiet
            #print "Quiet for", quiescentChunks, "frames"
          else:
            quiescentChunks = 0                    # Ok, back again
            #print "Ok, again:", quiescentChunks
          if (quiescentChunks == maxChunks):
            #print "Stopped for being too quiet"
            break
          if (self.stop):
            #print "Stopped externally"
            break
        #print "Finished recording"
      else:
        # Flush record buffer
        self.frames = []

      # Post completion event
      self.event.set()

  def StartRecord(self, maxSeconds=60):

    # Clean up if already running
    self.StopRecord()

    # Flush buffer
    self.__Flush()

    # Start background thread
    self.recordThread = \
      self.__BackgroundRecordThread__(self.recordEvent, self.stream,
                                      self.frames,
                                      self.rate, self.chunk, maxSeconds)
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
    if (sz > 0):
      power = CalcRmsPower(self.frames[-2:])
    else:
      power = 0
    return (sz, power)

  def __Flush(self):
    self.frames = []

  def WriteFileAndClose(self, outputFileName='output.wav'):
    """Write everything recorded out to a wave file"""
    wf = wave.open(outputFileName, 'wb')
    wf.setnchannels(self.channels)
    wf.setsampwidth(self.p.get_sample_size(self.format))
    wf.setframerate(self.rate)
    wf.writeframes(b''.join(self.frames))
    wf.close()

  def Exit(self):
    self.StopRecord()
    self.stream.stop_stream()
    self.stream.close()
    self.p.terminate()

