<div align="center">

# ✋ Intelligent Hand Gesture Recognition & IoT Control System

### AI-powered Hand Gesture Recognition Pipeline with FastAPI, PostgreSQL, MQTT and ESP32 Devices

[![Python](https://img.shields.io/badge/Python-3.13-blue.svg)]()
[![FastAPI](https://img.shields.io/badge/FastAPI-Backend-009688.svg)]()
[![MediaPipe](https://img.shields.io/badge/MediaPipe-Tasks-orange.svg)]()
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-Database-blue.svg)]()
[![MQTT](https://img.shields.io/badge/MQTT-IoT-success.svg)]()
[![ESP32](https://img.shields.io/badge/ESP32-Firmware-red.svg)]()
[![TLS](https://img.shields.io/badge/TLS-Secured-green.svg)]()
[![License](https://img.shields.io/badge/License-MIT-lightgrey.svg)]()

</div>

---

# 📖 Overview

This project presents a complete **AI-powered hand gesture recognition and IoT control platform** capable of recognizing static hand poses and dynamic hand motions in real time and translating them into secure commands for smart devices.

Unlike traditional gesture recognition projects that stop after image classification, this system implements an entire end-to-end software stack including:

- Computer Vision
- Artificial Intelligence
- Command Processing
- Secure REST API
- PostgreSQL Database
- MQTT Communication
- IoT Device Firmware
- Device Monitoring
- Web Dashboard

The platform enables users to control multiple IoT devices using natural hand interactions while maintaining authentication, message integrity, replay protection, encrypted communication, and real-time monitoring.

---

# ✨ Features

## Computer Vision

- Real-time hand tracking using MediaPipe Tasks
- 21 hand landmark extraction
- Landmark normalization
- Bounding rectangle calculation
- Frame quality evaluation
- Gesture confidence estimation
- Motion trajectory tracking

---

## Artificial Intelligence

- Static gesture classification
- Dynamic motion classification
- Command voting mechanism
- Confidence filtering
- Motion history processing
- Gesture history processing

---

## Command Engine

- Pose + Motion combination
- Rule-based command generation
- Duplicate command prevention
- Gesture cooldown
- Motion cooldown
- Command confirmation
- Quality-aware filtering

---

## Backend

- FastAPI REST API
- JWT Authentication
- HMAC Signature Verification
- Replay Attack Protection
- PostgreSQL Integration
- SQLAlchemy ORM
- Device Management
- Action Management
- Gesture Mapping

---

## IoT Communication

- MQTT Broker
- TLS Encryption
- Device Authentication
- Command Acknowledgment
- Device Status Monitoring
- Telemetry Collection
- Automatic Reconnection
- Last Will and Testament (LWT)

---

## Monitoring

- Command History
- Device Status
- Broker Status
- WiFi Signal Monitoring
- Uptime Monitoring
- Security Validation
- Event Logging
- Administrative Dashboard

---

# 🎯 Project Goals

The main objective of this project is to transform human hand movements into secure and reliable IoT commands.

The project focuses on solving several practical challenges simultaneously:

- Robust hand recognition
- False command reduction
- Secure communication
- Device authentication
- Reliable command delivery
- Scalable architecture
- Easy device management

Instead of creating a simple gesture classifier, the project implements an extensible architecture that separates gesture recognition, command generation, backend routing, and IoT execution into independent modules.

---

# 🏗 High-Level Architecture

```text
                     Webcam
                        │
                        ▼
             MediaPipe Hand Landmarker
                        │
                        ▼
              Landmark Normalization
                        │
        ┌───────────────┴───────────────┐
        ▼                               ▼
 Static Gesture Classifier      Motion Classifier
        │                               │
        └───────────────┬───────────────┘
                        ▼
                 Command Engine
                        │
                        ▼
               Secure HTTPS Request
                        │
                        ▼
                 FastAPI Backend
                        │
                        ▼
                PostgreSQL Database
                        │
                        ▼
                  MQTT Broker (TLS)
                        │
        ┌───────────────┴───────────────┐
        ▼                               ▼
      ESP32 #1                      ESP32 #2
        │                               │
        ▼                               ▼
     Execute Action               Execute Action
        │                               │
        └───────────────┬───────────────┘
                        ▼
             Acknowledgment + Telemetry
                        │
                        ▼
                    FastAPI Server
                        │
                        ▼
                  Web Dashboard
```

---

# 🚀 Key Technologies

| Category | Technologies |
|-----------|-------------|
| Programming Language | Python, C++ |
| Computer Vision | OpenCV |
| Hand Tracking | MediaPipe Tasks |
| AI Models | TensorFlow Lite |
| Backend | FastAPI |
| Database | PostgreSQL |
| ORM | SQLAlchemy |
| Authentication | JWT |
| Security | HMAC, TLS, HTTPS |
| IoT Communication | MQTT |
| Firmware | ESP32 |
| Reverse Proxy | Caddy |
| DNS | Cloudflare |
| Dashboard | React |

---

# 📂 Repository Structure

```
Hand_gesture_recognition/

├── AI/
│   ├── Gesture Classification
│   ├── Motion Classification
│   ├── Command Engine
│   └── Frame Quality Analyzer
│
├── Server/
│   ├── FastAPI
│   ├── Database
│   ├── Authentication
│   ├── MQTT Service
│   └── REST API
│
├── Firmware/
│   ├── ESP32
│   ├── MQTT Client
│   └── Device Actions
│
├── Dashboard/
│   ├── Device Management
│   ├── Command History
│   └── Monitoring
│
└── Documentation
```

---

# 🌟 System Highlights

✔ Real-Time AI Gesture Recognition

✔ Secure HTTPS Communication

✔ MQTT over TLS

✔ JWT Authentication

✔ HMAC Signed Commands

✔ Replay Attack Protection

✔ Device Authentication

✔ PostgreSQL Logging

✔ Telemetry Collection

✔ Web Monitoring Dashboard

✔ Modular Architecture

✔ Easily Expandable

# 🧠 AI Recognition Pipeline

The AI pipeline is responsible for transforming raw webcam frames into reliable and meaningful commands. Rather than relying solely on image classification, the system combines computer vision, preprocessing, machine learning, confidence estimation, motion analysis, and quality assessment to minimize false detections while maintaining real-time performance.

The complete recognition pipeline is illustrated below.

```text
Camera Frame
      │
      ▼
Frame Quality Analyzer
      │
      ▼
MediaPipe Hand Landmarker
      │
      ▼
21 Hand Landmarks
      │
      ▼
Landmark Preprocessing
      │
      ├───────────────► Gesture Classifier
      │
      └───────────────► Motion History
                              │
                              ▼
                     Motion Classifier
                              │
                              ▼
                      Command Engine
                              │
                              ▼
                    Confirmed Command
```

---

# ✋ Hand Landmark Detection

The first stage of the pipeline performs real-time hand detection using **MediaPipe Tasks Hand Landmarker**.

Instead of classifying the entire image, MediaPipe estimates the position of **21 anatomical landmarks** representing fingers, joints, and the palm.

These landmarks provide a compact mathematical representation of the hand that is independent of image color or background, making them highly suitable for machine learning.

For each detected hand, MediaPipe returns:

- 21 normalized landmark coordinates
- Handedness (left/right)
- Detection confidence
- Tracking confidence

Because only landmark coordinates are used in later stages, the AI models remain lightweight and significantly faster than image-based neural networks.

---

# 📦 Bounding Rectangle Extraction

Before visualization and preprocessing, the system computes a **bounding rectangle** around the detected hand.

The bounding rectangle is calculated by finding the minimum and maximum x/y coordinates among all detected landmarks.

This rectangle is used for several purposes:

- Visualizing the detected hand
- Displaying classification results
- Defining the hand region
- Providing user feedback

Although the rectangle itself is **not used directly by the classifiers**, it improves interaction by clearly indicating the detected hand area.

---

# 📍 Landmark Coordinate Extraction

After MediaPipe detects the hand, the normalized landmark coordinates are converted into pixel coordinates relative to the current camera frame.

Each landmark is represented by:

- x coordinate
- y coordinate

These pixel coordinates simplify visualization and become the input for the preprocessing stage.

---

# ⚙ Landmark Preprocessing

Raw landmark coordinates cannot be directly used for machine learning because they depend on the hand's position inside the camera frame.

The preprocessing stage transforms the landmarks into a position-independent representation.

The following operations are applied:

## Relative Coordinate Conversion

The wrist landmark is selected as the reference point.

Every other landmark is translated relative to the wrist position.

This removes dependence on where the hand appears inside the image.

---

## Scale Normalization

After translation, all coordinates are divided by the largest absolute coordinate value.

This ensures that every sample has approximately the same numerical range regardless of:

- Distance from the camera
- Hand size
- Image resolution

The resulting feature vector describes only the hand geometry rather than its absolute location.

---

## Feature Vector Generation

Finally, the normalized coordinates are flattened into a one-dimensional feature vector.

This vector becomes the input of the static gesture classifier.

---

# 🤖 Static Gesture Classification

The static gesture classifier predicts the current hand pose using the normalized landmark vector.

Examples of supported poses include:

- Open Palm
- Fist
- Point
- OK
- Three
- Four
- Five

The classifier produces:

- predicted gesture label
- confidence score

Low-confidence predictions are rejected to reduce false positives.

Only stable predictions are forwarded to the next stage.

---

# 📈 Motion Tracking

Static gestures alone cannot distinguish movements such as swiping or drawing circles.

To recognize dynamic motions, the system continuously stores landmark history across multiple frames.

Instead of classifying a single frame, motion recognition analyzes temporal movement.

Two independent motion tracking strategies are implemented.

---

## Fingertip Motion Tracking

For pointing gestures, the trajectory of the index fingertip is recorded.

This enables recognition of motions such as:

- Swipe Left
- Swipe Right
- Swipe Up
- Swipe Down
- Clockwise Circle
- Counter-Clockwise Circle

Because only pointing gestures use fingertip trajectories, accidental finger movements during other poses are ignored.

---

## Hand Center Motion Tracking

Some gestures require movement of the entire hand instead of a single finger.

For these cases, the geometric center of the detected hand is calculated for every frame.

The sequence of hand centers forms another motion history.

This allows recognition of whole-hand movements independently of finger articulation.

---

# 🔄 Motion Preprocessing

Motion history cannot be directly classified because its coordinates still depend on the camera position.

The preprocessing stage performs operations similar to landmark normalization.

These include:

- Relative coordinate conversion
- Scale normalization
- Temporal flattening

The processed trajectory becomes a compact feature vector suitable for machine learning.

---

# 🎯 Motion Classification

The motion classifier analyzes the processed trajectory and predicts the performed movement.

Each prediction includes:

- motion label
- confidence score

Only sufficiently confident predictions are considered valid.

Like gesture recognition, motion classification also uses confidence thresholds to reduce unreliable detections.

---

# 📷 Frame Quality Analyzer

Reliable gesture recognition depends heavily on image quality.

Instead of assuming every frame is suitable for inference, the system evaluates each captured frame before accepting classification results.

Several image characteristics are analyzed simultaneously.

### Brightness

Average frame intensity is measured to detect underexposed or overexposed images.

---

### Contrast

Image contrast is estimated to determine whether sufficient visual information is present.

Very low contrast usually indicates poor lighting conditions.

---

### Sharpness

Sharpness is estimated using the variance of the Laplacian operator.

Blurred images generally produce lower landmark accuracy.

---

### Motion Blur

Rapid camera or hand movement introduces blur.

The analyzer detects excessive blur and reduces the quality score accordingly.

---

### Noise Estimation

Image noise is estimated to detect unstable camera input caused by poor lighting or sensor artifacts.

---

### Overall Quality Score

The measured characteristics are combined into a single quality score.

This score represents the overall reliability of the current frame.

The command engine later uses this value to reject commands produced from low-quality frames.

---

# 🎮 Command Engine

The Command Engine combines the outputs of all previous stages into meaningful user commands.

Instead of immediately executing every classifier prediction, multiple validation stages are performed.

The engine receives:

- Gesture prediction
- Gesture confidence
- Motion prediction
- Motion confidence
- Motion source
- Frame quality score

It then applies several decision rules before generating a confirmed command.

These include:

- Confidence threshold verification
- Gesture stability
- Motion stability
- Voting over recent predictions
- Cooldown management
- Duplicate prevention
- Rule matching

Only after all validation conditions are satisfied does the engine generate a confirmed command.

The confirmed command is then securely transmitted to the backend server through HTTPS for authentication, routing, and execution.
