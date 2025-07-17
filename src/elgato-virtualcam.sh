#!/usr/bin/env bash

set -euo pipefail

# Accept input device or try to auto-detect Elgato Facecam
INPUT_DEVICE="${1:-}"

if [[ -z "$INPUT_DEVICE" ]]; then
  echo "🔍 Auto-detecting Elgato Facecam..."
  INPUT_DEVICE=$(v4l2-ctl --list-devices 2>/dev/null | awk '/Elgato Facecam/{getline; print $1}' | head -n 1)

  if [[ -z "$INPUT_DEVICE" ]]; then
    echo "❌ Elgato Facecam not detected. Exiting."
    exit 1
  fi
fi

# Ensure no other ffmpeg process is already using the virtual cam
if pgrep -f "ffmpeg.*video10" > /dev/null; then
  echo "❌ FFmpeg is already using /dev/video10. Is the service already running?"
  exit 1
fi

# Ensure v4l2loopback is loaded
if ! lsmod | grep -q v4l2loopback; then
  echo "📦 Loading v4l2loopback module..."
  sudo modprobe v4l2loopback video_nr=10 card_label="VirtualCam" exclusive_caps=1 || {
    echo "❌ Failed to load v4l2loopback"
    exit 1
  }
fi

# Confirm that the virtual cam device exists
VIRTUAL_DEV=$(v4l2-ctl --list-devices 2>/dev/null | awk '/VirtualCam/{getline; print $1}' | head -n 1)
if [[ -z "$VIRTUAL_DEV" ]]; then
  echo "❌ Could not find VirtualCam device after loading module."
  exit 1
fi

echo "🎥 Streaming from $INPUT_DEVICE to $VIRTUAL_DEV..."

exec ffmpeg \
  -f v4l2 -framerate 30 -input_format uyvy422 -video_size 1280x720 -i "$INPUT_DEVICE" \
  -f v4l2 -pix_fmt yuv420p "$VIRTUAL_DEV" 2>>/tmp/elgato-virtualcam.err.log
