<div align="center">

# 🚀 Smart File Optimizer & Task Scheduler

### Intelligent Duplicate Detection • Safe Disk Recovery • Multithreaded Scheduling

A Windows-native utility engineered for efficient duplicate file detection and disk space recovery. The system combines multithreaded file processing, optimized SHA-256 hashing pipelines, and a custom scheduling layer to deliver high-performance scanning while maintaining system responsiveness.

Designed with scalability and safety in mind, the application minimizes unnecessary disk I/O, prevents accidental data loss, and provides actionable analytics for storage optimization.

![Python](https://img.shields.io/badge/Python-3776AB?style=for-the-badge&logo=python&logoColor=white)
![CustomTkinter](https://img.shields.io/badge/CustomTkinter-20232A?style=for-the-badge)
![Threading](https://img.shields.io/badge/Multithreading-FF6B35?style=for-the-badge)
![SHA--256](https://img.shields.io/badge/SHA--256-000000?style=for-the-badge)
![Windows](https://img.shields.io/badge/Windows-Native-0078D6?style=for-the-badge&logo=windows)

</div>

---

## Overview

Smart File Optimizer & Task Scheduler is a desktop utility built to automate duplicate file discovery and reclaim wasted storage space without compromising system stability.

Unlike conventional duplicate cleaners that rely on naive file comparisons, this project introduces a layered hashing pipeline, a priority-aware scheduling engine, and a controlled worker pool architecture that balances performance with resource utilization.

The application focuses on three engineering goals:

- Efficient duplicate detection.
- Safe storage recovery.
- Controlled concurrent execution.

---

## Key Features

### ⚡ Multithreaded Processing Engine

- Worker-pool architecture optimized for disk-intensive workloads.
- Configurable concurrency model:
  - CLI mode: up to **3 workers**.
  - GUI mode: up to **7 workers**.
- Prevents CPU and storage bottlenecks during large scans.

---

### 🔐 Dual-Layer SHA-256 Hashing Pipeline

To minimize unnecessary disk reads, the system uses a two-stage hashing strategy:

#### Stage 1 — Partial Hashing

- Computes SHA-256 on the first **64 KB** of each file.
- Quickly filters out non-duplicate candidates.

#### Stage 2 — Full Verification

- Executes complete SHA-256 hashing only when partial hashes match.
- Reduces disk I/O and improves overall throughput.

---

### 🧠 Aging Priority Scheduler

The application wraps Python's built-in `heapq` module inside a custom `AgingPriorityScheduler`.

The scheduler combines:

- Priority-based execution.
- Arrival-time tracking.
- First Come First Serve behavior for equally prioritized tasks.

Jobs are submitted by the file scanner and consumed by worker threads through a centralized scheduling layer.

This design:

- Prevents resource starvation.
- Reduces priority inversion risks.
- Improves scheduling fairness.

---

### 🛡️ Safe Deletion Workflow

Duplicate files are never permanently deleted.

Instead, the system integrates with the Windows Recycle Bin using:

```python
send2trash
```

This approach ensures:

- Reversible deletion.
- Safer cleanup operations.
- Reduced risk of accidental data loss.

---

### 📊 Risk Analysis Engine

The built-in `RiskScoringEngine` evaluates whether a file may be critical to system stability.

Examples include:

- `.dll`
- `.sys`
- Protected directories
- Operating system dependencies

This additional validation layer helps users avoid removing sensitive files.

---

### 📈 Storage Analytics

The application generates insights including:

- Reclaimable disk space.
- Duplicate density per directory.
- Scan statistics.
- Duplicate distribution.

---

## Architecture

```text
┌─────────────────────┐
│  FileSystemScanner  │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│ AgingPriorityQueue  │
│   (heapq Wrapper)   │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│    Worker Threads   │
│   (3–7 Consumers)   │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│ Partial SHA-256     │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│ Full SHA-256        │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│ Risk Analysis       │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│ Safe Delete Engine  │
└─────────────────────┘
```

---

## Technology Stack

### Core Technologies

- Python 3
- CustomTkinter
- threading
- queue
- heapq
- hashlib
- send2trash

### Core Concepts

- Producer–Consumer Pattern
- Worker Pool Architecture
- Priority Scheduling
- Concurrent Processing
- Hash-Based Deduplication
- Disk I/O Optimization

---

## Installation

Clone the repository:

```bash
git clone https://github.com/SyedAteebJilani/Smart-File-Optimizer-Task-Scheduler-.git
```

Move into the project directory:

```bash
cd Smart-File-Optimizer-Task-Scheduler-
```

Install dependencies:

```bash
pip install -r requirements.txt
```

Run the application:

```bash
python main.py
```

Alternatively:

```bash
pip install .
```

---

## Repository

🔗 Repository Link:

https://github.com/SyedAteebJilani/Smart-File-Optimizer-Task-Scheduler-

---

## Engineering Focus

This project explores practical applications of:

- Concurrent programming.
- Task scheduling.
- Storage optimization.
- File-system analysis.
- Resource management.
- Safe automation workflows.

---

<div align="center">

Built to explore the intersection of automation, concurrency, and system-level software engineering.

</div>
