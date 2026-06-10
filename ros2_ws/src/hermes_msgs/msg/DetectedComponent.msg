# A single detected component with its pick coordinates
string class_name           # detection class name
string sku                  # Odoo SKU (empty if unmapped)
float32 confidence          # detection confidence 0.0-1.0
string class_source         # detector or reclassifier
string detector_class_name  # original detector class before any override
string classifier_class_name  # classifier top-1 class if evaluated
float32 classifier_confidence  # classifier top-1 confidence
string proposal_source      # foreground_blob, detector_bbox, rtmdet_mask, ...
string mask_source          # rtmdet_mask, grabcut_mask, sam2_rescue, ...
float32 retrieval_score     # memory-bank cosine score when available
float32 retrieval_margin    # top-1 minus top-2 SKU score
string reference_id         # best-matching memory-bank reference ID
string reference_pose       # best-matching pose label

# Bounding box in pixels (top-left origin)
int32 bbox_x
int32 bbox_y
int32 bbox_w
int32 bbox_h

# Pick point in robot base frame (meters)
geometry_msgs/Point pick_point

# Pick point in pixel coordinates (refined when template matching succeeds)
geometry_msgs/Point pixel_point
