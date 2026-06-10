import copy
import itertools
import csv
import time
from collections import Counter, deque

import cv2
import mediapipe as mp
import numpy as np

from mediapipe.tasks import python
from mediapipe.tasks.python import vision

from utils.cvfpscalc import CvFpsCalc

from model import KeyPointClassifier
from model import PointHistoryClassifier

from dataclasses import dataclass


@dataclass
class QualityConfig:
    # Analyze only a central ROI for speed and relevance.
    roi_x0: float = 0.20
    roi_y0: float = 0.15
    roi_x1: float = 0.80
    roi_y1: float = 0.85

    # Downscale before analysis for speed.
    analysis_max_width: int = 320

    # Heuristic thresholds tuned for hand-landmark detection.
    brightness_low: float = 78.0
    brightness_high: float = 185.0
    contrast_low: float = 32.0
    blur_low: float = 60.0
    clip_high_ratio: float = 0.04
    clip_low_ratio: float = 0.04

    # Enhancement strength.
    dark_alpha: float = 1.10
    dark_beta: int = 16
    bright_alpha: float = 0.98
    bright_beta: int = -6
    gamma_dark: float = 1.15

    clahe_clip_limit: float = 1.6
    clahe_tile_grid_size: tuple = (8, 8)

    sharpen_enabled: bool = True
    sharpen_if_blur_below: float = 55.0

    # Smooth metrics to avoid oscillation.
    ema_alpha: float = 0.25

    # Debug overlay.
    show_overlay: bool = True


class AdaptiveFrameQualityAnalyzer:
    """
    Lightweight adaptive enhancer for live hand gesture recognition.

    Strategy:
    1) Measure brightness / contrast / blur / clipping on a small ROI.
    2) Apply only the needed corrections.
    3) Keep processing fast enough for video streams.
    """

    def __init__(self, config: QualityConfig | None = None):
        self.cfg = config or QualityConfig()
        self.clahe = cv2.createCLAHE(
            clipLimit=self.cfg.clahe_clip_limit,
            tileGridSize=self.cfg.clahe_tile_grid_size,
        )
        self.sharpen_kernel = np.array(
            [[0, -1, 0],
             [-1, 5, -1],
             [0, -1, 0]],
            dtype=np.float32
        )
        self._gamma_cache: dict[float, np.ndarray] = {}
        self._ema_metrics: dict | None = None

    def _resize_for_analysis(self, frame: np.ndarray) -> np.ndarray:
        h, w = frame.shape[:2]
        if w <= self.cfg.analysis_max_width:
            return frame
        new_w = self.cfg.analysis_max_width
        new_h = max(1, int(h * (new_w / w)))
        return cv2.resize(frame, (new_w, new_h), interpolation=cv2.INTER_AREA)

    def _get_roi(self, frame: np.ndarray) -> np.ndarray:
        h, w = frame.shape[:2]
        x0 = int(w * self.cfg.roi_x0)
        y0 = int(h * self.cfg.roi_y0)
        x1 = int(w * self.cfg.roi_x1)
        y1 = int(h * self.cfg.roi_y1)
        return frame[y0:y1, x0:x1]

    def analyze(self, frame: np.ndarray) -> dict:
        small = self._resize_for_analysis(frame)
        roi = self._get_roi(small)

        gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)

        brightness = float(gray.mean())
        contrast = float(gray.std())
        blur = float(cv2.Laplacian(gray, cv2.CV_64F).var())

        # Saturation / clipping indicators.
        low_clip = float(np.mean(gray <= 10))
        high_clip = float(np.mean(gray >= 245))

        # A simple edge-density proxy: helpful when the hand edges are weak.
        edges = cv2.Canny(gray, 60, 120)
        edge_density = float(np.mean(edges > 0))

        # Normalize into a rough 0-100 score.
        b_score = np.clip((brightness - 45.0) / (130.0 - 45.0) * 100.0, 0.0, 100.0)
        c_score = np.clip((contrast - 10.0) / (45.0 - 10.0) * 100.0, 0.0, 100.0)
        s_score = np.clip((blur - 20.0) / (150.0 - 20.0) * 100.0, 0.0, 100.0)
        e_score = np.clip(edge_density * 900.0, 0.0, 100.0)  # tuned for ROI scale

        clip_penalty = np.clip((low_clip + high_clip) * 120.0, 0.0, 100.0)

        quality = (
            0.30 * b_score +
            0.25 * c_score +
            0.30 * s_score +
            0.15 * e_score
        ) - (0.15 * clip_penalty)

        metrics = {
            "brightness": brightness,
            "contrast": contrast,
            "blur": blur,
            "low_clip": low_clip,
            "high_clip": high_clip,
            "edge_density": edge_density,
            "quality": float(np.clip(quality, 0.0, 100.0)),
        }

        # Exponential moving average to prevent frame-to-frame flicker.
        if self._ema_metrics is None:
            self._ema_metrics = metrics.copy()
        else:
            a = self.cfg.ema_alpha
            for k, v in metrics.items():
                self._ema_metrics[k] = (1.0 - a) * self._ema_metrics[k] + a * v

        return self._ema_metrics.copy()

    def _gamma_correct(self, frame: np.ndarray, gamma: float) -> np.ndarray:
        gamma = float(max(gamma, 1e-6))
        key = round(gamma, 3)
        table = self._gamma_cache.get(key)
        if table is None:
            inv_gamma = 1.0 / gamma
            table = np.array(
                [((i / 255.0) ** inv_gamma) * 255 for i in range(256)],
                dtype=np.uint8
            )
            self._gamma_cache[key] = table
        return cv2.LUT(frame, table)

    def enhance(self, frame: np.ndarray, metrics: dict) -> np.ndarray:
        out = frame
        brightness = metrics["brightness"]
        contrast = metrics["contrast"]
        blur = metrics["blur"]

        # Dark scene: lift brightness first, then gently gamma-correct.
        if brightness < self.cfg.brightness_low:
            out = cv2.convertScaleAbs(out, alpha=self.cfg.dark_alpha, beta=self.cfg.dark_beta)
            out = self._gamma_correct(out, self.cfg.gamma_dark)

        # Overexposed scene: reduce intensity slightly.
        elif brightness > self.cfg.brightness_high:
            out = cv2.convertScaleAbs(out, alpha=self.cfg.bright_alpha, beta=self.cfg.bright_beta)

        # Low contrast: CLAHE is usually the most useful lightweight fix.
        if contrast < self.cfg.contrast_low:
            lab = cv2.cvtColor(out, cv2.COLOR_BGR2LAB)
            l, a, b = cv2.split(lab)
            l = self.clahe.apply(l)
            out = cv2.cvtColor(cv2.merge((l, a, b)), cv2.COLOR_LAB2BGR)

        # Mild blur: sharpen only if necessary.
        if self.cfg.sharpen_enabled and blur < self.cfg.sharpen_if_blur_below:
            out = cv2.filter2D(out, -1, self.sharpen_kernel)

        return out

    def process(self, frame: np.ndarray) -> tuple[np.ndarray, dict]:
        metrics = self.analyze(frame)
        enhanced = self.enhance(frame, metrics)
        return enhanced, metrics


