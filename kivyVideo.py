#!/usr/bin/env kivy
import kivy

kivy.require('1.9.1')

from kivy.app import App

from kivy.uix.videoplayer import VideoPlayer

VIDEO_PATH = './../video/1x01.mkv'


class FriendApp(App):
    def build(self):
        playbin = VideoPlayer(source=VIDEO_PATH, state="play",
                              options={"allow_stretch": True})
        return playbin


FriendApp().run()