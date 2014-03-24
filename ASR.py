"""
ASR

An ASR instance using pocketsphinx.

Dependencies: pocketsphinx, gstreamer

Copyright (c) 2014 All Right Reserved, Liam Wickins

Please see the LICENSE file for more information.

THIS CODE AND INFORMATION ARE PROVIDED "AS IS" WITHOUT WARRANTY OF ANY 
KIND, EITHER EXPRESSED OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE
IMPLIED WARRANTIES OF MERCHANTABILITY AND/OR FITNESS FOR A
PARTICULAR PURPOSE.
"""

import gobject
import pygst
pygst.require('0.10')
gobject.threads_init()
import gst
import time
import os

class ASR():

    BASE = '/home/liamw/Python/audio/MusicDB/model/88a693a77bb44a1ca402fa61b4bc6dbf/'
    NAME = 'MusicDB'

    def __init__(self, callback, hmm=None, lm=None, dic=None, nBestSize=0,
                 latdir=None, fsg=None, tag='cmu', wordLimit=2):
        self.__InitGsr(hmm, lm, dic, nBestSize, latdir, fsg)
        self.Pause()
        self.callback = callback
        self.tag = tag
        self.wordLimit = wordLimit

    def IsPlaying(self):
      return self.isPlaying

    def Play(self):
      self.pipeline.set_state(gst.STATE_PLAYING)
      self.isPlaying = True

    def Pause(self):
      self.pipeline.set_state(gst.STATE_PAUSED)
      self.isPlaying = False

    def Flush(self):
      pass

    def Exit(self):
      self.Pause()

    def __InitGsr(self, hmm, lm, dic, nBestSize, latdir, fsg):
        if (hmm is None):
          hmm = self.BASE
        if (lm is None):
          lm = self.BASE + self.NAME + '.lm'
        if (dic is None):
          dic = self.BASE + self.NAME + '.dic'
        pipeline =  " gconfaudiosrc ! audioconvert ! audioresample !"
        pipeline += " vader name=vad auto-threshold=true !"
        pipeline += " pocketsphinx"
        pipeline += " name=asr"
        pipeline += " ! fakesink"
        self.pipeline = gst.parse_launch(pipeline)
        asr = self.pipeline.get_by_name('asr')
        if (os.path.exists(hmm)):
          asr.set_property('hmm', hmm[:-1]) # FIXME: Remove trailing '/'
        if (not fsg and os.path.exists(lm)):
          asr.set_property('lm', lm)
        if (os.path.exists(dic)):
          asr.set_property('dict', dic)
        if (latdir and os.path.exists(latdir)):
          asr.set_property('latdir', latdir)
        if (fsg):
          asr.set_property('fsg', fsg)
        self.nBestSize = nBestSize
        if (nBestSize > 0):
          asr.set_property('nbest_size', nBestSize)
        asr.connect('partial_result', self.__AsrPartial)
        asr.connect('result', self.__AsrResult)
        asr.set_property('configured', True)

    def __AsrPartial(self, asr, text, uttid):
        items = [text]
        nbest = asr.get_property('nbest')
        if (self.nBestSize > 0): items += nbest
        self.callback('partial', self.tag, items)

    def __AsrResult(self, asr, text, uttid):
        items = [text]
        nbest = asr.get_property('nbest')
        if (self.nBestSize > 0): items += nbest
        if (len(text.split(' ')) <= self.wordLimit):
          self.callback('result', self.tag, items)
