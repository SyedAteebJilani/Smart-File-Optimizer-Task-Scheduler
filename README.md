# Smart File Optimizer & Task Scheduler

A Windows-only PyQt6 desktop application that demonstrates operating-system concepts through concurrent file scanning and duplicate detection.

## Run

```powershell
python -m pip install -r requirements.txt
python .\main.py
```

The application stores SQLite data under `%LOCALAPPDATA%\SmartFileOptimizer\smart_optimizer.db`.

## Architecture

- `presentation`: PyQt6 widgets, signals, and visual rendering only.
- `application`: orchestration, use cases, event routing, metrics snapshots.
- `domain`: entities, value objects, enums, interfaces, pure risk and learning models.
- `infrastructure`: filesystem traversal, hashing, scheduler/thread pool, SQLite, logging.

The worker pool uses `threading`, `heapq`, locks, semaphores, and a producer-consumer queue. The GUI receives updates only through Qt signals emitted by the application event bridge.

