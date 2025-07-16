#!/bin/bash

set -euo pipefail

# Accept input device from args or auto-detect Elgato
INPUT_DEVICE="${1:-}"

if [[ -z "$INPUT_DEVICE" ]]; then
  echo "🔍 Searching for Elgato Facecam..."
  INPUT_DEVICE=$(v4l2-ctl --list-devices 2>/dev/null | awk '/Elgato Facecam/{getline; print $1}' | head -n 1)

  if [[ -z "$INPUT_DEVICE" ]]; then
    echo "❌ Could not detect Elgato Facecam. Is it connected?"
    exit 1
  fi
fi

echo "🎥 Using Elgato Facecam at $INPUT_DEVICE"

# Load v4l2loopback module if needed
modprobe v4l2loopback video_nr=10 card_label="VirtualCam" exclusive_caps=1 || true

# Start FFmpeg pipeline
exec ffmpeg \
  -f v4l2 -input_format uyvy422 -video_size 1280x720 -i "$INPUT_DEVICE" \
  -f v4l2 -pix_fmt yuv420p /dev/video10
