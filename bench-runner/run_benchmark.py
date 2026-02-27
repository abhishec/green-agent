#!/usr/bin/env python3
"""
Run a single benchmark task against the purple agent and display scores.
Usage: python run_benchmark.py --task task_01 [--difficulty none] [--purple-url http://localhost:9010]
Exit 0 if overall >= 70, else 1.
"""
from __future__ import annotations
import argparse
import asyncio
import sys
import uuid

import httpx


async def run(task_id: str, difficulty: str, purple_url: str, green_url: str) -> int:
    session_id = str(uuid.uuid4())

    # Import scenario to get task text + policy
    sys.path.insert(0, str(__import__("pathlib").Path(__file__).parent.parent / "green-agent"))
    from src.scenarios import SCENARIO_REGISTRY
    from src.task_manager import run_assessment

    result = await run_assessment(
        task_id=task_id,
        purple_agent_url=purple_url,
        difficulty=difficulty,
        session_id=session_id,
    )

    scores = result.score.summary()
    print(f"\n{'='*55}")
    print(f"  AgentBench Results — {task_id.upper()}")
    print(f"{'='*55}")
    print(f"  {'Dimension':<22} {'Score':>6}  {'Weight':>7}")
    print(f"  {'-'*42}")
    weights = {"functional": "30%", "policy_compliance": "20%", "escalation": "15%",
               "sequence": "15%", "arithmetic": "10%", "hallucination": "5%", "communication": "5%"}
    for dim, weight in weights.items():
        score = scores.get(dim, 0)
        bar = "█" * int(score / 10) + "░" * (10 - int(score / 10))
        print(f"  {dim:<22} {score:>5.1f}  {weight:>7}  {bar}")
    print(f"  {'-'*42}")
    print(f"  {'OVERALL':<22} {scores['overall']:>5.1f}")
    print(f"{'='*55}")

    if result.error:
        print(f"\n  Warning: {result.error}")

    passed = scores["overall"] >= 70
    print(f"\n  {'PASS' if passed else 'FAIL'} (threshold: 70)\n")
    return 0 if passed else 1


def main():
    parser = argparse.ArgumentParser(description="Run AgentBench task")
    parser.add_argument("--task", required=True, help="Task ID e.g. task_01")
    parser.add_argument("--difficulty", default="none", choices=["none", "low", "medium", "high"])
    parser.add_argument("--purple-url", default="http://localhost:9010")
    parser.add_argument("--green-url", default="http://localhost:9009")
    args = parser.parse_args()
    sys.exit(asyncio.run(run(args.task, args.difficulty, args.purple_url, args.green_url)))


if __name__ == "__main__":
    main()