def draw_quality_overlay(image: np.ndarray, metrics: dict) -> np.ndarray:
    y = 150
    lines = [
        f"Brightness: {metrics['brightness']:.1f}",
        f"Contrast:    {metrics['contrast']:.1f}",
        f"Blur:        {metrics['blur']:.1f}",
        f"Edge dens:    {metrics['edge_density']:.3f}",
        f"Quality:     {metrics['quality']:.1f}/100",
    ]

    for i, txt in enumerate(lines):
        yy = y + i * 22
        cv2.putText(image, txt, (11, yy + 1),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.58, (0, 0, 0), 3, cv2.LINE_AA)
        cv2.putText(image, txt, (10, yy),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.58, (255, 255, 255), 1, cv2.LINE_AA)

    return image

# Create detector
current_mode = 0      # start in normal mode
current_number = -1   # no label chosen yet
number_buffer = ""

history_length = 16
point_history = deque(maxlen=history_length)
finger_gesture_history = deque(maxlen=history_length)
POINT_GESTURE_ID=3

#frame_id = 0 
cvFpsCalc = CvFpsCalc(buffer_len=10)

quality_analyzer = AdaptiveFrameQualityAnalyzer()
last_timestamp_ms = 0

base_options = python.BaseOptions(model_asset_path='hand_landmarker.task')
options = vision.HandLandmarkerOptions(
    base_options=base_options,
    running_mode=vision.RunningMode.VIDEO,
    num_hands=1,
    min_hand_detection_confidence=0.65, #0.6
    min_hand_presence_confidence=0.60,  #0.6
    min_tracking_confidence=0.55        #0.6
    )

keypoint_classifier = KeyPointClassifier()
point_history_classifier = PointHistoryClassifier()

