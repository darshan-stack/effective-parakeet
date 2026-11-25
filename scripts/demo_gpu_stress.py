#!/usr/bin/env python3
"""GPU Stress Test for GPUGuard.

Generates controlled GPU load to test thermal throttling, VRAM pressure, etc.
"""
import argparse
import time
import sys
import threading
from typing import List

import torch
import torch.nn as nn


class StressModel(nn.Module):
    """Large model for GPU stress testing."""

    def __init__(self, size: int = 8192, layers: int = 10):
        super().__init__()
        self.layers = nn.ModuleList()
        for i in range(layers):
            self.layers.append(nn.Linear(size, size))
            self.layers.append(nn.ReLU())
        self.output = nn.Linear(size, 1000)

    def forward(self, x):
        for layer in self.layers:
            x = layer(x)
        return self.output(x)


def stress_compute(device: str, intensity: float, duration: int, stop_event: threading.Event):
    """Stress GPU compute."""
    print(f"Starting compute stress on {device} (intensity: {intensity})...")

    # Create model
    size = int(8192 * intensity)
    model = StressModel(size=size, layers=int(10 * intensity)).to(device)
    model.train()

    # Create optimizer
    optimizer = torch.optim.SGD(model.parameters(), lr=0.01)

    # Input data
    batch_size = int(256 * intensity)
    x = torch.randn(batch_size, size, device=device)
    y = torch.randint(0, 1000, (batch_size,), device=device)

    criterion = nn.CrossEntropyLoss()

    start = time.time()
    iterations = 0

    while not stop_event.is_set() and (duration == 0 or time.time() - start < duration):
        optimizer.zero_grad()
        out = model(x)
        loss = criterion(out, y)
        loss.backward()
        optimizer.step()

        iterations += 1

        if iterations % 100 == 0:
            elapsed = time.time() - start
            print(f"  Compute: {iterations} iters, {iterations/elapsed:.1f} iters/s, "
                  f"loss: {loss.item():.4f}")

    print(f"Compute stress stopped after {iterations} iterations")


def stress_memory(device: str, target_gb: float, duration: int, stop_event: threading.Event):
    """Stress GPU memory (VRAM)."""
    print(f"Starting memory stress on {device} (target: {target_gb}GB)...")

    tensors: List[torch.Tensor] = []
    allocated = 0.0
    chunk_size = 512 * 1024 * 1024  # 512MB chunks

    try:
        while not stop_event.is_set() and allocated < target_gb:
            try:
                t = torch.randn(chunk_size // 4, device=device, dtype=torch.float32)
                tensors.append(t)
                allocated += chunk_size / 1e9
                print(f"  Allocated: {allocated:.2f}GB")
                time.sleep(0.5)
            except RuntimeError as e:
                if "out of memory" in str(e):
                    print(f"  OOM at {allocated:.2f}GB")
                    break
                raise

        # Hold memory
        start = time.time()
        while not stop_event.is_set() and (duration == 0 or time.time() - start < duration):
            # Touch memory to prevent optimization
            for t in tensors:
                _ = t.sum()
            time.sleep(1.0)

    finally:
        # Cleanup
        del tensors
        torch.cuda.empty_cache()
        print("Memory stress stopped")


def stress_bandwidth(device: str, duration: int, stop_event: threading.Event):
    """Stress GPU memory bandwidth."""
    print(f"Starting bandwidth stress on {device}...")

    # Large tensor copies
    size = 2 * 1024 * 1024 * 1024 // 4  # 2GB float32
    src = torch.randn(size, device=device, dtype=torch.float32)
    dst = torch.empty_like(src)

    start = time.time()
    copies = 0

    while not stop_event.is_set() and (duration == 0 or time.time() - start < duration):
        dst.copy_(src)
        copies += 1

        if copies % 10 == 0:
            elapsed = time.time() - start
            gb_copied = copies * 2
            print(f"  Bandwidth: {gb_copied/elapsed:.1f} GB/s")

    del src, dst
    torch.cuda.empty_cache()
    print("Bandwidth stress stopped")


def main():
    parser = argparse.ArgumentParser(description="GPU Stress Test for GPUGuard")
    parser.add_argument("--device", default="cuda", choices=["cuda", "cpu"], help="Device to stress")
    parser.add_argument("--compute", type=float, default=1.0, help="Compute intensity (0-2)")
    parser.add_argument("--memory", type=float, default=0, help="Target VRAM usage in GB (0 = auto)")
    parser.add_argument("--bandwidth", action="store_true", help="Stress memory bandwidth")
    parser.add_argument("--duration", type=int, default=60, help="Duration in seconds (0 = infinite)")
    parser.add_argument("--all", action="store_true", help="Run all stress tests")
    args = parser.parse_args()

    if args.device == "cuda" and not torch.cuda.is_available():
        print("CUDA not available, using CPU")
        args.device = "cpu"

    print(f"GPU Stress Test on {args.device}")
    print(f"Compute intensity: {args.compute}")
    print(f"Memory target: {args.memory}GB" if args.memory > 0 else "Memory: auto")
    print(f"Bandwidth test: {args.bandwidth}")
    print(f"Duration: {args.duration}s" if args.duration > 0 else "Duration: infinite")

    if args.all:
        args.compute = 1.0
        args.memory = 0  # auto
        args.bandwidth = True

    # Auto-detect memory target
    if args.device == "cuda" and args.memory == 0:
        total_mem = torch.cuda.get_device_properties(0).total_memory / 1e9
        args.memory = total_mem * 0.85  # 85% of VRAM
        print(f"Auto memory target: {args.memory:.1f}GB (85% of {total_mem:.1f}GB)")

    stop_event = threading.Event()
    threads = []

    try:
        # Start compute stress
        if args.compute > 0:
            t = threading.Thread(
                target=stress_compute,
                args=(args.device, args.compute, args.duration, stop_event),
                daemon=True,
            )
            t.start()
            threads.append(t)

        # Start memory stress
        if args.memory > 0:
            t = threading.Thread(
                target=stress_memory,
                args=(args.device, args.memory, args.duration, stop_event),
                daemon=True,
            )
            t.start()
            threads.append(t)

        # Start bandwidth stress
        if args.bandwidth:
            t = threading.Thread(
                target=stress_bandwidth,
                args=(args.device, args.duration, stop_event),
                daemon=True,
            )
            t.start()
            threads.append(t)

        # Wait
        if args.duration > 0:
            time.sleep(args.duration)
        else:
            print("Press Ctrl+C to stop...")
            while True:
                time.sleep(1)

    except KeyboardInterrupt:
        print("\nStopping...")
    finally:
        stop_event.set()
        for t in threads:
            t.join(timeout=5)

    print("Stress test complete")


if __name__ == "__main__":
    main()