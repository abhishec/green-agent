#!/usr/bin/env python3
"""
Run pass@k evaluation for one or all tasks.
Usage: python pass_k_runner.py --task task_01 [--k 8] [--purple-url http://localhost:9010]
       python pass_k_runner.py --all [--k 3]
"""
from __future__ import annotations
import argparse
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "green-agent"))


async def run_task_k_times(task_id: str, k: int, purple_url: str, green_url: str = "http://localhost:9009") -> dict:
    from src.task_manager import run_assessment

    scores = []
    for i in range(k):
        result = await run_assessment(task_id=task_id, purple_agent_url=purple_url, green_agent_url=green_url)
        scores.append(result.score.overall)
        print(f"  {task_id} run {i+1}/{k}: {result.score.overall:.1f}")

    avg = sum(scores) / len(scores) if scores else 0
    pass_count = sum(1 for s in scores if s >= 70)
    all_pass = pass_count == k
    return {
        "task_id": task_id,
        "pass_at_1": round(pass_count / k * 100, 1) if k else 0,
        "avg_score": round(avg, 1),
        "pass_k": all_pass,
        "min_score": round(min(scores), 1) if scores else 0,
        "max_score": round(max(scores), 1) if scores else 0,
        "k": k,
    }


async def run_all(k: int, purple_url: str, green_url: str = "http://localhost:9009"):
    from src.scenarios import SCENARIO_REGISTRY

    tasks = list(SCENARIO_REGISTRY.keys())
    results = []
    for task_id in tasks:
        print(f"\nRunning {task_id} x{k}...")
        r = await run_task_k_times(task_id, k, purple_url, green_url)
        results.append(r)

    print(f"\n{'='*72}")
    print(f"  {'Task':<20} {'pass@1%':>8} {'avg':>6} {'pass^k':>7} {'min':>6} {'max':>6}")
    print(f"  {'-'*62}")
    for r in results:
        pk = "PASS" if r["pass_k"] else "FAIL"
        print(f"  {r['task_id']:<20} {r['pass_at_1']:>7.1f} {r['avg_score']:>6.1f} {pk:>7}  {r['min_score']:>5.1f}  {r['max_score']:>5.1f}")
    overall_pass = sum(1 for r in results if r["pass_k"])
    print(f"  {'-'*62}")
    print(f"  Tasks passing pass^{k}: {overall_pass}/{len(results)}")
    print(f"{'='*72}\n")


def main():
    parser = argparse.ArgumentParser(description="Run pass@k benchmark")
    parser.add_argument("--task", help="Single task ID")
    parser.add_argument("--all", action="store_true", help="Run all tasks")
    parser.add_argument("--k", type=int, default=8)
    parser.add_argument("--purple-url", default="http://localhost:9010")
    parser.add_argument("--green-url", default="http://localhost:9009")
    args = parser.parse_args()

    if args.all:
        asyncio.run(run_all(args.k, args.purple_url, args.green_url))
    elif args.task:
        result = asyncio.run(run_task_k_times(args.task, args.k, args.purple_url, args.green_url))
        print(f"\npass@1={result['pass_at_1']}% avg={result['avg_score']} pass^{args.k}={'PASS' if result['pass_k'] else 'FAIL'}")
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