# Read labels ###########################################################
with open('model/keypoint_classifier/keypoint_classifier_label.csv',
            encoding='utf-8-sig') as f:
        #keypoint_classifier_labels = csv.reader(f)
        keypoint_classifier_labels = [ row[0] for row in csv.reader(f)]
        
with open("model/point_history_classifier/point_history_classifier_label.csv",
            encoding="utf-8-sig") as f:
        #keypoint_classifier_labels = csv.reader(f)
        point_history_classifier_labels = [row[0] for row in csv.reader(f)]
        
detector = vision.HandLandmarker.create_from_options(options)
# Load image
stream_link = "http://espcam.local:81/stream"
cap = cv2.VideoCapture(0)
cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)

#cap.set(cv2.CAP_PROP_AUTO_EXPOSURE, 0.25)
#cap.set(cv2.CAP_PROP_EXPOSURE, -4)

#print(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
#print(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
#print(cap.get(cv2.CAP_PROP_FPS))

while True:
    fps = cvFpsCalc.get()
    
    key = cv2.waitKey(10)
    if key == 27:
        break
    
    if 48 <= key <= 57:
        number_buffer += chr(key)
    elif key == 13:  # Enter
        if number_buffer != "":
            current_number = int(number_buffer)
            print(f"Selected label: {current_number}")
            number_buffer = ""
    elif key == 8:   # Backspace
        number_buffer = number_buffer[:-1]
        print(f"Typing label: {number_buffer}")
        
    _, current_mode = select_mode(key, current_mode)
    
    ret, frame = cap.read()
    if not ret:
        break

    # Flip for mirror view
    
    #frame = cv2.resize(frame, (960, 540))
    frame = cv2.flip(frame, 1)
    frame, quality_metrics = quality_analyzer.process(frame)
    debug_image = copy.deepcopy(frame)
    
    rgb_frame = cv2.cvtColor(frame,cv2.COLOR_BGR2RGB)

    # Convert to MediaPipe image
    mp_image = mp.Image(image_format=mp.ImageFormat.SRGB,data=rgb_frame)

    # Detect hands
    rgb_frame.flags.writeable = False
    timestamp_ms = time.perf_counter_ns() // 1_000_000
    if timestamp_ms <= last_timestamp_ms:
        timestamp_ms = last_timestamp_ms + 1
    last_timestamp_ms = timestamp_ms
    
    detection_result = detector.detect_for_video(mp_image, timestamp_ms)
    rgb_frame.flags.writeable = True
    
    for hand_landmarks in detection_result.hand_landmarks:
        
        brect = calc_bounding_rect_task(debug_image, hand_landmarks)
        landmark_list = calc_landmark_list_task(debug_image, hand_landmarks)
        
        # 1) preprocess landmarks for classifier
        pre_processed_landmark_list = pre_process_landmark(landmark_list)
        
         # Point-history classifier input
        pre_processed_point_history_list = pre_process_point_history(debug_image, point_history)

        # 2) logging (gesture-only)
        logging_csv(current_number, current_mode, pre_processed_landmark_list, pre_processed_point_history_list)
        
        # 3) classification
        scores = keypoint_classifier(pre_processed_landmark_list)
        #print(scores)
        exp_scores = np.exp(scores - np.max(scores))
        probs = exp_scores / np.sum(exp_scores)
        
        hand_sign_id = int(np.argmax(probs))
        max_prob = float(np.max(probs))

        confidence_threshold = 0.2  # 0.6–0.8 with no Unknown label // 0.3-0.5 with Unknown label
        finger_gesture_confidence_threshold = 0.5
        
        if max_prob < confidence_threshold:
            hand_sign_text = "Unknown"
        else:
            if 0 <= hand_sign_id < len(keypoint_classifier_labels):
                hand_sign_text = keypoint_classifier_labels[hand_sign_id]
            else:
                hand_sign_text = "Unknown"
                
        # Update point history only when the "point" gesture is active
        if hand_sign_id == POINT_GESTURE_ID:
            point_history.append(landmark_list[8])  # index fingertip
        else:
            point_history.append([0, 0])

        # Motion gesture classification
        # Motion gesture classification
        finger_gesture_id = 0
        finger_gesture_score = 0.0
        finger_gesture_text = "Unknown"

        if len(pre_processed_point_history_list) == (history_length * 2):
            finger_gesture_id, finger_gesture_score = point_history_classifier(
                pre_processed_point_history_list
            )

        finger_gesture_history.append(finger_gesture_id)
        most_common_fg = Counter(finger_gesture_history).most_common(1)

        if finger_gesture_score >= finger_gesture_confidence_threshold:
            if most_common_fg:
                fg_id = most_common_fg[0][0]
                if 0 <= fg_id < len(point_history_classifier_labels):
                    finger_gesture_text = point_history_classifier_labels[fg_id]
                else:
                    finger_gesture_text = "Unknown"
        else:
            finger_gesture_text = "Unknown"          

        debug_image = draw_landmarks_task(debug_image, landmark_list)
        debug_image = draw_point_history(debug_image, point_history)
        debug_image = draw_connections_task(debug_image, landmark_list)
        debug_image = draw_bounding_rect_task(debug_image, brect)
        
        debug_image = draw_gesture_info(
                debug_image,
                brect,
                hand_sign_text,
                finger_gesture_text
            )
    # Show
    debug_image = draw_info(debug_image, fps, current_mode, current_number, number_buffer)
    debug_image = draw_quality_overlay(debug_image, quality_metrics)
    cv2.imshow("Hand Gesture Recognition",debug_image)
    
