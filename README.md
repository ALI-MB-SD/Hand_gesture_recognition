# 🌐 Backend Architecture

The backend acts as the central coordinator of the entire system. While the AI module is responsible for recognizing gestures and motions, the backend authenticates incoming requests, validates command integrity, resolves gesture mappings, records system events, and delivers commands to the appropriate IoT devices.

Instead of directly controlling devices from the computer vision application, all commands pass through the backend, allowing centralized management, monitoring, scalability, and security.

The backend is implemented using **FastAPI**, **PostgreSQL**, and **SQLAlchemy**, providing a modern, asynchronous, and modular architecture.

---

# 🏛 Backend Architecture Overview

```text
                AI Recognition Application
                         │
                 HTTPS + JSON Request
                         │
                         ▼
                  FastAPI REST API
                         │
        ┌────────────────┼────────────────┐
        ▼                ▼                ▼
 Authentication   Command Validation   Database
        │                │                │
        └────────────────┼────────────────┘
                         ▼
                Gesture Resolution
                         │
                         ▼
              Gesture → Action Mapping
                         │
                         ▼
              Action → Device Mapping
                         │
                         ▼
               MQTT Command Publisher
                         │
                         ▼
                    Target Device
```

---

# ⚡ Why FastAPI?

FastAPI was selected because it provides high performance, automatic request validation, asynchronous capabilities, and excellent integration with modern Python libraries.

Its automatic OpenAPI documentation also simplifies API testing and future frontend development.

The backend exposes a collection of REST endpoints responsible for user management, gesture configuration, action creation, device registration, mapping management, command ingestion, monitoring, and administrative operations.

---

# 🗄 Database Architecture

All persistent system data is stored in a PostgreSQL database.

Rather than hardcoding device behaviors into the application, the database stores every configurable relationship inside dedicated tables.

This design allows administrators to modify system behavior without changing any source code.

The database stores:

- Registered users
- Gesture definitions
- Available actions
- Registered IoT devices
- Gesture-to-action mappings
- Action-to-device mappings
- Command history
- Device status logs
- Device telemetry logs
- Broker status logs

As a result, the backend becomes completely data-driven.

---

# 📚 SQLAlchemy ORM

Communication between FastAPI and PostgreSQL is handled through SQLAlchemy ORM.

Instead of writing raw SQL queries throughout the project, each database table is represented by a Python model.

This provides several advantages:

- Improved readability
- Easier maintenance
- Type safety
- Automatic relationship handling
- Database independence

Each API endpoint interacts with these ORM models rather than manually constructing SQL statements.

---

# 👤 User Authentication

Administrative endpoints are protected using JWT authentication.

When a user logs into the system, the backend verifies the supplied credentials by comparing the provided password against the securely hashed password stored in the database.

After successful authentication, the server generates a signed JSON Web Token (JWT).

The client includes this token in the Authorization header of subsequent requests.

Protected endpoints verify the token before allowing access to administrative resources such as:

- Creating gestures
- Registering devices
- Defining actions
- Editing mappings
- Viewing command history

This approach enables stateless authentication without requiring server-side login sessions.

---

# 🔐 Password Security

User passwords are never stored in plaintext.

Instead, passwords are hashed using the Argon2 password hashing algorithm before being saved in the database.

During login, the submitted password is hashed again and compared against the stored hash.

Because only hashes are stored, the original passwords cannot be recovered even if the database contents become exposed.

---

# 🎯 Gesture Definition

The backend does not assume any predefined gestures.

Instead, every supported gesture is registered through the administrative interface.

Each gesture consists of:

- Gesture name
- Static pose
- Motion
- Internal normalized keys
- Enable/disable status

This allows new gestures to be introduced without modifying the recognition software.

---

# ⚙ Action Definition

Actions represent abstract operations that may later be executed by devices.

Examples include:

- LIGHT_ON
- LIGHT_OFF
- FAN_ON
- OPEN_DOOR
- PLAY_MUSIC

Importantly, actions are independent of specific hardware.

The same action may later be assigned to different devices.

---

# 📱 Device Registration

Every IoT device must first be registered in the backend.

During registration, each device receives:

- Unique device identifier
- Device type
- Human-readable name
- Automatically generated API key
- Enable/disable state

