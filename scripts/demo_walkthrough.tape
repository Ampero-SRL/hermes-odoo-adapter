# vhs tape file for the optional ~90 s open-module demo clip.
#
# Render with:
#   go install github.com/charmbracelet/vhs@latest
#   vhs scripts/demo_walkthrough.tape   # produces demo.gif
#
# vhs runs commands in a headless terminal and captures the output to
# a GIF/MP4 — no manual screen recording needed.

Output media/demo.gif
Output media/demo.mp4

Set FontSize 14
Set Width 1280
Set Height 720
Set Theme "Dracula"
Set TypingSpeed 35ms
Set PlaybackSpeed 1.0

Type "bash scripts/demo_walkthrough.sh"
Enter

# The walkthrough script does its own pacing (sleep between scenes).
# Wait for it to finish + a couple of seconds of credit time.
Sleep 95s