cap.release()
cv2.destroyAllWindows()

def select_mode(key: int, mode: int):
    number = -1
    # mode keys
    if key == ord('n'):
        mode = 0         # normal
    if key == ord('k'):
        mode = 1         # logging Keypoint
    if key == ord('h'):  # logging Point_history
        mode = 2
    return number, mode

def calc_bounding_rect_task(image, hand_landmarks):
    image_width, image_height = image.shape[1], image.shape[0]
    landmark_array = np.empty((0, 2), int)

    for landmark in hand_landmarks:
        landmark_x = min(int(landmark.x * image_width), image_width - 1)
        landmark_y = min(int(landmark.y * image_height), image_height - 1)

        landmark_point = [np.array((landmark_x, landmark_y))]
        landmark_array = np.append(landmark_array, landmark_point, axis=0)

    x, y, w, h = cv2.boundingRect(landmark_array)
    return [x, y, x + w, y + h]

def calc_landmark_list_task(image, hand_landmarks):
    image_width, image_height = image.shape[1], image.shape[0]
    landmark_point = []

    for landmark in hand_landmarks:
        landmark_x = min(int(landmark.x * image_width), image_width - 1)
        landmark_y = min(int(landmark.y * image_height), image_height - 1)
        landmark_point.append([landmark_x, landmark_y])

    return landmark_point

def pre_process_landmark(landmark_list: list[list[int]]) -> list[float]:
    temp_landmark_list = copy.deepcopy(landmark_list)

    # Convert to relative coordinates
    base_x, base_y = 0, 0
    for index, landmark_point in enumerate(temp_landmark_list):
        if index == 0:
            base_x, base_y = landmark_point[0], landmark_point[1]

        temp_landmark_list[index][0] = temp_landmark_list[index][0] - base_x
        temp_landmark_list[index][1] = temp_landmark_list[index][1] - base_y

    # Convert to a one-dimensional list
    temp_landmark_list = list(
        itertools.chain.from_iterable(temp_landmark_list)
    )

    # Normalization
    if len(temp_landmark_list) == 0:
        return temp_landmark_list

    max_value = max(list(map(abs, temp_landmark_list)))
    if max_value == 0:
        # Avoid division by zero, return as is
        return temp_landmark_list

    def normalize_(n):
        return n / max_value

    temp_landmark_list = list(map(normalize_, temp_landmark_list))

    return temp_landmark_list

def pre_process_point_history(image, point_history):
    image_width, image_height = image.shape[1], image.shape[0]

    temp_point_history = copy.deepcopy(point_history)

    base_x, base_y = 0, 0
    for index, point in enumerate(temp_point_history):
        if index == 0:
            base_x, base_y = point[0], point[1]

        temp_point_history[index][0] = (temp_point_history[index][0] - base_x) / image_width
        temp_point_history[index][1] = (temp_point_history[index][1] - base_y) / image_height

    temp_point_history = list(itertools.chain.from_iterable(temp_point_history))
    return temp_point_history

# --- CSV logging (adapted from app.py:280–293) ---
def logging_csv(number: int, mode: int, landmark_list: list[float], point_history_list=None):
    if mode == 0:
        return
    if mode == 1 and (0 <= number <= 9):
        csv_path = 'model/keypoint_classifier/keypoint.csv'
        with open(csv_path, 'a', newline="") as f:
            writer = csv.writer(f)
            writer.writerow([number, *landmark_list])
            
    if mode == 2 and (0 <= number <= 9):
        csv_path = "model/point_history_classifier/point_history.csv"
        with open(csv_path, "a", newline="") as f:
            writer = csv.writer(f)
            writer.writerow([number, *point_history_list])        