The generated API key becomes the device's identity when communicating with the backend.

This prevents unauthorized hardware from interacting with the system.

---

# 🔄 Gesture → Action Mapping

One of the most important architectural decisions is separating gestures from actions.

Rather than embedding application logic inside the AI recognition module, recognized gestures are translated into abstract actions using database mappings.

For example:

```
Gesture:
Open Palm + Swipe Right

↓

Action:
NEXT_SLIDE
```

Changing the system behavior therefore requires only updating database records rather than modifying recognition code.

---

# 🔌 Action → Device Mapping

Actions are then mapped to physical devices.

For example:

```
NEXT_SLIDE

↓

Presentation Controller
```

or

```
LIGHT_ON

↓

Living Room ESP32
```

This second mapping layer completely decouples AI recognition from IoT hardware.

A single action can later be reassigned to different devices without changing either the recognition software or the firmware.

---

# 📥 Command Ingestion Pipeline

After the AI application confirms a command, it sends a secure HTTPS POST request to the backend.

Each request contains:

- Event ID
- Session ID
- Pose
- Motion
- Motion source
- Confidence scores
- Frame quality
- Timestamp
- Nonce
- HMAC signature

The backend validates every field before processing the command.

---

# 🛡 Command Validation

Incoming commands pass through several validation stages.

These include:

1. JWT Authentication

Verifies that the request originates from an authenticated user.

---

2. Replay Window Verification

Checks whether the timestamp falls within the permitted time window.

Old or delayed commands are rejected.

---

3. HMAC Verification

Recalculates the HMAC signature and compares it against the received signature.

If any field has been modified during transmission, validation immediately fails.

---

4. Duplicate Event Detection

Previously processed Event IDs are rejected to prevent accidental duplicate execution.

---

5. Nonce Validation

Every command contains a unique nonce.

If a previously used nonce is detected, the request is treated as a replay attack and rejected.

---

# 🧭 Command Resolution

After passing security validation, the backend determines how the recognized gesture should be handled.

The resolution process consists of two sequential lookup stages:

```
Pose + Motion

↓

Gesture Definition

↓

Mapped Action

↓

Mapped Device
```

If any lookup fails, the command is rejected with an appropriate error response.

---

# 📝 Command Logging

Before being forwarded to the IoT network, every accepted command is permanently stored in PostgreSQL.

Each command record includes:

- User
- Gesture
- Action
- Target device
- Confidence values
- Frame quality
- Timestamp
- Security metadata
- Current execution status

Maintaining a complete command history simplifies debugging, auditing, and performance evaluation.

---

# 📊 Command Lifecycle

Each command progresses through multiple execution stages.

```text
Received

↓

Validated

↓

Stored

↓

Published

↓

Acknowledged

↓

Completed
```

Initially, commands are stored with a **Pending** status.

After successful publication through MQTT, the status changes to **Sent**.

Finally, once the target device confirms execution, the command becomes **Acknowledged (Acked)**.

A background monitoring service continuously checks command timeouts.

Commands that remain in intermediate states beyond predefined time limits are automatically marked as failed, ensuring accurate tracking of unsuccessful deliveries.

---

# 📈 Monitoring Services

The backend continuously records operational events generated by connected devices and internal services.

These include:

- Device online/offline transitions
- WiFi signal strength
- Device uptime
- Broker connection events
- Command history
- Execution acknowledgements

All monitoring information is stored in PostgreSQL and later visualized through the web dashboard.

---

# 🖥 Administrative Dashboard

To simplify system administration, a dedicated web dashboard communicates directly with the FastAPI backend.

The dashboard allows administrators to:

- Register new devices
- Create gesture definitions
- Define actions
- Configure mappings
- View command history
- Monitor device connectivity
- Inspect telemetry data
- Observe broker status

By separating the management interface from the backend logic, the system remains modular and can easily support future extensions such as user roles, analytics, or remote administration.

---

# 🔄 Backend Workflow Summary

The backend serves as the intelligent routing layer between AI recognition and IoT execution.

It authenticates users, validates command authenticity, resolves configurable mappings, records all system events, and forwards verified commands toward the MQTT communication layer.

This modular design keeps recognition, business logic, database management, and device communication independent from one another, making the overall system easier to maintain, scale, and extend.
