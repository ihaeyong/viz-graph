import json
import collections
import sys
import logging
import math
import jsonlines
import cv2

MERGE_TIME_WINDOW = 1.0
MERGE_OVERLAP_THRESHOLD = 0.5

logger = None

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

def init_logger():
    global logger
    logger = logging.getLogger('builder_main')
    logger.setLevel(logging.DEBUG)

    file_handler = logging.FileHandler('main.log')
    file_handler.setLevel(logging.DEBUG)

    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.DEBUG)

    formatter = logging.Formatter('[%(asctime)s - %(name)s - %(levelname)s] %(message)s')
    file_handler.setFormatter(formatter)
    console_handler.setFormatter(formatter)

    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

def get_labels_iter():
    #with open('./test_input.jsonlines') as f:
    #    df = json.load(f)
    with jsonlines.open('./test_input.jsonlines') as reader:
        for obj in reader:
            print(obj)

    for line in sys.stdin:
        try:
            yield json.loads(line)
        except json.decoder.JSONDecodeError:
            logger.warn('Failed to decode JSON line: %s' % line.strip())

def main():
    init_logger()
    labels = Labels()

    #line = 0
    #for label in get_labels_iter():
    #    labels.add_label(label)
    #    print('line:', line)
    #    line += 1

    # tracking data
    episode = '01'
    file = 'friends_s01_e' + episode + '.jsonl'

    tracking = './../VTT_TRACKING_DATA/data/friends/' + file
    sound = './../vtt-sound-event-data/data/friends/' + file
    place = './../2nd-year-data/data/friends/' + file
    action = './../vtt-action-recognition-data/data/friends/' + file
    emotion = './../VTT_vid_emotion_data/data/friends/' + file
    relation_kbb = './../vtt-triple-data-jsonl/data/friends/' + file
    relation_kbh = './../vtt-swrc-2018-data-result/data/friends/' + file
    relation_object = './../VTT_object_data/data/friends/' + file

    # subtitle
    subtitle_file = 's01_e' + episode + '.jsonl'
    subtitle = './../tracking/subtitle/' + subtitle_file

    with jsonlines.open(place) as reader:
        for obj in reader:
            labels.add_label(obj)

    with jsonlines.open(sound) as reader:
        for obj in reader:
            labels.add_label(obj)

    with jsonlines.open(tracking) as reader:
        for obj in reader:
            labels.add_label(obj)

    with jsonlines.open(action) as reader:
        for obj in reader:
            labels.add_label(obj)

    with jsonlines.open(emotion) as reader:
        for obj in reader:
            labels.add_label(obj)

    with jsonlines.open(relation_kbb) as reader:
        for obj in reader:
            labels.add_label(obj)

    with jsonlines.open(relation_kbh) as reader:
        for obj in reader:
            labels.add_label(obj)

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
            if 'subclass' not in obj:
                obj['subclass'] = obj['caption'].split(' ')[2]
                #print(obj['subclass'])
            labels.add_label(obj)

    with jsonlines.open(subtitle) as reader:
        for obj in reader:
            if 'type' not in obj:
                obj['type'] = 'subtitle'
            labels.add_label(obj)

    place = []
    for entity in labels.get_entities_iter():
        if 'value' in entity:
            if 'seconds' in entity['value']:
                #print(json.dumps(entity['value']['seconds']))
                place.append(entity)
            else:
                pass
        else:
            pass
            #print(json.dumps(entity['value']['seconds']))

    # find the dictionary by time
    results = list(filter(lambda  x : x['value']['seconds'] > 1.0 and x['value']['seconds'] < 50.0 , place))

    for d in results:
        print(d)
    print('done.')

    season = 1
    episode = 1
    frame_number = 100
    bbox_fpath = "./../tracking/person/S{:02d}_EP{:02d}/{:05d}.json".format(season, episode, frame_number)
    with open(bbox_fpath, 'r') as fin:
        bboxes = json.load(fin)
    bboxes = [bbox for bbox in bboxes if bbox['confidence'] > 0.5 and bbox['label'] == 'person']
    for bbox in bboxes:
        x1, y1 = bbox['topleft']['x'], bbox['topleft']['y']
        x2, y2 = bbox['bottomright']['x'], bbox['bottomright']['y']

        print('x1:', str(x1), 'y1:', str(y1), 'x2:', str(x2), 'y2:', str(y2))

if __name__ == '__main__':
    main()
