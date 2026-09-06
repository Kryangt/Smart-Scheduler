"""
Basic end-to-end reliability test for SmartScheduling.

Purpose:
- Send realistic user requests to the REAL running FastAPI backend.
- Do NOT mock the AI.
- Do NOT require Google login because /task-decomposition is currently unauthenticated.
- Measure one simple metric: end-to-end success rate.

How to run:
1. Start your backend, for example:
       uvicorn backend.app.main:app --host 127.0.0.1 --port 8080

2. In another terminal:
       python tests/reliability/test_system_reliability.py

Optional:
    Set a different backend URL:
       SMARTSCHEDULER_BASE_URL=http://127.0.0.1:8000 python tests/reliability/test_system_reliability.py
"""

import json
import os
import time
from pathlib import Path

import requests


BASE_URL = os.getenv(
    "SMARTSCHEDULER_BASE_URL",
    "http://127.0.0.1:8080",
).rstrip("/")

ENDPOINT = f"{BASE_URL}/task-decomposition"
TIMEOUT_SECONDS = 120

RESULTS_DIR = Path(__file__).parent / "results"
RESULTS_FILE = RESULTS_DIR / "system_reliability_results.json"


TEST_CASES = [
    {
        "id": 1,
        "expected": "success",
        "input": (
            "Finish my operating systems coding assignment about implement multi-filesystem by next Monday"
        ),
    },
    {
        "id": 2,
        "expected": "success",
        "input": (
            "Prepare a 10 minutes presentation of Zeus law in the Odessey tonight, including making slides"
        ),
    },
    {
        "id": 3,
        "expected": "clarification",
        "input": (
            "complete the quarterly financial report"
        ),
    },
    {
        "id": 4,
        "expected": "success",
        "input": (
            "Finish my topology homework by next tuesday, chapter 7 exercises"
        ),
    },
    {
        "id": 5,
        "expected": "clarification",
        "input": (
            "Continue my SmartSchedule project, debug the database part"
        ),
    },
    {
        "id": 6,
        "expected": "clarification",
        "input": (
            "Prepare a dinner event for 6 people today"
        ),
    },
    {
        "id": 7,
        "expected": "success",
        "input": (
            "start to prepare and cook a homemade dinner for 6 people, be ready by 7:00 PM today. The budget is about $1000"
        ),
    },
    {
        "id": 8,
        "expected": "success",
        "input": (
            "Pack up my 1b1b apartment for move-out by August 25. I have a normal amount of furniture and belongings."
        ),
    },
    {
        "id": 9,
        "expected": "clarification",
        "input": (
            "Pack up my apartment for move-out by August 25."
        ),
    },
    {
        "id": 10,
        "expected": "success",
        "input": (
            "Finish my machine learning homework by sunday, implement logistic regression and write the short report"
        ),
    },
    {
        "id": 11,
        "expected": "clarification",
        "input": (
            "Prepare materials for the client meeting tomorrow"
        ),
    },
    {
        "id": 12,
        "expected": "success",
        "input": (
            "Prepare a 15 minutes client presentation about Q3 sales performance by tomorrow afternoon, including making slides"
        ),
    },
    {
        "id": 13,
        "expected": "clarification",
        "input": (
            "Clean up the apartment this weekend"
        ),
    },
    {
        "id": 14,
        "expected": "success",
        "input": (
            "Deep clean my 1b1b apartment this saturday, including kitchen bathroom bedroom and living room"
        ),
    },
    {
        "id": 15,
        "expected": "clarification",
        "input": (
            "Finish the patient report by tomorrow"
        ),
    },
    {
        "id": 16,
        "expected": "success",
        "input": (
            "Finish the regular discharge summary for 8 patients by tomorrow noon, all lab results and doctor notes are already available"
        ),
    },
    {
        "id": 17,
        "expected": "clarification",
        "input": (
            "Fix the frontend issue in my React project"
        ),
    },
    {
        "id": 18,
        "expected": "success",
        "input": (
            "Find and Fix the React login page bug where the submit button does nothing after entering email and password, finish it tonight"
        ),
    },
    {
        "id": 19,
        "expected": "clarification",
        "input": (
            "Study for my chemistry exam next week"
        ),
    },
    {
        "id": 20,
        "expected": "success",
        "input": (
            "continue review chapter 5 to chapter 8 for my chemistry exam next friday, focus on equilibrium acids bases and thermodynamics"
        ),
    },
    {
        "id": 21,
        "expected": "clarification",
        "input": (
            "Prepare the monthly marketing report"
        ),
    },
    {
        "id": 22,
        "expected": "success",
        "input": (
            "Prepare the monthly marketing report for our social media campaigns by monday, summarize Instagram TikTok and Google Ads performance"
        ),
    },
    {
        "id": 23,
        "expected": "clarification",
        "input": (
            "Get everything ready for my trip tomorrow"
        ),
    },
    {
        "id": 24,
        "expected": "success",
        "input": (
            "Pack for my 4 days business trip to Seattle tomorrow morning, including clothes laptop chargers and work documents"
        ),
    },
    {
        "id": 25,
        "expected": "clarification",
        "input": (
            "Review the legal contract before friday"
        ),
    },
    {
        "id": 26,
        "expected": "success",
        "input": (
            "Review a 12 page software vendor contract before friday, focus on payment terms termination and data privacy clauses"
        ),
    },
    {
        "id": 27,
        "expected": "clarification",
        "input": (
            "Analyze the experiment results for my research project"
        ),
    },
    {
        "id": 28,
        "expected": "success",
        "input": (
            "Analyze the results from my robotics experiment by sunday, compare the success rate of 3 control methods across 200 trials"
        ),
    },
    {
        "id": 29,
        "expected": "clarification",
        "input": (
            "Prepare food for the party tonight"
        ),
    }
]


