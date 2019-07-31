# -*- coding: utf-8 -*-
# visualization of scene understandings for VTT project
# authored by haeyong kang
# 2019/07/30

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

import json
import collections
import sys
import logging
import math
import jsonlines
import os

MERGE_TIME_WINDOW = 1.0
MERGE_OVERLAP_THRESHOLD = 0.5

logger = None

video_file = './../video/1x01.mkv'

class Labels:
    def __init__(self, merge_time_window=MERGE_TIME_WINDOW, merge_overlap_threshold=MERGE_OVERLAP_THRESHOLD):
        self.entities = {}
        self.abstract_object_ids = collections.defaultdict(dict)
        self.coordinate_object_ids = collections.defaultdict(dict)
        self.located_at_property_ids = collections.defaultdict(list)
        self.video_entity_id = None
        self.ids = {}
        self.property_id = 0
        self.object_id = 0
        self.merge_time_window = merge_time_window
        self.merge_overlap_threshold = merge_overlap_threshold

    def get_property_id(self):
        self.property_id += 1
        return 'P%d' % self.property_id

    def get_object_id(self):
        self.object_id += 1
        return 'O%d' % self.object_id

    def get_entities_iter(self):
        for entity_id, entity in self.entities.items():
            yield entity

    def is_coordinates_mergeable(self, coord_a, coord_b):
        # [x, y, width, height]
        a_x, a_y, a_width, a_height = coord_a
        a_x2 = a_x + a_width
        a_y2 = a_y + a_height
        b_x, b_y, b_width, b_height = coord_b
        b_x2 = b_x + b_width
        b_y2 = b_y + b_height
        overlap_width = max(0, min(a_x2, b_x2) - max(a_x, b_x))
        overlap_height = max(0, min(a_y2, b_y2) - max(a_y, b_y))
        a_area = a_width * a_height
        b_area = b_width * b_height
        overlap_area = overlap_width * overlap_height
        return (overlap_area > a_area * self.merge_overlap_threshold) and (overlap_area > b_area * self.merge_overlap_threshold)

    def add_entity(self, entity):
        self.entities[entity['id']] = entity
        if entity['entity_type'] == 'property' and entity['class'] == 'located_at':
            seconds = entity['value']['seconds']
            self.located_at_property_ids[math.floor(seconds)].append(entity['id'])

    def get_video_object(self):
        if self.video_entity_id is None:
            entity = {
                'entity_type': 'object',
                'id': self.get_object_id(),
                'class': 'video'
            }
            self.video_entity_id = entity['id']
            self.add_entity(entity)
            return entity
        else:
            return self.entities[self.video_entity_id]

    def get_entity_id_by_coord(self, seconds, coordinates):
        range_start = max(math.floor(seconds) - math.ceil(self.merge_time_window), 0)
        range_end = math.ceil(seconds) + math.ceil(self.merge_time_window) + 1
        for i in range(range_start, range_end):
            for prop_id in self.located_at_property_ids[i]:
                prop = self.entities[prop_id]
                time_mergeable = abs(prop['value']['seconds'] - seconds) <= self.merge_time_window
                prop_coord = self.entities[prop['target']]
                coord_mergeable = self.is_coordinates_mergeable(coordinates, prop_coord['value']['coordinates'])
                if time_mergeable and coord_mergeable:
                    return prop['source']
        return None

    def get_object_by_coord(self, seconds, coordinates):
        entity_id = self.get_entity_id_by_coord(seconds, coordinates)
        if entity_id is not None:
            return self.entities[entity_id]
        else:
            entity = {
                'entity_type': 'object',
                'id': self.get_object_id(),
                'class': 'unknown'
            }
            self.add_entity(entity)
            return entity

    def get_object(self, seconds, obj):
        if 'id' in obj:
            #obj_id = self.ids[obj['id']]

            # refine_obj = obj['id'].split('_')[1]
            if obj['id'] in self.ids :
                obj_id = self.ids[obj['id']]
            else:
                print('error: get_object.')
                #for key, value in self.entities.items():
                #    print(key, value)
                #    obj_id = key
                #    break
            return self.entities[obj_id]

        elif 'coordinates' in obj:
            return self.get_object_by_coord(seconds, obj['coordinates'])
        else:
            logger.error('Unknown type of object found in %s' % obj)
            return None

    def get_coordinate_object(self, seconds, coordinates):
        coordinates_key = ','.join([str(i) for i in coordinates])
        if coordinates_key in self.coordinate_object_ids[seconds]:
            return self.coordinate_object_ids[seconds][coordinates_key]
        else:
            obj = {
                'entity_type': 'object',
                'id': self.get_object_id(),
                'class': 'video_box',
                'value': {
                    'coordinates': coordinates,
                    'seconds': seconds
                }
            }
            self.coordinate_object_ids[seconds][coordinates_key] = obj
            self.add_entity(obj)
            return obj

    def get_abstract_object(self, object_class, label):
        if label in self.abstract_object_ids[object_class]:
            return self.abstract_object_ids[object_class][label]
        else:
            obj = {
                'entity_type': 'object',
                'id': self.get_object_id(),
                'class': object_class,
                'value': {
                    'label': label
                }
            }
            self.add_entity(obj)
            self.abstract_object_ids[object_class][label] = obj
            return obj

    def get_label_property(self, seconds, object_class, source, target):
        prop_entity = {
            'entity_type': 'property',
            'id': self.get_property_id(),
            'class': object_class,
            'source': source['id'],
            'target': target['id'],
            'value': {
                'seconds': seconds,
                'label': source['value']['label'] # added by haeyong.k
            }
        }
        self.add_entity(prop_entity)
        return prop_entity

    def get_subtitle_property(self, seconds, object_class, source, target):
        prop_entity = {
            'entity_type': 'property',
            'id': self.get_property_id(),
            'class': object_class,
            'source': source['id'],
            'target': target['id'],
            'value': {
                'seconds': seconds,
                'label': source['value']['label'],# added by haeyong.k
                'id': source['value']['id']
            }
        }
        self.add_entity(prop_entity)
        return prop_entity

    def get_behavior_property(self, seconds, object_class, source, target):
        prop_entity = {
            'entity_type': 'property',
            'id': self.get_property_id(),
            'class': object_class,
            'source': source['id'],
            'target': target['id'],
            'value': {
                'seconds': seconds,
                'label': target['value']['label']  # added by haeyong.k
            }
        }
        self.add_entity(prop_entity)
        return prop_entity

    def get_emotion_property(self, seconds, object_class, source, target):
        prop_entity = {
            'entity_type': 'property',
            'id': self.get_property_id(),
            'class': object_class,
            'source': source['id'],
            'target': target['id'],
            'value': {
                'seconds': seconds,
                'label': target['value']['label'],  # added by haeyong.k
                'person': source['input_ids'][0]
            }
        }
        print(source['input_ids'][0])
        self.add_entity(prop_entity)
        return prop_entity


    def get_relation_property(self, seconds, object_class, source, target):
        prop_entity = {
            'entity_type': 'property',
            'id': self.get_property_id(),
            'class': object_class,
            'source': source['id'],
            'target': target['id'],
            'value': {
                'seconds': seconds['seconds'],
                'source': source['input_ids'], # added by haeyong.k
                'target': target['input_ids'], # added by haeyong.k
                'relation_kb': seconds['subclass']  # added by haeyong.k
            }
        }
        self.add_entity(prop_entity)
        return prop_entity

    def get_relation_object_property(self, seconds, object_class, source, target):
        prop_entity = {
            'entity_type': 'property',
            'id': self.get_property_id(),
            'class': object_class,
            'source': source['id'],
            'target': target['id'],
            'value': {
                'seconds': seconds['seconds'],
                'source': source['input_ids'], # added by haeyong.k
                'source_coordinates' : source['value']['coordinates'], # added by haeyong.k
                'target': target['input_ids'], # added by haeyong.k
                'target_coordinates': target['value']['coordinates'], # added by haeyong.k
                'relation_obj': seconds['subclass'] # added by haeyong.k
            }
        }
        print(prop_entity)
        self.add_entity(prop_entity)
        return prop_entity

    def get_property(self, seconds, object_class, source, target):
        prop_entity = {
            'entity_type': 'property',
            'id': self.get_property_id(),
            'class': object_class,
            'source': source['id'],
            'target': target['id'],
            'value': {
                'seconds': seconds,
            }
        }
        self.add_entity(prop_entity)
        return prop_entity

    def add_label(self, label):
        new_entities = []
        if label['type'] == 'object' :
            # Overwrite the entity
            entity = self.get_object_by_coord(label['seconds'], label['coordinates'])
            entity['entity_type'] = 'object'
            entity['class'] = label['class']
            entity['value'] = {'label': label['label']}

            if 'id' in label and label['id'] is not None:
                if 'input_ids' not in entity:
                    entity['input_ids'] = []
                #entity['input_ids'].append(label['id'].split(' ')[0])
                #self.ids[label['id'].split(' ')[0]] = entity['id']
                entity['input_ids'].append(label['id'])
                self.ids[label['id']] = entity['id']

            coord_entity = self.get_coordinate_object(label['seconds'], label['coordinates'])
            prop_entity = self.get_property(label['seconds'], 'located_at', entity, coord_entity)

        elif label['type'] == 'behavior':
            entity = self.get_object(label['seconds'], label['object'])
            behavior_entity = self.get_abstract_object('behavior', label['class'])
            prop_entity = self.get_behavior_property(label['seconds'], 'do', entity, behavior_entity)

        elif label['type'] == 'emotion':

            # Overwrite the entity
            entity = self.get_object_by_coord(label['seconds'], [0,0,0,0])
            entity['entity_type'] = 'object'
            entity['class'] = label['class']
            entity['value'] = {'label': label['class']}

            if 'id' in label['object'] and label['object']['id'] is not None:
                if 'input_ids' not in entity:
                    entity['input_ids'] = []
                # entity['input_ids'].append(label['id'].split(' ')[0])
                # self.ids[label['id'].split(' ')[0]] = entity['id']
                entity['input_ids'].append(label['object']['id'])
                self.ids[label['object']['id']] = entity['id']

            entity = self.get_object(label['seconds'], label['object'])
            emotion_entity = self.get_abstract_object('emotion', label['class'])
            prop_entity = self.get_emotion_property(label['seconds'], 'feel', entity, emotion_entity)

        elif label['type'] == 'relation':
            relation_type_entity = self.get_abstract_object(label['class'], label['subclass'])
            # Overwrite the entity
            entity = self.get_object_by_coord(label['seconds'], [0,0,0,0])
            entity['entity_type'] = 'relation'
            entity['class'] = label['class']
            entity['value'] = {'label': label['class']}

            if 'id' in label['source'] and label['source']['id'] is not None:
                if 'input_ids' not in entity:
                    entity['input_ids'] = []
                entity['input_ids'].append(label['source']['id'])
                self.ids[label['source']['id']] = entity['id']

            # Overwrite the entity
            entity = self.get_object_by_coord(label['seconds'], [0,0,0,0])
            entity['entity_type'] = 'relation'
            entity['class'] = label['class']
            entity['value'] = {'label': label['class']}

            if 'id' in label['target'] and label['target']['id'] is not None:
                if 'input_ids' not in entity:
                    entity['input_ids'] = []
                entity['input_ids'].append(label['target']['id'])
                self.ids[label['target']['id']] = entity['id']

            source_entity = self.get_object(label['seconds'], label['source'])
            target_entity = self.get_object(label['seconds'], label['target'])
            #prop_entity = self.get_relation_kbb_property(label['seconds'], 'related_to', source_entity, target_entity)
            prop_entity = self.get_relation_property(label, 'related_to', source_entity, target_entity)
            prop_entity['value']['relation'] = relation_type_entity['id']

        elif label['type'] == 'relation_object':
            relation_type_entity = self.get_abstract_object(label['class'], label['subclass'])
            # Overwrite the entity
            entity = self.get_object_by_coord(label['seconds'], [0,0,0,0])
            entity['entity_type'] = 'relation_object'
            entity['class'] = label['class']
            entity['value'] = {'label': label['class']}

            if 'id' in label['source'] and label['source']['id'] is not None:
                if 'input_ids' not in entity:
                    entity['input_ids'] = []
                entity['input_ids'].append(label['source']['id'])
                self.ids[label['source']['id']] = entity['id']

            # Overwrite the entity
            entity = self.get_object_by_coord(label['seconds'], [0,0,0,0])
            entity['entity_type'] = 'relation_object'
            entity['class'] = label['class']
            entity['value'] = {'label': label['class']}

            if 'id' in label['target'] and label['target']['id'] is not None:
                if 'input_ids' not in entity:
                    entity['input_ids'] = []
                entity['input_ids'].append(label['target']['id'])
                self.ids[label['target']['id']] = entity['id']

            source_entity = self.get_object(label['seconds'], label['source'])
            source_entity['value']['coordinates'] = label['source']['coordinates']
            target_entity = self.get_object(label['seconds'], label['target'])
            target_entity['value']['coordinates'] = label['target']['coordinates']
            #prop_entity = self.get_relation_kbb_property(label['seconds'], 'related_to', source_entity, target_entity)
            prop_entity = self.get_relation_object_property(label, 'related_to_object', source_entity, target_entity)
            prop_entity['value']['relation'] = relation_type_entity['id']

        elif label['type'] == 'location':
            entity = self.get_abstract_object('location', label['class'])
            video_entity = self.get_video_object()
            prop_entity = self.get_label_property(label['seconds'], 'location_of', entity, video_entity)

        elif label['type'] == 'sound':
            entity = self.get_abstract_object('sound', label['class'])
            video_entity = self.get_video_object()
            prop_entity = self.get_label_property(label['seconds'], 'sound_of', entity, video_entity)

        elif label['type'] == 'subtitle':
            entity = self.get_abstract_object('subtitle', label['subtitle'])
            video_entity = self.get_video_object()
            entity['value']['id'] = label['id']
            prop_entity = self.get_subtitle_property(label['start_time'], 'subtitle_of', entity, video_entity)

