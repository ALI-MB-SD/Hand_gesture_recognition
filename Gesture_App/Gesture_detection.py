import copy
import itertools
import csv
import time
from collections import Counter, deque
from dataclasses import dataclass

import cv2
import mediapipe as mp
import numpy as np

from mediapipe.tasks import python
from mediapipe.tasks.python import vision

from utils.cvfpscalc import CvFpsCalc

from model import KeyPointClassifier
from model import PointHistoryClassifier

import os,json, hmac, hashlib, secrets
from pathlib import Path
from datetime import datetime
from uuid import uuid4

from dotenv import load_dotenv
import requests
 
######################################################################################################
######################################################################################################

DATA_DIR = Path("data/commands")
DATA_DIR.mkdir(parents=True, exist_ok=True)

SESSION_ID = datetime.now().strftime("session_%Y-%m-%d_%H-%M-%S")
SESSION_FILE = DATA_DIR / f"{SESSION_ID}.jsonl"

load_dotenv()
SERVER_URL = os.getenv("SERVER_URL", "https://api.alimb.ir").rstrip("/")
HMAC_SECRET_KEY = os.getenv("HMAC_SECRET_KEY", "").strip()
REQUEST_TIMEOUT_SECONDS = float(os.getenv("REQUEST_TIMEOUT_SECONDS", "5"))
SERVER_USERNAME = os.getenv("SERVER_USERNAME","").strip()
SERVER_PASSWORD = os.getenv("SERVER_PASSWORD","").strip()

#CA_CERT = os.getenv("GESTURE_SERVER_CA")

def save_data_command(event: dict, file_path: Path = SESSION_FILE) -> None:
    """
    Append one confirmed DataCommand to a JSONL file.
    """
    file_path.parent.mkdir(parents=True, exist_ok=True)
    
    event = dict(event)
    event["event_id"] = event.get("event-id") or uuid4().hex
    event["session_id"] = SESSION_ID
    event["created_at"] = datetime.utcnow().isoformat() +"Z"
    
    file_path.parent.mkdir(parents=True, exist_ok=True)

    with file_path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(event, ensure_ascii=False) + "\n")


def load_data_commands(file_path: Path = SESSION_FILE) -> list[dict]:
    """
    Read back a JSONL file for later transfer or debugging.
    """
    if not file_path.exists():
        return []

    items = []
    with file_path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                items.append(json.loads(line))
    return items

def build_command_hmac_message(command_data: dict) -> str:
    """
    Build the canonical JSON string used by both PC and server for HMAC.
    """
    canonical = {
        "event_id": command_data["event_id"],
        "session_id": command_data["session_id"],
        "pose": command_data["pose"],
        "motion": command_data["motion"],
        "motion_source": command_data.get("motion_source") or "",
        "support": command_data.get("support"),
        "pose_score": command_data.get("pose_score"),
        "motion_score": command_data.get("motion_score"),
        "quality": command_data.get("quality"),
        "timestamp_ms": int(command_data["timestamp_ms"]),
        "nonce": command_data["nonce"],
    }
    return json.dumps(canonical, sort_keys=True, separators=(",", ":"), ensure_ascii=False)

