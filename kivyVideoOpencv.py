# -*- coding: utf-8 -*-
from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.button import Button
from kivy.uix.slider import Slider
from kivy.uix.image import Image
from kivy.uix.label import Label
from kivy.graphics.texture import Texture
from kivy.clock import Clock
from kivy.core.audio import SoundLoader
from kivy.uix.videoplayer import VideoPlayer
import cv2
from kivy.properties import StringProperty
from kivy.core.text.text_layout import layout_text


video_file = './../video/1x01.mkv'

class Friends(App):

    def __init__(self, **kwargs):
        super(Friends, self).__init__(**kwargs)
        #self.text = ''
        self.seconds = 0

    # build
    def build(self):
        self._cap = cv2.VideoCapture(video_file)

        # define botton
        kvButtonPlay = Button(text="play", size_hint=(1.0, 0.1))
        kvButtonPlay.bind(on_press = self.buttonCallbackPlay)

        kvButtonStop = Button(text="stop", size_hint=(1.0, 0.1))
        kvButtonStop.bind(on_press=self.buttonCallbackStop)

        # define image
        self.kvImage_raw = Image()
        self.kvImage_pros = Image()

        # define video layout and add image
        #VideoLayout = BoxLayout(orientation='vertical')
        VideoLayout = GridLayout(cols=2)
        VideoLayout.add_widget(self.kvImage_raw)
        VideoLayout.add_widget(self.kvImage_pros)

        # BoxLayout
        #kvLayout2 = BoxLayout(orientation='horizontal', size_hint=(1.0, 0.2))
        #self.kvSlider1Label = Label(text = 'Slider', size_hint=(0.2, 1.0), halign='center')
        #kvSlider1 = Slider(size_hint=(0.7, 1.0))
        #kvSlider1.bind(value=self.slideCallback)
        #kvLayout1.add_widget(kvLayout2)
        #kvLayout2.add_widget(self.kvSlider1Label)
        #kvLayout2.add_widget(kvSlider1)

        # add buttons to layout
        ButtonLayout = BoxLayout(orientation='vertical', size_hint=(1.0, 0.2))
        #ButtonLayoutStop = BoxLayout(orientation='vertical', size_hint=(1.0, 0.1))
        VideoLayout.add_widget(ButtonLayout)
        ButtonLayout.add_widget(kvButtonPlay)
        ButtonLayout.add_widget(kvButtonStop)

        # add text
        self.second_label = Label(text='second: ' + str(self.seconds), halign='left', color=(1,0,1,1))
        self.sound_label = Label(text='sound: ' + 'background music', halign='left', color=(1,1,1,1))
        self.place_label = Label(text='place: ' + 'caffe', halign='left', color=(1,1,1,1))
        #self.text = StringProperty(text='hello')
        LabelLayout = BoxLayout(orientation='vertical', size_hint=(1.0,1.0))
        VideoLayout.add_widget(LabelLayout)
        LabelLayout.add_widget(self.second_label)
        LabelLayout.add_widget(self.sound_label)
        LabelLayout.add_widget(self.place_label)
        #LabelLayout.add_widget(self.text)

        # wait for opencv video capture
        while not self._cap.isOpened():
            pass
        Clock.schedule_interval(self.update, 1.0/30.0)

        self.flag = False

        return VideoLayout

    def buttonCallbackPlay(self, instance):
        # the buttonCallback is used as a flag
        self.flag = True
        print('Play <%s> is pressed.' % (instance))

    def buttonCallbackStop(self, instance):
        # the buttonCallback is used as a flag
        self.flag = False
        self.text = 'Stop <%s> is pressed.' % (instance)
        print('Stop <%s> is pressed.' % (instance))

    def slideCallback(self, instance, value):
        # the range is  from 0 to 100
        self.kvSlider1Label.text = 'Slider %s' % int(value)
        print('Slider <%s> is pressed.' % (instance))

    def update(self, dt):
        # OpenCV processing

        if self.flag == True:
            ret, frame = self._cap.read()
            frame = cv2.flip(frame, 0)
            kvTexture1 = Texture.create(size=(frame.shape[1], frame.shape[0]), colorfmt='bgr')
            kvTexture1.blit_buffer(frame.tostring(), colorfmt='bgr', bufferfmt='ubyte')

            # processing
            self.seconds += 1
            kvTexture2 = Texture.create(size=(frame.shape[1], frame.shape[0]), colorfmt='bgr')
            kvTexture2.blit_buffer(frame.tostring(), colorfmt='bgr', bufferfmt='ubyte')

            self.kvImage_raw.texture = kvTexture1
            self.kvImage_pros.texture = kvTexture1

            #self.text = 'hello'
            #self.label = Label(text='Hello', color=(1,0,1,1))
            self.second_label.text = 'second: ' + str(int(self.seconds/30.0))
            self.sound_label.text = 'sound: ' + 'music...'
            self.place_label.text = 'place: ' + 'caffe...'

if __name__ == '__main__':
    Friends().run()