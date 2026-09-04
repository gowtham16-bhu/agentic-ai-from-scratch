import json
import os
import time
from step4_orchestrator import orchestrator

TRACE_FILE = "traces.jsonl"   # one JSON object per line, one line per run
KILL_SWITCH_FILE = "STOP"     # if this file exists, refuse to run

class KilledError(Exception):
    pass

def check_kill_switch():
    if os.path.exists(KILL_SWITCH_FILE):
        raise KilledError(f"kill switch active: '{KILL_SWITCH_FILE}' file exists. Delete it to resume.")

def traced_orchestrator(question, extra_context_by_worker=None):
    check_kill_switch()  # checked BEFORE doing any work, not after

    start = time.time()
    answer, worker = orchestrator(question, extra_context_by_worker=extra_context_by_worker)
    latency = time.time() - start

    trace = {
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "question": question,
        "worker": worker,
        "answer": answer,
        "latency_seconds": round(latency, 2),
    }
    # 'a' = append mode -- each run adds one line, never overwrites past traces
    with open(TRACE_FILE, "a") as f:
        f.write(json.dumps(trace) + "\n")

    return answer, worker

if __name__ == "__main__":
    for q in [
        "What is 128 * 37?",
        "Write a one-sentence tagline for a coffee shop.",
    ]:
        print(f"\nQ: {q}")
        try:
            answer, worker = traced_orchestrator(q)
            print(f"A ({worker}): {answer}")
        except KilledError as e:
            print(f"REFUSED TO RUN: {e}")
            break

    print(f"\nSee {TRACE_FILE} for the full trace log.")