def sign_command_payload(command_data: dict) -> str:
    if not HMAC_SECRET_KEY:
        raise RuntimeError("HMAC_SECRET_KEY is not set in the environment")
    message = build_command_hmac_message(command_data)
    return hmac.new(
        HMAC_SECRET_KEY.encode("utf-8"),
        message.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()

def build_signed_server_payload(confirmed: dict, timestamp_ms: int) -> dict:
    """
    Build the exact payload expected by POST /commands/ingest.
    """
    payload = {
        "event_id": uuid4().hex,
        "session_id": SESSION_ID,
        "pose": confirmed["pose"],
        "motion": confirmed["motion"],
        "motion_source": confirmed.get("motion_source") or "",
        "support": float(confirmed["support"]),
        "pose_score": float(confirmed["pose_score"]),
        "motion_score": float(confirmed["motion_score"]),
        "quality": float(confirmed["quality"]),
        "timestamp_ms": int(timestamp_ms),
        "nonce": secrets.token_urlsafe(16),
    }
    payload["signature"] = sign_command_payload(payload)
    return payload

def login_and_get_token(username: str, password: str) -> str:
    r = requests.post(
        f"{SERVER_URL}/users/login",
        json={"username": username, "password": password},
        timeout=5,
    )
    r.raise_for_status()
    return r.json()["access_token"]
print("SERVER_URL =", SERVER_URL)
JWT_TOKEN = login_and_get_token(SERVER_USERNAME, SERVER_PASSWORD)

def post_command_to_server(payload: dict) -> dict:
    """
    Send one signed command to the FastAPI server.
    Returns a small result dict for logging/debugging.
    """
    if not JWT_TOKEN:
        return {
            "ok": False,
            "error": "GESTURE_SERVER_JWT is not set",
        }

    url = f"{SERVER_URL}/commands/ingest"
    headers = {
        "Authorization": f"Bearer {JWT_TOKEN}",
        "Content-Type": "application/json",
    }

    try:
        response = requests.post(
            url,
            json=payload,
            headers=headers,
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
        try:
            body = response.json()
        except Exception:
            body = {"text": response.text}

        return {
            "ok": response.ok,
            "status_code": response.status_code,
            "response": body,
        }
    except requests.RequestException as exc:
        return {
            "ok": False,
            "error": str(exc),
        }
        
######################################################################################################
######################################################################################################

# Frame quality analyzer
# -----------------------------------------------------------------------------

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
        cv2.putText(image, txt, (11, yy + 20),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.58, (0, 0, 0), 3, cv2.LINE_AA)
        cv2.putText(image, txt, (10, yy + 19),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.58, (255, 255, 255), 1, cv2.LINE_AA)

    return image

#########################################################################################
#########################################################################################

# Command layer
# -----------------------------------------------------------------------------
def majority_label(history, min_votes=3):
    """
    Returns:
        (label, confidence_ratio)
    """
    if not history:
        return "Unknown", 0.0

    label, count = Counter(history).most_common(1)[0]
    confidence = count / len(history)

    if count < min_votes:
        return "Unknown", confidence

    return label, confidence


@dataclass
class CommandRule:
    pose: str
    motion: str
    command: str
    cooldown_ms: int = 1000


@dataclass
class CommandEvent:
    command: str
    pose: str
    motion: str
    motion_source : str
    pose_score: float
    motion_score: float
    timestamp_ms: int
    
class CommandEngine:
    """
    Combines static pose + motion label into one command.
    """
    def __init__(self, rules, pose_vote_len=5, motion_vote_len=5):
        self.rule_map = {
            (norm_label(rule.pose), norm_label(rule.motion)): rule
            for rule in rules
        }
        self.pose_history = deque(maxlen=pose_vote_len)
        self.motion_history = deque(maxlen=motion_vote_len)
        self.last_emit_ms = {}
        self.last_motion_source = None
        self.event_log = deque(maxlen=200)

    def update(self, pose_text, pose_score, motion_text, motion_score, 
               motion_source, quality_metrics, timestamp_ms):
        self.pose_history.append(pose_text)
        
        if motion_source != self.last_motion_source:
            self.motion_history.clear()
            self.last_motion_source = motion_source
        
        self.motion_history.append(motion_text)

        stable_pose, pose_conf = majority_label(self.pose_history, min_votes=3)
        stable_motion, motion_conf = majority_label(self.motion_history, min_votes=3)

        rule = self.rule_map.get((norm_label(stable_pose), norm_label(stable_motion)))
        if rule is None:
            return None

        last_time = self.last_emit_ms.get(rule.command, -10**9)
        if timestamp_ms - last_time < rule.cooldown_ms:
            return None

        if pose_score < 0.30 or motion_score < 0.40:
            return None

        event = CommandEvent(
            command=rule.command,
            pose=stable_pose,
            motion=stable_motion,
            motion_source= motion_source,
            pose_score=float(pose_score),
            motion_score=float(motion_score),
            timestamp_ms=int(timestamp_ms),
        )

        self.last_emit_ms[rule.command] = timestamp_ms
        self.event_log.append({
            "command": event.command,
            "pose": event.pose,
            "motion": event.motion,
            "motion_source": event.motion_source,
            "pose_score": event.pose_score,
            "motion_score": event.motion_score,
            "timestamp_ms": event.timestamp_ms,
            "quality": quality_metrics,
            "pose_vote_conf": pose_conf,
            "motion_vote_conf": motion_conf,
        })
        return event
#def get_hand_center_from_brect(brect):
#    return [(brect[0] + brect[2]) // 2, (brect[1] + brect[3]) // 2]
def get_palm_center(landmark_list):
    ids = [0, 5, 9, 13, 17]
    x = int(np.mean([landmark_list[i][0] for i in ids]))
    y = int(np.mean([landmark_list[i][1] for i in ids]))
    return [x, y]

# Label normalization
# ==========================================================
def norm_label(s):
    return ( str(s).lower().replace("_", "").replace(" ", "") )

# Safe history clear
# ==========================================================
def clear_motion_buffers(point_history,hand_center_history):
    point_history.clear()
    hand_center_history.clear()
    
def resolve_point_gesture_id(labels, default=3):
    candidates = ["point", "pointing", "indexpoint", "index"]
    for i, label in enumerate(labels):
        n = norm_label(label)
        if any(c in n for c in candidates):
            return i
    return default

########################################################################################
########################################################################################
def select_mode(key: int, mode: int):
    number = -1
    # mode keys
    if key == ord('n'):
        mode = 0         # normal
    if key == ord('k'):
        mode = 1         # logging Keypoint
    if key == ord('h'):  # logging Point_history
        mode = 2
    if key == ord('g'):
        mode = 3    
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

def pre_process_motion_history(image, motion_history):
    image_width, image_height = image.shape[1], image.shape[0]
    temp_motion_history = copy.deepcopy(motion_history)

    base_x, base_y = 0, 0
    for index, point in enumerate(temp_motion_history):
        if index == 0:
            base_x, base_y = point[0], point[1]

        temp_motion_history[index][0] = (temp_motion_history[index][0] - base_x) / image_width
        temp_motion_history[index][1] = (temp_motion_history[index][1] - base_y) / image_height

    temp_motion_history = list(itertools.chain.from_iterable(temp_motion_history))
    return temp_motion_history

def pre_process_point_history(image, point_history):
    return pre_process_motion_history(image, point_history)

# --- CSV logging 
def logging_csv(number: int,
                mode: int, 
                landmark_list: list[float], 
                point_history_list=None,
                hand_center_history_list=None):
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
    if mode == 3 and (0 <= number <= 9) and hand_center_history_list is not None:
        csv_path = 'model/hand_center_history_classifier/hand_center_history.csv'
        with open(csv_path, 'a', newline="") as f:
            writer = csv.writer(f)
            writer.writerow([number, *hand_center_history_list])                

########################################################################################
########################################################################################

def draw_landmarks_task(image, hand_landmark_points):
    for point in hand_landmark_points:
        cv2.circle(image, tuple(point), 3, (255, 255, 255), 8)
        cv2.circle(image, tuple(point), 3, (0, 0, 0), 4)
    return image

def draw_motion_history(image, motion_history, color, thickness=2):
    for index, point in enumerate(motion_history):
        if point[0] != 0 and point[1] != 0:
            cv2.circle(image, (point[0], point[1]), 1 + int(index / 2), color, thickness)
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

def draw_gesture_info(image, brect, hand_sign_text, motion_text, motion_source="", command_text="", data_command_text=""):
    cv2.rectangle(image, (brect[0], brect[1]), (brect[2], brect[1] - 22), (0, 0, 0), -1)

    info_text = "Gesture"
    if hand_sign_text != "":
        info_text += f" : {hand_sign_text}"
    cv2.putText(image, info_text, (brect[0] + 5, brect[1] - 4),
                cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1, cv2.LINE_AA)

    if motion_text != "":
        motion_label = "Motion"
        if motion_source != "":
            motion_label += f"[{motion_source}]"
        cv2.putText(image, f"{motion_label}:{motion_text}", (10, 60),
                    cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 0, 0), 4, cv2.LINE_AA)
        cv2.putText(image, f"{motion_label}:{motion_text}", (10, 60),
                    cv2.FONT_HERSHEY_SIMPLEX, 1.0, (255, 255, 255), 2, cv2.LINE_AA)

    if command_text != "":
        cv2.putText(image, "Command:" + command_text, (10, 115),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 0, 0), 4, cv2.LINE_AA)
        cv2.putText(image, "Command:" + command_text, (10, 115),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 255, 255), 2, cv2.LINE_AA)
        
    if data_command_text != "":
        cv2.putText(image, "DataCommand:" + data_command_text, (10, 150),
                cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 0, 0), 4, cv2.LINE_AA)
        cv2.putText(image, "DataCommand:" + data_command_text, (10, 150),
                cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 255, 0), 2, cv2.LINE_AA)    

    return image