def build_payload(user_input: str) -> dict:
    return {
        "clarifyMessages": [
            {
                "id": 1,
                "role": "user",
                "content": user_input,
            }
        ]
    }


def classify_response(data: dict) -> tuple[bool, str]:
    """
    Check whether the returned object is usable.

    This deliberately does NOT judge whether the wording is perfect.
    It only checks whether the system returned a meaningful result.
    """
    status = data.get("status")

    # Your current JSON schema uses "need_clarification".
    # Older tests/code may use "needs_clarification", so both are accepted here.
    if status in {"need_clarification", "needs_clarification"}:
        questions = data.get("questions", [])
        if isinstance(questions, list) and len(questions) > 0:
            return True, "clarification"
        return False, "clarification response contains no questions"

    if status == "success":
        sub_tasks = data.get("sub_tasks")

        if not isinstance(sub_tasks, list) or len(sub_tasks) == 0:
            return False, "success response contains no subtasks"

        for index, task in enumerate(sub_tasks):
            if not isinstance(task, dict):
                return False, f"subtask {index} is not an object"

            if not task.get("title"):
                return False, f"subtask {index} has no title"

            if not task.get("deadline"):
                return False, f"subtask {index} has no deadline"

            duration = task.get("estimated_duration_minutes")
            if duration is not None and (
                not isinstance(duration, int) or duration <= 0
            ):
                return False, f"subtask {index} has invalid duration"

            if "depends_on" not in task or not isinstance(task["depends_on"], list):
                return False, f"subtask {index} has invalid depends_on"

        return True, "success"

    if status == "error":
        return False, f"application returned error: {data.get('message')}"

    return False, f"unexpected status: {status!r}"


def run_case(case: dict) -> dict:
    started = time.perf_counter()

    try:
        response = requests.post(
            ENDPOINT,
            json=build_payload(case["input"]),
            timeout=TIMEOUT_SECONDS,
        )
        latency = time.perf_counter() - started

    except requests.RequestException as exc:
        return {
            "id": case["id"],
            "input": case["input"],
            "expected": case["expected"],
            "passed": False,
            "latency_seconds": round(time.perf_counter() - started, 3),
            "reason": f"request failed: {exc}",
            "response": None,
        }

    try:
        data = response.json()
    except ValueError:
        data = None

    if response.status_code != 200:
        return {
            "id": case["id"],
            "input": case["input"],
            "expected": case["expected"],
            "passed": False,
            "latency_seconds": round(latency, 3),
            "reason": f"HTTP {response.status_code}",
            "response": data if data is not None else response.text,
        }

    if not isinstance(data, dict):
        return {
            "id": case["id"],
            "input": case["input"],
            "expected": case["expected"],
            "passed": False,
            "latency_seconds": round(latency, 3),
            "reason": "response is not a JSON object",
            "response": data,
        }

    structurally_valid, actual_outcome = classify_response(data)

    if not structurally_valid:
        passed = False
        reason = actual_outcome
    else:
        passed = actual_outcome == case["expected"]
        if passed:
            reason = "matched expected behavior"
        else:
            reason = (
                f"expected {case['expected']}, "
                f"but system returned {actual_outcome}"
            )

    return {
        "id": case["id"],
        "input": case["input"],
        "expected": case["expected"],
        "actual": actual_outcome,
        "passed": passed,
        "latency_seconds": round(latency, 3),
        "reason": reason,
        "response": data,
    }


def main() -> None:
    print("=" * 72)
    print("SmartScheduling - Basic End-to-End Reliability Test")
    print("=" * 72)
    print(f"Backend: {BASE_URL}")
    print(f"Endpoint: {ENDPOINT}")
    print(f"Cases: {len(TEST_CASES)}")
    print()

    # Quick health check first.
    try:
        health = requests.get(f"{BASE_URL}/", timeout=10)
        if health.status_code != 200:
            print(f"Backend health check failed: HTTP {health.status_code}")
            raise SystemExit(1)
    except requests.RequestException as exc:
        print(f"Cannot connect to backend: {exc}")
        print("Start the FastAPI server before running this test.")
        raise SystemExit(1)

    results = []

    for case in TEST_CASES:
        print(f"[{case['id']:02d}] {case['input']}")

        result = run_case(case)
        results.append(result)

        marker = "PASS" if result["passed"] else "FAIL"
        print(
            f"     {marker} | expected={result['expected']} "
            f"| actual={result.get('actual', 'N/A')} "
            f"| {result['latency_seconds']}s"
        )

        if not result["passed"]:
            print(f"     Reason: {result['reason']}")

        print()

    passed_count = sum(1 for result in results if result["passed"])
    failed_count = len(results) - passed_count
    success_rate = passed_count / len(results)

    average_latency = (
        sum(result["latency_seconds"] for result in results) / len(results)
    )

    summary = {
        "total_cases": len(results),
        "passed": passed_count,
        "failed": failed_count,
        "end_to_end_success_rate": round(success_rate, 4),
        "average_latency_seconds": round(average_latency, 3),
    }

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)

    with RESULTS_FILE.open("w", encoding="utf-8") as file:
        json.dump(
            {
                "summary": summary,
                "results": results,
            },
            file,
            indent=2,
            ensure_ascii=False,
        )

    print("=" * 72)
    print("RESULT")
    print("=" * 72)
    print(f"Passed: {passed_count}/{len(results)}")
    print(f"Failed: {failed_count}/{len(results)}")
    print(f"End-to-end success rate: {success_rate:.1%}")
    print(f"Average response time: {average_latency:.2f}s")
    print(f"Detailed results saved to: {RESULTS_FILE}")

    # This makes the script useful in CI later:
    # exit non-zero if any case fails.
    if failed_count > 0:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
