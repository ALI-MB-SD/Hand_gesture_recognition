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