def draw_info(image, fps, mode, number, buffer_text=""):
    cv2.putText(image, "FPS:" + str(int(fps)), (10, 30),
                cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 0, 0), 4, cv2.LINE_AA)
    cv2.putText(image, "FPS:" + str(int(fps)), (10, 30),
                cv2.FONT_HERSHEY_SIMPLEX, 1.0, (255, 255, 255), 2, cv2.LINE_AA)

    mode_string = [
        'Normal',
        'Logging Keypoint',
        'Logging Point History',
        'Logging Hand Center History',
    ]

    if 0 <= mode < len(mode_string):
        cv2.putText(image, "MODE:" + mode_string[mode], (10, 90),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1, cv2.LINE_AA)

    if 0 <= number <= 9:
        cv2.putText(image, "NUM:" + str(number), (10, 110),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1, cv2.LINE_AA)

    '''label_text = f"Label:{number}"
    cv2.putText(image, label_text, (10, 135),
                cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 0, 0), 4, cv2.LINE_AA)
    cv2.putText(image, label_text, (10, 135),
                cv2.FONT_HERSHEY_SIMPLEX, 1.0, (255, 255, 255), 2, cv2.LINE_AA)'''

    if buffer_text != "":
        buf_text = f"Typing:{buffer_text}"
        cv2.putText(image, buf_text, (10, 170),
                    cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 0, 255), 4, cv2.LINE_AA)
        cv2.putText(image, buf_text, (10, 170),
                    cv2.FONT_HERSHEY_SIMPLEX, 1.0, (255, 255, 0), 2, cv2.LINE_AA)

    return image

