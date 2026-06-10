# Gesture command from ROS4HRI vision module
# Used to control mission flow via operator gestures

# Command types
string PAUSE=PAUSE
string RESUME=RESUME
string CONFIRM=CONFIRM
string ABORT=ABORT
string HANDOVER_READY=HANDOVER_READY

# The command to execute
string command

# Gesture type that triggered this command (e.g., open_palm, thumbs_up)
string gesture_type

# Identifier of the tracked body that made the gesture
string body_id

# Confidence score of the gesture detection (0.0 - 1.0)
float32 confidence

# Hand position in normalized image coordinates (optional)
geometry_msgs/Point hand_position
