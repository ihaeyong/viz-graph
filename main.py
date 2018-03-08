import json
import collections
import sys
import logging
import math

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
            obj_id = self.ids[obj['id']]
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

    def get_property(self, seconds, object_class, source, target):
        prop_entity = {
            'entity_type': 'property',
            'id': self.get_property_id(),
            'class': object_class,
            'source': source['id'],
            'target': target['id'],
            'value': {
                'seconds': seconds
            }
        }
        self.add_entity(prop_entity)
        return prop_entity

    def add_label(self, label):
        new_entities = []
        if label['type'] == 'object':
            # Overwrite the entity
            entity = self.get_object_by_coord(label['seconds'], label['coordinates'])
            entity['entity_type'] = 'object'
            entity['class'] = label['class']
            entity['value'] = {'label': label['label']}

            if 'id' in label and label['id'] is not None:
                if 'input_ids' not in entity:
                    entity['input_ids'] = []
                entity['input_ids'].append(label['id'])
                self.ids[label['id']] = entity['id']

            coord_entity = self.get_coordinate_object(label['seconds'], label['coordinates'])
            prop_entity = self.get_property(label['seconds'], 'located_at', entity, coord_entity)

        elif label['type'] == 'behavior':
            entity = self.get_object(label['seconds'], label['object'])
            behavior_entity = self.get_abstract_object('behavior', label['class'])
            prop_entity = self.get_property(label['seconds'], 'do', entity, behavior_entity)

        elif label['type'] == 'emotion':
            entity = self.get_object(label['seconds'], label['object'])
            emotion_entity = self.get_abstract_object('emotion', label['class'])
            prop_entity = self.get_property(label['seconds'], 'feel', entity, emotion_entity)

        elif label['type'] == 'relation':
            relation_type_entity = self.get_abstract_object(label['class'], label['subclass'])
            source_entity = self.get_object(label['seconds'], label['source'])
            target_entity = self.get_object(label['seconds'], label['target'])
            prop_entity = self.get_property(label['seconds'], 'related_to', source_entity, target_entity)
            prop_entity['value']['relation_type'] = relation_type_entity['id']

        elif label['type'] == 'location':
            entity = self.get_abstract_object('location', label['class'])
            video_entity = self.get_video_object()
            prop_entity = self.get_property(label['seconds'], 'location_of', entity, video_entity)

        elif label['type'] == 'sound':
            entity = self.get_abstract_object('sound', label['class'])
            video_entity = self.get_video_object()
            prop_entity = self.get_property(label['seconds'], 'sound_of', entity, video_entity)

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
    for line in sys.stdin:
        try:
            yield json.loads(line)
        except json.decoder.JSONDecodeError:
            logger.warn('Failed to decode JSON line: %s' % line.strip())

def main():
    init_logger()
    labels = Labels()

    for label in get_labels_iter():
        labels.add_label(label)

    for entity in labels.get_entities_iter():
        print(json.dumps(entity))

if __name__ == '__main__':
    main()