########################################################################################
########################################################################################

# Create detector
current_mode = 0      # start in normal mode
current_number = -1   # no label chosen yet
number_buffer = ""

history_length = 16
point_history = deque(maxlen=history_length)
hand_center_history = deque(maxlen=history_length)
#finger_gesture_history = deque(maxlen=history_length)
#POINT_GESTURE_ID=3

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
detector = vision.HandLandmarker.create_from_options(options)

keypoint_classifier = KeyPointClassifier()

point_history_classifier = PointHistoryClassifier(
        model_path='model/point_history_classifier/point_history_classifier.tflite',
        score_th=0.5,
        invalid_value=0,
    )

hand_center_history_classifier = PointHistoryClassifier(
    model_path='model/hand_center_history_classifier/hand_center_history_classifier.tflite',
    score_th=0.5,
    invalid_value=0,
)

# Read labels ###########################################################
with open('model/keypoint_classifier/keypoint_classifier_label.csv',
            encoding='utf-8-sig') as f:
        keypoint_classifier_labels = [ row[0] for row in csv.reader(f)]
        
with open("model/point_history_classifier/point_history_classifier_label.csv",
            encoding="utf-8-sig") as f:
        point_history_classifier_labels = [row[0] for row in csv.reader(f)]
        
with open('model/hand_center_history_classifier/hand_center_history_classifier_label.csv', 
            encoding='utf-8-sig') as f:
        hand_center_history_classifier_labels = [row[0] for row in csv.reader(f)]
        
point_gesture_id = resolve_point_gesture_id(keypoint_classifier_labels, default=3)
point_gesture_name = keypoint_classifier_labels[point_gesture_id] if 0 <= point_gesture_id < len(keypoint_classifier_labels) else 'fallback' 
print(f"Resolved POINT_GESTURE_ID = {point_gesture_id} ({point_gesture_name})")

