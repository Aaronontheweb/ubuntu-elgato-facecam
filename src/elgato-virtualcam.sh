#!/bin/bash

# Load the loopback module (only if not already loaded)
modprobe v4l2loopback video_nr=10 card_label="VirtualCam" exclusive_caps=1

# Start transcoding from Elgato Facecam to virtual device
exec ffmpeg \
  -f v4l2 -input_format uyvy422 -video_size 1280x720 -i /dev/video0 \
  -f v4l2 -pix_fmt yuv420p /dev/video10