class Friends(App, Labels):

    def __init__(self, **kwargs):
        super(Friends, self).__init__(**kwargs)
        # initialize parameters
        # friend season and episode settings
        self.season = 1
        self.episode = 1

        # initial seconds
        self.seconds = 1

        # update / clear rates
        self.frame_rate = 5 # 1.0 / self.frame_rate
        self.clear_rate = 3 # [sec]

        # prediction star flag
        self.flag = False
        self.object_relation_flag = False

        #dir = "./../tracking/person/S{:02d}_EP{:02d}".format(self.season, self.episode)
        dir = "./json/tracking/person/S{:02d}_EP{:02d}".format(self.season, self.episode)
        frame_list = os.listdir(dir)  # dir is your directory path
        self.num_frames = len(frame_list)

        self.labels = Labels()
        # tracking data
        episode = '01'
        file = 'friends_s{:02d}_e{:02d}.jsonl'.format(self.season,self.episode)

        #tracking = './../VTT_TRACKING_DATA/data/friends/' + file
        sound = './json/sound_event/data/friends/' + file
        place = './json/place/data/friends/' + file
        behavior = './json/action/data/friends/' + file
        emotion = './json/emotion/data/friends/' + file
        relation_kbb = './json/triple/data/friends/' + file
        relation_kbh = './json/swrc/data/friends/' + file
        relation_object = './json/object/data/friends/' + file

        # subtitle
        subtitle_file = 's{:02d}_e{:02d}.jsonl'.format(self.season, self.episode)
        subtitle = './subtitle/' + subtitle_file

        # add places
        with jsonlines.open(place) as reader:
            for obj in reader:
                self.labels.add_label(obj)
        print('places added successfully.')

        # add sound
        with jsonlines.open(sound) as reader:
            for obj in reader:
                self.labels.add_label(obj)
        print('sound event detection added successfully.')

        # add tracking
        #with jsonlines.open(tracking) as reader:
        #    for obj in reader:
        #        self.labels.add_label(obj)
        #print('human tracking added successfully.')

        # add behavior
        with jsonlines.open(behavior) as reader:
            for obj in reader:
                self.labels.add_label(obj)
        print('behavior added successfully.')

        # add emotion
        with jsonlines.open(emotion) as reader:
            for obj in reader:
                self.labels.add_label(obj)
        print('emotion added successfully.')

        # add knowlege background
        with jsonlines.open(relation_kbb) as reader:
            for obj in reader:
                self.labels.add_label(obj)
        print('knowlege added successfully.')

        # add knowlege background
        with jsonlines.open(relation_kbh) as reader:
            for obj in reader:
                self.labels.add_label(obj)
        print('knowlege added successfully.')


        # add relation
        with jsonlines.open(relation_object) as reader:
            for obj in reader:
                obj['type'] = 'relation_object'
                obj['source']['id'] = obj['caption'].split(' ')[0] + '_' + obj['caption'].split(' ')[1]
                target = ''
                for word in obj['caption'].split(' ')[3:]:
                    if '_' in target:
                        target = target + '_' + word
                    else:
                        target = word
                obj['target']['id'] = target
                obj['class'] = 'related_to_object'
                obj['subclass'] = obj['caption'].split(' ')[2]
                self.labels.add_label(obj)
        print('relation added successfully.')

        with jsonlines.open(subtitle) as reader:
            for obj in reader:
                if 'type' not in obj:
                    obj['type'] = 'subtitle'
                self.labels.add_label(obj)

        self.avail_entity = []
        for entity in self.labels.get_entities_iter():
            if 'value' in entity:
                if 'seconds' in entity['value']:
                    self.avail_entity.append(entity)
                else:
                    pass
            else:
                pass

        # find the dictionary by time, test the annotations
        results = list(filter(lambda x: x['value']['seconds'] > 200.0 and x['value']['seconds'] < 250.0, self.avail_entity))
        for d in results:
            print(d)
        print('done.')

    # build
    def build(self):
        #self._cap = cv2.VideoCapture(video_file)
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
        #scrollLayout = BoxLayout(orientation='vertical', size_hint=(1.0, 0.2))
        self.SliderLabel = Label(text='...', size_hint=(1.0, 0.1), halign='center')
        SliderBar = Slider(min=1, max= self.num_frames, size_hint=(1.0, 0.1))
        SliderBar.bind(value=self.slideCallback)
        #kvLayout1.add_widget(kvLayout2)
        #kvLayout2.add_widget(kvSlider1)

        # add buttons to layout
        self.subtitle = Label(text='subtitle: ' + '...', halign='left', color=(1, 1, 1, 1), size_hint=(1.0, 0.4))
        self.relation_obj = Label(text='relation_obj: ' + '...', halign='left', color=(1, 1, 1, 1))
        ButtonLayout = BoxLayout(orientation='vertical', size_hint=(1.0, 1.0))
        VideoLayout.add_widget(ButtonLayout)
        ButtonLayout.add_widget(self.subtitle)
        #ButtonLayout.add_widget(self.relation_obj)
        ButtonLayout.add_widget(self.SliderLabel)
        ButtonLayout.add_widget(SliderBar)
        ButtonLayout.add_widget(kvButtonPlay)
        ButtonLayout.add_widget(kvButtonStop)

        # add text
        self.second_label = Label(text='second: ' + str(self.seconds), halign='left', color=(1, 1, 1, 1))
        self.sound_label = Label(text='sound: ' + '...', halign='left', color=(1, 1, 1, 1))
        self.place_label = Label(text='place: ' + '...', halign='left', color=(1, 1, 1, 1))
        self.behavior_label = Label(text='behavior: ' + '...', halign='left', color=(1, 1, 1, 1))
        self.emotion_label = Label(text='emotion: ' + '...', halign='left', color=(1, 1, 1, 1))
        self.relation_kbb = Label(text='knowlege_base: ' + '...', halign='left', color=(1, 1, 1, 1))


        # add information in Label layout
        LabelLayout = BoxLayout(orientation='vertical', size_hint=(1.0, 1.0))
        VideoLayout.add_widget(LabelLayout)
        LabelLayout.add_widget(self.second_label)
        LabelLayout.add_widget(self.sound_label)
        LabelLayout.add_widget(self.place_label)
        LabelLayout.add_widget(self.behavior_label)
        LabelLayout.add_widget(self.emotion_label)
        LabelLayout.add_widget(self.relation_kbb)
        LabelLayout.add_widget(self.relation_obj)

        # wait for opencv video capture
        #while not self._cap.isOpened():
        #    pass
        #self._cap.set(cv2.CAP_PROP_FPS, 5)
        # update/clear schedules
        Clock.schedule_interval(self.update, 1.0/ self.frame_rate)
        Clock.schedule_interval(self.clear, self.clear_rate)
        Clock.schedule_interval(self.clear_kb, self.clear_rate * 5)

        return VideoLayout

    # callback functions
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
        self.seconds = value
        self.SliderLabel.text = 'predictions from %s seconds,  %s frames' % (int(self.seconds / self.frame_rate), int(value))
        print('Slider <%s> is pressed.' % (instance))

    # clear function
    def clear(self, dt):
        self.place_label.text = 'place: ' + '...'
        self.place_label.color = (1, 1, 1, 1)

        self.sound_label.text = 'sound: ' + '...'
        self.sound_label.color = (1, 1, 1, 1)

        self.behavior_label.text = 'behavior: ' + '...'
        self.behavior_label.color = (1, 1, 1, 1)

        self.emotion_label.text = 'emotion: ' + '...'
        self.emotion_label.color = (1, 1, 1, 1)

        self.relation_obj.text = 'relation_obj: ' + '...'
        self.relation_obj.color = (1, 1, 1, 1)

    def clear_kb(self, dt):

        #self.relation_kbb.text = 'knowlege_base: ' + '...'
        #self.relation_kbb.color = (1, 1, 1, 1)

        self.subtitle.text = 'subtitle: ' + '...'
        self.subtitle.color = (1, 1, 1, 1)

    def mkdirs(self, path):
        if os.path.exists(path):
            return
        os.makedirs(path)


    def update(self, dt):
        # OpenCV processing

        if self.flag == True:
            #ret, frame = self._cap.read()
            #frame = cv2.flip(frame, 0)
            #kvTexture1 = Texture.create(size=(frame.shape[1], frame.shape[0]), colorfmt='bgr')
            #kvTexture1.blit_buffer(frame.tostring(), colorfmt='bgr', bufferfmt='ubyte')

            # save detection results
            #save_path = './../tracking/det/S{:02d}_EP{:02d}'.format(self.season, self.episode)
            save_path = './json/tracking/det/S{:02d}_EP{:02d}'.format(self.season, self.episode)
            save_file = save_path + '/det.txt'.format(self.season, self.episode)
            self.mkdirs(save_path)

            # processing
            self.seconds += 1

            with open(save_file, 'a') as f:

                #frame_number = int(self.seconds / 6.0) + 5
                frame_number = int(self.seconds)
                if self.seconds > 1:
                    #bbox_fpath = "./../tracking/person/S{:02d}_EP{:02d}/{:05d}.json".format(self.season, self.episode, frame_number)
                    #imgs_fpath = "./../tracking/frames/S{:02d}_EP{:02d}/{:05d}.jpg".format(self.season, self.episode, frame_number)
                    #relation_fpath = "./../tracking/relation_obj/S{:02d}_EP{:02d}_RE/{:05d}.json".format(self.season, self.episode, frame_number)

                    bbox_fpath = "./json/tracking/person/S{:02d}_EP{:02d}/{:05d}.json".format(self.season, self.episode, frame_number)
                    imgs_fpath = "./frames/S{:02d}_EP{:02d}/{:05d}.jpg".format(self.season, self.episode, frame_number)
                    relation_fpath = "./json/tracking/relation_obj/S{:02d}_EP{:02d}/{:05d}.json".format(self.season, self.episode, frame_number)

                    frame = cv2.imread(imgs_fpath)
                    frame_left = frame.copy()
                    #frame_left = cv2.flip(frame_left, 0)

                    print(bbox_fpath)
                    with open(bbox_fpath, 'r') as fin:
                        bboxes = json.load(fin)
                    bboxes_ = [bbox for bbox in bboxes if bbox['confidence'] > 0.5 and bbox['label'] == 'person']

                    for bbox in bboxes_:
                        x1, y1 = bbox['topleft']['x'], bbox['topleft']['y']
                        x2, y2 = bbox['bottomright']['x'], bbox['bottomright']['y']

                        #print('x1:', str(x1), 'y1:', str(y1), 'x2:', str(x2), 'y2:', str(y2))
                        cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 3)

                        # saving format
                        id = -1
                        w = x2-x1
                        h = y2-y1
                        conf = bbox['confidence'] - 0.5
                        #save_format = '{frame},{id},{x1},{y1},{w},{h},1,-1,-1,-1'
                        ped_info = '%d,%d,%f,%f,%f,%f,%f,%d,%d,%d \n' % (frame_number, id, x1,y1,w,h,conf,-1,-1,-1)
                        f.write(ped_info)

                    with open(relation_fpath, 'r') as fin:
                        bboxes = json.load(fin)

                    # relation_object
                    bboxes_obj_cap = []
                    bboxes_obj = []
                    man_cnt = 0
                    woman_cnt = 0
                    for boxes in bboxes:
                        if man_cnt >= 3:
                            break
                        if woman_cnt >= 3:
                            break

                        boxes['type'] = 'relation_object'
                        boxes['source']['id'] = boxes['caption'].split(' ')[0] + '_' + boxes['caption'].split(' ')[1]
                        target = ''
                        for word in boxes['caption'].split(' ')[3:]:
                            if '_' in target:
                                target = target + '_' + word
                            else:
                                target = word
                        boxes['target']['id'] = target
                        boxes['class'] = 'related_to_object'
                        if 'subclass' not in boxes:
                            boxes['subclass'] = boxes['caption'].split(' ')[2]

                        bboxes_obj.append(boxes)

                        if boxes['caption'].find("man") >= 1 or boxes['caption'].find("woman") >= 1 :
                            # source object bounding box
                            x = int(boxes['source']['coordinates'][0] * (1280/720))
                            y = int(boxes['source']['coordinates'][1] * (720/402))
                            w = int(boxes['source']['coordinates'][2] * (1280/720))
                            h = int(boxes['source']['coordinates'][3] * (720/402))
                            cv2.rectangle(frame_left, (x, y), (x+w, y+h), (255, 0, 0), 2)
                            cv2.putText(frame_left, boxes['subject'], (x, y), cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 0, 0), 1, cv2.LINE_AA)

                            # target object bounding box
                            x = int(boxes['target']['coordinates'][0] * (1280/720))
                            y = int(boxes['target']['coordinates'][1] * (720/402))
                            w = int(boxes['target']['coordinates'][2] * (1280/720))
                            h = int(boxes['target']['coordinates'][3] * (720/402))
                            cv2.rectangle(frame_left, (x, y), (x+w, y+h), (0, 0, 255), 2)
                            cv2.putText(frame_left, boxes['object'], (x, y), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255),1, cv2.LINE_AA)
                            bboxes_obj_cap.append(boxes['caption'])

                            if boxes['caption'].find("man") >= 1:
                                man_cnt += 1
                            if boxes['caption'].find("woman") >= 1:
                                woman_cnt += 1

                    captions = ''
                    for cap in bboxes_obj_cap:
                        if '\n' in captions:
                            captions = captions + cap + '\n'
                        else:
                            captions = cap + '\n'

                    self.relation_obj.text = captions
                    self.relation_obj.color = (1, 0, 0, 1)


            f.close()


            #self.text = 'hello'
            #self.label = Label(text='Hello', color=(1,0,1,1))
            self.second_label.text = 'second: ' + str(int(self.seconds / self.frame_rate)) + ', frame: ' + str(frame_number)
            self.second_label.color = (1,1,1,1)

            results = list(filter(lambda x: x['value']['seconds'] >= int(self.seconds / self.frame_rate) and x['value']['seconds'] < int(self.seconds / self.frame_rate)+1.0, self.avail_entity))

            # subtitle
            for i in range(len(results)):
                if results[i]['class'] == 'location_of':
                    self.place_label.text = 'place: ' + results[i]['value']['label']
                    self.place_label.color = (1,0,1,1)
                elif results[i]['class'] == 'sound_of':
                    self.sound_label.text = 'sound: ' + results[i]['value']['label']
                    self.sound_label.color = (1,0.5,0.5,1)
                elif results[i]['class'] == 'subtitle_of':
                    self.subtitle.text = results[i]['value']['id']+ ': '+results[i]['value']['label']
                    self.subtitle.color = (1,0.5,0.5,1)
                elif results[i]['class'] == 'video_box':
                    # [255, 305, 351, 523]
                    # draw a green rectangle to visualize the bounding rect
                    #x = results[i]['value']['coordinates'][0]
                    #y = results[i]['value']['coordinates'][1]
                    #w = results[i]['value']['coordinates'][2]
                    #h = results[i]['value']['coordinates'][3]
                    #frame = cv2.rectangle(frame, (x, y), (x+w, y+h), (0, 255, 0), 2)
                    pass

                elif results[i]['class'] == 'do':
                    self.behavior_label.text = 'behavior: ' + results[i]['value']['label']
                    self.behavior_label.color = (1, 0, 1, 1)

                elif results[i]['class'] == 'feel':
                    self.emotion_label.text = 'emotion: ' + results[i]['value']['person'] + '_' + results[i]['value']['label']
                    self.emotion_label.color = (1, 0, 1, 1)

                # relations
                elif results[i]['class'] == 'related_to':
                    self.relation_kbb.text = 'knowlege_base: ' + results[i]['value']['source'][0]+' <--> '+ \
                                                    results[i]['value']['relation_kb'] + ' <--> ' + results[i]['value']['target'][0]
                    self.relation_kbb.color = (1, 0, 0, 1)

                elif results[i]['class'] == 'related_to_object':
                    #self.relation_obj.text = 'relation_obj: ' + results[i]['value']['source'][0]+' <--> '+ \
                    #                                results[i]['value']['relation_obj'] + ' <--> ' + results[i]['value']['target'][0]
                    self.relation_obj.text = captions
                    self.relation_obj.color = (1, 0, 0, 1)

                    if self.object_relation_flag:
                        # source object bbox
                        x = int(results[i]['value']['source_coordinates'][0])
                        y = int(results[i]['value']['source_coordinates'][1])
                        w = int(results[i]['value']['source_coordinates'][2])
                        h = int(results[i]['value']['source_coordinates'][3])
                        cv2.rectangle(frame_left, (x, y), (w, h), (255, 0, 0), 2)

                        # target object bbox
                        x = int(results[i]['value']['target_coordinates'][0])
                        y = int(results[i]['value']['target_coordinates'][1])
                        w = int(results[i]['value']['target_coordinates'][2])
                        h = int(results[i]['value']['target_coordinates'][3])
                        cv2.rectangle(frame_left, (x, y), (w, h), (0, 0, 255), 2)

            # frame updated
            frame = cv2.flip(frame, 0)
            frame_left = cv2.flip(frame_left, 0)

            kvTexture1 = Texture.create(size=(frame_left.shape[1], frame_left.shape[0]), colorfmt='bgr')
            kvTexture1.blit_buffer(frame_left.tostring(), colorfmt='bgr', bufferfmt='ubyte')

            kvTexture2 = Texture.create(size=(frame.shape[1], frame.shape[0]), colorfmt='bgr')
            kvTexture2.blit_buffer(frame.tostring(), colorfmt='bgr', bufferfmt='ubyte')

            self.kvImage_raw.texture = kvTexture1
            self.kvImage_pros.texture = kvTexture2

if __name__ == '__main__':
    Friends().run()