command_rules = [
    CommandRule("OK", "Swipe Right", "OPEN_APP", cooldown_ms=1200),
    CommandRule("Three", "Swipe Left", "CLOSE_APP", cooldown_ms=1200),
    CommandRule("Three", "Swipe Up", "SCROLL_UP", cooldown_ms=1200),
    CommandRule("Three", "Swipe Down", "SCROLL_DOWN", cooldown_ms=1200),
    CommandRule("Pointer", "Circle", "CONFIRM", cooldown_ms=1200),
    CommandRule("Pointer", "Clockwise", "NEXT", cooldown_ms=1200),
    CommandRule("Pointer", "Counter Clockwise", "PREVIOUS", cooldown_ms=1200),
    CommandRule("OK", "Swipe Down", "TURN_OFF", cooldown_ms=1200),
    CommandRule("OK", "Swipe Up", "TURN_ON", cooldown_ms=1200),
]

command_engine = CommandEngine(command_rules, pose_vote_len=5, motion_vote_len=5)        

# Command confirmation
# ==========================================================
data_command_event = None
data_command_log = deque(maxlen=300)
data_command_window = deque(maxlen=10)

latest_command_text = ""
data_command_display = 0
data_command_text = ""

COMMAND_LOCK_MS = 1200          # time lock after a confirmed data command
REARM_NEUTRAL_FRAMES = 6        # require this many neutral frames before re-arming
DATA_COMMAND_DISPLAY_FRAMES = 20

command_state = "ACTIVE"        # ACTIVE | LOCKED
command_locked_until_ms = 0
neutral_frames = 0

POSE_SETTLE_FRAMES = 3
pose_candidate = "Unknown"
pose_candidate_count = 0

# Load image
stream_link = "http://espcam.local:81/stream"
cap = cv2.VideoCapture(0)
cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)


# Confirmed command system
# ====================================================
def confirm_data_command(window, ratio_th=0.8, min_valid=8,
                        pose_score_th=0.30, motion_score_th=0.50, quality_th=55.0 ):
    valid = [x for x in window if x is not None]

    if len(valid) < min_valid:
        return None

    counter = Counter( item["command"] for item in valid )
    
    command_name, command_count = counter.most_common(1)[0]
    support = command_count / len(valid)
    if support < ratio_th:
        return None

    selected = [
        item
        for item in valid
        if item["command"] == command_name
    ]
    
    pose_score = np.mean( [x["pose_score"] for x in selected] )
    motion_score = np.mean( [x["motion_score"] for x in selected] )
    quality_score = np.mean( [x["quality"]["quality"] for x in selected] )

    if pose_score < pose_score_th:
        return None

    if motion_score < motion_score_th:
        return None

    if quality_score < quality_th:
        return None
    
    print("valid:", len(valid), "support:", support, "command:", command_name)
    return {
        "command": command_name,
        "support": float(support),
        "pose_score": float(pose_score),
        "motion_score": float(motion_score),
        "quality": float(quality_score),

        "pose": Counter( x["pose"] for x in selected).most_common(1)[0][0],
        "motion": Counter( x["motion"] for x in selected).most_common(1)[0][0],
        "motion_source": Counter( x["motion_source"] for x in selected).most_common(1)[0][0],
    }
    ########################################################
def make_command_candidate(pose_text, motion_text, motion_source, pose_score, motion_score,
                            quality_metrics, rule_map ):
    key = (norm_label(pose_text), norm_label(motion_text))
    rule = rule_map.get(key)

    if rule is None:
        return None
    if pose_score < 0.30 or motion_score < 0.30:
        return None

    return {
        "command": rule.command,
        "pose": pose_text,
        "motion": motion_text,
        "motion_source": motion_source,
        "pose_score": float(pose_score),
        "motion_score": float(motion_score),
        "quality": quality_metrics,
    }    

