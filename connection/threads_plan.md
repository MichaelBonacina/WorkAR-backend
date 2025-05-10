# Core idea—turn the app into a tiny pipeline

```
WebSocket ⇢ Ingest  ⇢ ① Task-State worker (slow, serial)
                   \
                    ↘ ② Object-Loc worker(s) (fast, parallel OK)
                              \
                               ↘ Outgoing-msg dispatcher ⇢ WebSocket
```

Ingest is the only thing that touches the network and the disk.

Each worker owns its own asyncio/Thread queue so you can throttle or
drop frames independently.

The dispatcher is just another coroutine that reads a queue of
"things to send" and await websocket.send()—so every heavy call happens
off the event-loop thread.

## 2. Concurrency model

| Piece | Runs on | Max concurrency | Why |
|-------|---------|-----------------|-----|
| WebSocket I/O loop | asyncio | 1 per client | Non-blocking network I/O |
| Frame-ingest coroutine | asyncio | 1 per client | Writes file + queues work |
| Task-State worker | ThreadPoolExecutor(max_workers=1) | Exactly 1 | Guarantees processFrame can't overlap |
| Object-Loc worker | ThreadPoolExecutor(max_workers=N) | 1 – 2 (GPU permitting) | addObjectCoordinates can overlap across frames |
| Outgoing dispatcher | asyncio | 1 per client | Ordered, back-pressure aware |

## 3. Shared state & thread-safety

| Item | Scope | Access guard | Notes |
|------|-------|--------------|-------|
| VideoState | All workers | threading.Lock around add_image() & getters |  |
| TaskState | Read by Loc, written by State worker | threading.Lock or an asyncio.Lock plus run_in_executor |  |
| Model objects (OWLv2, etc.) | Per process | If GPU → serialize access with asyncio.Semaphore(1) |  |

Keep the locks tiny—wrap only the mutation/read, not the whole
algorithm call.

## 4. Queues & back-pressure

| Queue | Type | Size | Producer | Consumer |
|-------|------|------|----------|----------|
| detection_q | asyncio.Queue(1) | 1 | Ingest coroutine (only if empty) | Task-State worker |
| localization_q | asyncio.Queue(5) | Drop-new policy | Ingest coroutine (always) | Object-Loc worker(s) |
| send_q | asyncio.Queue() | Unbounded* | Both workers | Dispatcher |

*You can still cap send_q if you fear client slowness.

A size-1 detection_q means you always process the newest frame only for
state detection—greatly cutting wasted effort when the user moves quickly.

## 5. Data objects that travel through the pipeline

```python
@dataclass
class FramePacket:
    path: Path
    timestamp: float
    seq: int          # ever-increasing
```

```python
@dataclass
class LocResult:
    instruction_json: str     # already serialized
```

```python
@dataclass
class StateResult:
    status: str               # executing_task | completed_task | derailed | error
    new_step: Optional[Step]  # only for completed_task
```

Everything that goes onto a queue is an immutable dataclass.
No shared mutable blobs = no accidental data races.

## 6. Worker sketches (pseudo-code)

### 6.1 Task-State worker

```python
async def state_worker():
    while True:
        frame = await detection_q.get()
        try:
            status = await asyncio.to_thread(
                processFrame.processFrame,
                current_task_state, video_state
            )
            async with taskstate_lock:
                # mutate TaskState in place
            await send_q.put(StateResult(status, new_step))
        finally:
            detection_q.task_done()
```

### 6.2 Object-Loc worker

```python
async def loc_worker(worker_id):
    while True:
        frame = await localization_q.get()
        step_snapshot = task_state_snapshot()   # read-only
        instr = await asyncio.to_thread(
            build_instruction_with_objects,
            frame.path, step_snapshot
        )
        await send_q.put(LocResult(instr.to_json()))
        localization_q.task_done()
```

### 6.3 Dispatcher

```python
async def dispatcher(websocket):
    while True:
        msg = await send_q.get()
        await websocket.send(msg.json_string)  # ordered, back-pressure aware
        send_q.task_done()
```

## 7. Frame-ingest coroutine (inside your new_frame_handler)

1. Save image → frame_path.
2. video_state.add_image(frame_path) (protected by lock).
3. localization_q.put_nowait(FramePacket(...)).
4. if detection_q.empty(): detection_q.put_nowait(FramePacket(...)).

No more global is_processing_frame; the queues provide the same guarantee
non-blockingly.

## 8. Error handling & shutdown

Wrap every worker loop in try/except Exception → push an error
result onto send_q so the client sees something.

On WebSocket close:

Cancel the ingest coroutine → let queues drain → await queue.join()
→ cancel workers.

## 9. Gotchas & tuning tips

| Issue | Mitigation |
|-------|------------|
| GPU contention (two threads call ONNX/torch) | Guard model inference with asyncio.Semaphore(1) or run Loc workers in a separate process. |
| Detection lag still too high | Drop even more frames (keep newest only) or stream a down-scaled copy to state detection. |
| Memory leak from saved PNGs | When a frame has been processed by both workers, schedule it for deletion. Keep a collections.Counter keyed by path. |

## Next steps

1. Lift the pieces above into their own modules (pipeline.py, workers.py).
2. Add the queues + locks to your global state singletons.
3. Replace the is_processing_frame block in new_frame_handler
   with the ingest logic described.
4. Unit-test the pipeline with dummy time.sleep functions to verify
   ordering & throughput before plugging in real models.

Once the skeleton is in place you'll see latency drop to ≈1 s (Loc) and
≈3–4 s (State) without blocking each other, and your WebSocket will never
timeout waiting for a heavy call again.