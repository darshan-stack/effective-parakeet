#!/usr/bin/env python3
"""YOLO Inference Demo for GPUGuard.

Runs YOLO object detection on GPU to generate load for GPUGuard monitoring.
"""
import argparse
import time
import sys
from pathlib import Path

import cv2
import numpy as np
import torch


def main():
    parser = argparse.ArgumentParser(description="YOLO Inference Demo for GPUGuard")
    parser.add_argument("--model", default="yolov8n", help="YOLO model (yolov8n, yolov8s, yolov8m, yolov8l, yolov8x)")
    parser.add_argument("--device", default="cuda", choices=["cuda", "cpu"], help="Inference device")
    parser.add_argument("--batch", type=int, default=4, help="Batch size")
    parser.add_argument("--source", default="0", help="Video source (camera index, video file, or image directory)")
    parser.add_argument("--duration", type=int, default=0, help="Run duration in seconds (0 = infinite)")
    parser.add_argument("--imgsz", type=int, default=640, help="Inference image size")
    parser.add_argument("--conf", type=float, default=0.25, help="Confidence threshold")
    parser.add_argument("--benchmark", action="store_true", help="Run benchmark mode")
    args = parser.parse_args()

    # Check CUDA availability
    if args.device == "cuda" and not torch.cuda.is_available():
        print("CUDA not available, falling back to CPU")
        args.device = "cpu"

    print(f"Loading {args.model} on {args.device}...")

    try:
        from ultralytics import YOLO
    except ImportError:
        print("Installing ultralytics...")
        import subprocess
        subprocess.check_call([sys.executable, "-m", "pip", "install", "ultralytics"])
        from ultralytics import YOLO

    # Load model
    model = YOLO(f"{args.model}.pt")
    model.to(args.device)

    # Warmup
    print("Warming up...")
    dummy = np.random.randint(0, 255, (args.imgsz, args.imgsz, 3), dtype=np.uint8)
    for _ in range(5):
        _ = model(dummy, verbose=False)

    print(f"Starting inference (batch={args.batch})...")

    # Open video source
    if args.source.isdigit():
        cap = cv2.VideoCapture(int(args.source))
    else:
        cap = cv2.VideoCapture(args.source)

    if not cap.isOpened():
        print(f"Error: Could not open video source {args.source}")
        return 1

    # Set resolution
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)

    frame_count = 0
    start_time = time.time()
    latencies = []

    try:
        while True:
            ret, frame = cap.read()
            if not ret:
                # Loop video or use synthetic frames
                cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                continue

            # Prepare batch
            frames = []
            for _ in range(args.batch):
                frames.append(cv2.resize(frame, (args.imgsz, args.imgsz)))

            # Inference
            infer_start = time.perf_counter()
            results = model(frames, verbose=False, conf=args.conf)
            infer_time = (time.perf_counter() - infer_start) * 1000  # ms
            latencies.append(infer_time)

            frame_count += 1

            # Print stats every 30 frames
            if frame_count % 30 == 0:
                avg_latency = sum(latencies[-30:]) / min(30, len(latencies))
                fps = frame_count / (time.time() - start_time)
                print(f"Frame {frame_count}: {avg_latency:.1f}ms avg latency, {fps:.1f} FPS, "
                      f"GPU mem: {torch.cuda.memory_allocated()/1e9:.1f}GB" if args.device == "cuda" else "")

            # Check duration
            if args.duration > 0 and time.time() - start_time > args.duration:
                break

    except KeyboardInterrupt:
        print("\nStopping...")
    finally:
        cap.release()

    # Final stats
    if latencies:
        print(f"\n=== Benchmark Results ===")
        print(f"Total frames: {frame_count}")
        print(f"Avg latency: {np.mean(latencies):.1f}ms")
        print(f"P50 latency: {np.percentile(latencies, 50):.1f}ms")
        print(f"P95 latency: {np.percentile(latencies, 95):.1f}ms")
        print(f"P99 latency: {np.percentile(latencies, 99):.1f}ms")
        print(f"Max latency: {np.max(latencies):.1f}ms")
        print(f"Throughput: {frame_count / (time.time() - start_time):.1f} FPS")
        if args.device == "cuda":
            print(f"Peak GPU memory: {torch.cuda.max_memory_allocated()/1e9:.1f}GB")

    return 0


if __name__ == "__main__":
    sys.exit(main())