def update_pose_settle( pose_text, pose_candidate, pose_candidate_count, settle_frames,
                        point_history, hand_center_history, data_command_window):
    normalized_pose = norm_label(pose_text)
    
    if normalized_pose != pose_candidate:
        pose_candidate = normalized_pose
        pose_candidate_count = 1

        # Pose changed: clear old motion so transition movement does not count
        clear_motion_buffers(point_history, hand_center_history)
        data_command_window.clear()
    else:
        pose_candidate_count += 1
        
    pose_ready = ( normalized_pose != "unknown" and pose_candidate_count >= settle_frames)
    return pose_candidate, pose_candidate_count, pose_ready

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
    
    server_timestamp_ms = int(time.time() * 1000)
    
    detection_result = detector.detect_for_video(mp_image, timestamp_ms)
    rgb_frame.flags.writeable = True
    
    hand_sign_text = "Unknown"
    motion_text = "Unknown"
    motion_source = ""
    command_text = latest_command_text
    
    if detection_result.hand_landmarks:
        for hand_landmarks in detection_result.hand_landmarks:
            
            brect = calc_bounding_rect_task(debug_image, hand_landmarks)
            landmark_list = calc_landmark_list_task(debug_image, hand_landmarks)
            
            # 1) preprocess landmarks for classifier
            pre_processed_landmark_list = pre_process_landmark(landmark_list)
            
            # Point-history classifier input
            pre_processed_point_history_list = pre_process_motion_history(debug_image, point_history)
            pre_processed_hand_center_history_list = pre_process_motion_history(debug_image, hand_center_history)
            
            # 2) logging (gesture-only)
            logging_csv(
                current_number, 
                current_mode, 
                pre_processed_landmark_list, 
                pre_processed_point_history_list,
                pre_processed_hand_center_history_list)
            
            # 3) Static pose classification
            scores = keypoint_classifier(pre_processed_landmark_list)
            exp_scores = np.exp(scores - np.max(scores))
            probs = exp_scores / np.sum(exp_scores)
            
            hand_sign_id = int(np.argmax(probs))
            max_prob = float(np.max(probs))
            confidence_threshold = 0.3 
            
            
            
            if max_prob < confidence_threshold:
                hand_sign_text = "Unknown"
            else:
                if 0 <= hand_sign_id < len(keypoint_classifier_labels):
                    hand_sign_text = keypoint_classifier_labels[hand_sign_id]
                else:
                    hand_sign_text = "Unknown"
            
            pose_candidate, pose_candidate_count, pose_ready = update_pose_settle(
                hand_sign_text,
                pose_candidate,
                pose_candidate_count,
                POSE_SETTLE_FRAMES,
                point_history,
                hand_center_history,
                data_command_window,
            )
            
            # If pose is still changing, do not let motion create commands yet
            if not pose_ready:
                motion_text = "Unknown"
                motion_source = ""
                current_motion_score = 0.0
                latest_command_event = None
                command_text = ""
                data_command_window.append(None)
            else :            
                # Motion source A: fingertip history for pointer gestures
                if hand_sign_id == point_gesture_id and hand_sign_text != "Unknown":
                    motion_source = "Point"
                    hand_center_history.append([0, 0])
                    point_history.append(landmark_list[8])

                    pre_processed_point_history_list = pre_process_motion_history(debug_image, point_history)

                    point_motion_id, point_motion_score = (0, 0.0)
                    if len(pre_processed_point_history_list) == (history_length * 2):
                        point_motion_id, point_motion_score = point_history_classifier(
                            pre_processed_point_history_list
                        )

                    if point_motion_score >= 0.5:
                        if 0 <= point_motion_id < len(point_history_classifier_labels):
                            motion_text = point_history_classifier_labels[point_motion_id]
                        else:
                            motion_text = "Unknown"
                    else:
                        motion_text = "Unknown"

                    current_motion_score = point_motion_score

                # Motion source B: hand-center history for non-pointer gestures
                else:
                    motion_source = "Center"
                    point_history.append([0, 0])

                    center_point = get_palm_center(landmark_list)
                    hand_center_history.append(center_point)

                    pre_processed_hand_center_history_list = pre_process_motion_history(
                        debug_image,
                        hand_center_history,
                    )

                    center_motion_id, center_motion_score = (0, 0.0)
                    if len(pre_processed_hand_center_history_list) == (history_length * 2):
                        center_motion_id, center_motion_score = hand_center_history_classifier(
                            pre_processed_hand_center_history_list
                        )

                    if center_motion_score >= 0.5:
                        if 0 <= center_motion_id < len(hand_center_history_classifier_labels):
                            motion_text = hand_center_history_classifier_labels[center_motion_id]
                        else:
                            motion_text = "Unknown"
                    else:
                        motion_text = "Unknown"

                    current_motion_score = center_motion_score   
                
                # Command engine: pose + motion
                # ------------------------------
                # Build a frame-level candidate every frame while ACTIVE
                frame_candidate = make_command_candidate(
                    pose_text=hand_sign_text,
                    motion_text=motion_text,
                    motion_source=motion_source,
                    pose_score=max_prob,
                    motion_score=current_motion_score,
                    quality_metrics=quality_metrics,
                    rule_map=command_engine.rule_map,
                )

                # =====================================================
                # Command gate
                # =====================================================
                if command_state == "LOCKED":
                    latest_command_event = None
                    command_text = ""

                    # During lock, do not let return motion create new commands
                    if timestamp_ms >= command_locked_until_ms:
                        if pose_ready:
                            neutral_frames += 1
                        else:
                            neutral_frames = 0

                        if neutral_frames >= REARM_NEUTRAL_FRAMES:
                            command_state = "ACTIVE"
                            neutral_frames = 0
                            data_command_window.clear()
                            clear_motion_buffers(point_history, hand_center_history)
                else:
                    # Live command: only for preview / debug
                    latest_command_event = command_engine.update(
                        pose_text=hand_sign_text,
                        pose_score=max_prob,
                        motion_text=motion_text,
                        motion_score=current_motion_score,
                        motion_source=motion_source,
                        quality_metrics=quality_metrics,
                        timestamp_ms=timestamp_ms,
                    )

                    if latest_command_event is not None:
                        latest_command_text = latest_command_event.command
                        print("COMMAND EVENT:", latest_command_event)

                    command_text = latest_command_text

                    # Data command window must be fed from frame candidates, not from emitted events
                    data_command_window.append(frame_candidate)

                    confirmed = confirm_data_command(
                        data_command_window,
                        ratio_th=0.80,
                        min_valid=8,
                        pose_score_th=0.35,
                        motion_score_th=0.50,
                        quality_th=55.0,
                    )

                    if confirmed is not None:
                        server_payload = build_signed_server_payload(confirmed, server_timestamp_ms)
                        server_result = post_command_to_server(server_payload)
                        data_command_event = {
                            **confirmed,
                            **server_payload,
                            "server_result" : server_result,
                        }
                        
                        data_command_text = confirmed["command"]
                        data_command_display = DATA_COMMAND_DISPLAY_FRAMES

                        data_command_log.append(data_command_event)
                        print("DATA COMMAND:", data_command_event)
                        
                        # Save to local session file
                        save_data_command(data_command_event)

                        # Freeze everything after a confirmed command
                        command_state = "LOCKED"
                        command_locked_until_ms = timestamp_ms + COMMAND_LOCK_MS
                        neutral_frames = 0

                        # Clear old motion so the return movement does not reuse the old trail
                        clear_motion_buffers(point_history, hand_center_history)
                        data_command_window.clear()

                        # Clear live command so it does not linger
                        latest_command_text = ""
                        command_text = ""

                # Data command display hold
                if data_command_display > 0:
                    data_command_display -= 1
                else:
                    data_command_text = ""
            # Drawing 
            debug_image = draw_landmarks_task(debug_image, landmark_list)
            debug_image = draw_motion_history(debug_image, point_history, (152, 251, 152), thickness=2)
            debug_image = draw_motion_history(debug_image, hand_center_history, (255, 200, 0), thickness=2)
            debug_image = draw_connections_task(debug_image, landmark_list)
            debug_image = draw_bounding_rect_task(debug_image, brect)
            debug_image = draw_gesture_info(
                debug_image,
                brect,
                hand_sign_text,
                motion_text,
                motion_source=motion_source,
                command_text=command_text,
                data_command_text = data_command_text,
            )
    else:
        point_history.append([0, 0])
        hand_center_history.append([0, 0])
        latest_command_text = ""        
    # Show
    debug_image = draw_info(debug_image, fps, current_mode, current_number, number_buffer)
    debug_image = draw_quality_overlay(debug_image, quality_metrics)
    cv2.imshow("Hand Gesture Recognition",debug_image)
    
cap.release()
cv2.destroyAllWindows()        