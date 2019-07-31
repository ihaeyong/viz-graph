## Video Knowledge Builder and Graph

This is an application that takes *JSONLines* formatted video label dataset as input and
builds context dependent knowledge base.

### requirements
kivy for visualization of frames and recognition results

Ensure you have the latest pip, wheel, and virtualenv:

`$python -m pip install --upgrade pip wheel setuptools virtualenv`

Optionally create a new virtual environment for your Kivy project. Highly recommended:

First create the environment named kivy_venv in your current directory:

`$python -m virtualenv kivy_venv`

Activate the virtual environment or on windows CMD do: 

`$kivy_venv\Scripts\activate`

Install the dependencies and kivy 

`$python -m pip install docutils pygments pypiwin32 kivy.deps.sdl2 kivy.deps.glew`


![visualization of video](https://user-images.githubusercontent.com/14289457/62134415-674b7c80-b31b-11e9-8312-cdc7a6d7c507.PNG)

### Input frames :
Given the following video frames at 3 [FPS]

* [E01_S01](https://www.dropbox.com/sh/sblafxoo7ktv16n/AAD5GRzwni4Xk3b27dkQl9Qna?dl=0)


### Input format

Input data must be JSONLines that contains multiple JSON objects in one of the
formats below.

**Object**

* `{"type": "object", "class": "person", "label": "Person A", "seconds": 15.0, "coordinates": [100, 200, 20, 30]}`
* `{"type": "object", "id": "person_ross_geller", "class": "person", "label": "Ross Geller", "seconds": 15.0, "coordinates": [100, 200, 20, 30]}`
* https://github.com/vtt-project/DRCaptioning

**Behavior**

* `{"type": "behavior", "class": "stand", "seconds": 15.0, "object": Object}`
* https://github.com/vtt-project/vtt-action-recognition

**Emotion**

* `{"type": "emotion", "class": "happy", "seconds": 15.0, "object": Object}`
* https://github.com/vtt-project/VTT_vid_emotion

**Relation**

* `{"type": "relation", "class": RelationalClass, "subclass": "wear", "seconds": 15.0, "source": Object, "target": Object}`
* https://github.com/vtt-project/vtt-char-identify

**Place**

* `{"type": "location", "class": "central_perk", "seconds": 15.0}`
* https://github.com/vtt-project/2nd-year

**Sound event**

* `{"type": "sound", "class": "glass_crashing", "seconds": 15.0}`
* https://github.com/vtt-project/vtt-sound-event-detection

**Person re-id**

* `{"id": "person_ross_geller"}` or
* `{"coordinates": [100, 200, 20, 30]}`
* https://github.com/vtt-project/VTT_TRACKING

**RelationalClass**

* `"behavior"` for subclass `"wear"`, `"hold"`, `"hug"`, …
* `"emotion"` for subclass `"love"`, `"like"`, …
* `"position"` for subclass `"above"`, `"below"`, `"next_to"`, …
* `"social"` for subclass `"son_of"`, `"father_of"`, `"lover_of"`, `"friend_of"`, …



### How to use
`kivyVideoOpencvLabel.py` takes input data from several modules and visualize the results on video frames.

```
$ python kivyVideoOpencvLabel.py
```

`main.py` takes input data as standard input, and prints result knowledge base as
standard output as a JSONLines formatted string. For example:

```
video-knowledge-builder $ python main.py < test_input.jsonlines > output.jsonlines
```

The shell command above will provide the contents of `test_input.jsonlines` as
input for the application and save the result in a file `output.jsonlines`.


#### Acknowledgements

This work was supported by Institute for Information & communications Technology Promotion(IITP) grant funded by the Korea government(MSIT) (2017-0-01780, The technology development for event recognition/relational reasoning and learning knowledge based system for video understanding)