def draw_landmarks_task(image, hand_landmark_points):
    for point in hand_landmark_points:
        cv2.circle(image, tuple(point), 3, (255, 255, 255), 8)
        cv2.circle(image, tuple(point), 3, (0, 0, 0), 4)
    return image

def draw_point_history(image, point_history):
    for index, point in enumerate(point_history):
        if point[0] != 0 and point[1] != 0:
            cv2.circle(image, (point[0], point[1]), 1 + int(index / 2),
                      (152, 251, 152), 2)
    return image

def draw_connections_task(image, hand_landmark_points):
    HAND_CONNECTIONS = [
        (0, 1), (1, 2), (2, 3), (3, 4),
        (0, 5), (5, 6), (6, 7), (7, 8),
        (5, 9), (9, 10), (10, 11), (11, 12),
        (9, 13), (13, 14), (14, 15), (15, 16),
        (13, 17), (17, 18), (18, 19), (19, 20),
        (0, 17)
    ]

    for start_idx, end_idx in HAND_CONNECTIONS:
        if start_idx < len(hand_landmark_points) and end_idx < len(hand_landmark_points):
            start_point = tuple(hand_landmark_points[start_idx])
            end_point = tuple(hand_landmark_points[end_idx])

            cv2.line(image, start_point, end_point, (0, 0, 0), 6)
            cv2.line(image, start_point, end_point, (255, 255, 255), 2)
    return image

def draw_bounding_rect_task(image, brect):
    cv2.rectangle(image, (brect[0], brect[1]), (brect[2], brect[3]), (0, 0, 0), 2)
    cv2.rectangle(image, (brect[0], brect[1]), (brect[2], brect[3]), (255, 255, 255), 1)
    return image

def draw_gesture_info(image, brect, hand_sign_text, finger_gesture_text):
    # Draw rectangle
    cv2.rectangle(image, (brect[0], brect[1]), (brect[2], brect[1] - 22),
                 (0, 0, 0), -1)

    info_text = "Gesture"
    if hand_sign_text != "":
        info_text = info_text + ' : ' + hand_sign_text
    cv2.putText(image, info_text, (brect[0] + 5, brect[1] - 4),
               cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1, cv2.LINE_AA)
    
    if finger_gesture_text != "":
        cv2.putText(image, "Finger Gesture:" + finger_gesture_text, (10, 60),
                   cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 0, 0), 4, cv2.LINE_AA)
        cv2.putText(image, "Finger Gesture:" + finger_gesture_text, (10, 60),
                   cv2.FONT_HERSHEY_SIMPLEX, 1.0, (255, 255, 255), 2, cv2.LINE_AA)

    return image

def draw_info(image, fps, mode, number, buffer_text=""):
    cv2.putText(image, "FPS:" + str(int(fps)), (10, 30),
               cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 0, 0), 4, cv2.LINE_AA)
    cv2.putText(image, "FPS:" + str(int(fps)), (10, 30),
               cv2.FONT_HERSHEY_SIMPLEX, 1.0, (255, 255, 255), 2, cv2.LINE_AA)
    
    mode_string=['Logging Keypoint','Logging Point_history']
    
    if 1 <= mode <= 2:
        cv2.putText(image, "MODE:" + mode_string[mode - 1], (10, 90),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1, cv2.LINE_AA)
        if 0 <= number <= 9:
            cv2.putText(image, "NUM:" + str(number), (10, 110),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1, cv2.LINE_AA)

    label_text = f"Label:{number}"
    cv2.putText(image, label_text, (10, 90),
               cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 0, 0), 4, cv2.LINE_AA)
    cv2.putText(image, label_text, (10, 90),
               cv2.FONT_HERSHEY_SIMPLEX, 1.0, (255, 255, 255), 2, cv2.LINE_AA)

    if buffer_text != "":
        buf_text = f"Typing:{buffer_text}"
        cv2.putText(image, buf_text, (10, 120),
                   cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 0, 255), 4, cv2.LINE_AA)
        cv2.putText(image, buf_text, (10, 120),
                   cv2.FONT_HERSHEY_SIMPLEX, 1.0, (255, 255, 0), 2, cv2.LINE_AA)

    return image
