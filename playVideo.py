from ffpyplayer.player import MediaPlayer
from ffpyplayer.pic import Image, SWScale
from ffpyplayer.tools import get_supported_pixfmts
from ffpyplayer.writer import MediaWriter
import time


video = './../video/1x01.mkv'
save_dir = './../frame/1x01/'

# create image
w, h = 1280, 720
fmt = 'rgb24'
codec = 'png'  # we'll encode it using the tiff codec
out_opts = {'pix_fmt_in': fmt, 'width_in': w, 'height_in': h,
            'frame_rate': (30, 1), 'codec': codec}


player = MediaPlayer(video)
val = ''
while val != 'eof':
    frame, val = player.get_frame()
    if val != 'eof' and frame is not None:
        img, t = frame
        frame_file = 'frame' + str(int(t)) + '.png'
        file = save_dir + frame_file
        print(str(t))
        buf = img.to_bytearray()
        img = Image(plane_buffers=[buf[0]], pix_fmt=fmt, size=(w, h))
        writer = MediaWriter(file, [out_opts])
        writer.write_frame(img=img, pts=0, stream=0)
        writer.close()

