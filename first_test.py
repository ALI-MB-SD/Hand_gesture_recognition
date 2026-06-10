import cv2
import mediapipe as mp
import numpy as np

from mediapipe.tasks import python
from mediapipe.tasks.python import vision

# Draw landmarks manually

def draw_landmarks_on_image(rgb_image, detection_result):

    annotated_image = np.copy(rgb_image)

    h, w, _ = annotated_image.shape

    # Hand connections
    HAND_CONNECTIONS = [
        (0,1),(1,2),(2,3),(3,4),
        (0,5),(5,6),(6,7),(7,8),
        (5,9),(9,10),(10,11),(11,12),
        (9,13),(13,14),(14,15),(15,16),
        (13,17),(17,18),(18,19),(19,20),
        (0,17)
    ]

    for hand_landmarks in detection_result.hand_landmarks:

        points = []

        # Convert normalized coords -> pixel coords
        for landmark in hand_landmarks:

            x = int(landmark.x * w)
            y = int(landmark.y * h)

            points.append((x, y))

            # Draw point
            cv2.circle(
                annotated_image,
                (x, y),
                5,
                (255, 0, 0),
                -1
            )

        # Draw connections
        for connection in HAND_CONNECTIONS:

            start_idx = connection[0]
            end_idx = connection[1]

            cv2.line(
                annotated_image,
                points[start_idx],
                points[end_idx],
                (0, 255, 0),
                2
            )

    return annotated_image


# Create detector

base_options = python.BaseOptions(
model_asset_path='hand_landmarker.task'
)

options = vision.HandLandmarkerOptions(
base_options=base_options,
num_hands=2
)

detector = vision.HandLandmarker.create_from_options(options)

# Load image

cap = cv2.VideoCapture(0)

while True:

    ret, frame = cap.read()

    if not ret:
        break

    # Flip for mirror view
    frame = cv2.flip(frame, 1)

    # Convert BGR -> RGB
    rgb_frame = cv2.cvtColor(
        frame,
        cv2.COLOR_BGR2RGB
    )

    # Convert to MediaPipe image
    mp_image = mp.Image(
        image_format=mp.ImageFormat.SRGB,
        data=rgb_frame
    )

    # Detect hands
    detection_result = detector.detect(mp_image)

    # Draw landmarks
    annotated_image = draw_landmarks_on_image(
    rgb_frame,
    detection_result
    )

    # Convert RGB -> BGR
    annotated_image = cv2.cvtColor(
        annotated_image,
        cv2.COLOR_RGB2BGR
    )

    # Show
    cv2.imshow(
        "Hand Tracking",
        annotated_image
    )

    # Press ESC to quit
    key = cv2.waitKey(1)

    if key == 27:
        break
cap.release()
cv2.destroyAllWindows()    
