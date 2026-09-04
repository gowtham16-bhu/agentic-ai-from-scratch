from step4_orchestrator import orchestrator

# Each case: (question, expected_worker, expected_answer_or_None)
# expected_answer is only checked for math (exact string match on the number).
# For writing, we only check a worker got picked and produced non-empty text.
CASES = [
    ("What is 128 * 37?", "math", "4736"),
    ("What is 15 * 15?", "math", "225"),
    ("What is 900 / 4?", "math", "225"),
    ("Write a one-sentence tagline for a coffee shop.", "writing", None),
    ("Summarize why sleep matters in one sentence.", "writing", None),
]

def run_eval():
    passed = 0
    for question, expected_worker, expected_answer in CASES:
        answer, actual_worker = orchestrator(question)
        routed_correctly = actual_worker == expected_worker

        if expected_answer is not None:
            answer_correct = expected_answer in answer
        else:
            answer_correct = bool(answer.strip())

        ok = routed_correctly and answer_correct
        passed += ok

        status = "PASS" if ok else "FAIL"
        print(f"[{status}] '{question}'")
        if not routed_correctly:
            print(f"       routed to {actual_worker}, expected {expected_worker}")
        if not answer_correct:
            print(f"       answer did not look right: {answer}")

    print(f"\n{passed}/{len(CASES)} passed")

if __name__ == "__main__":
    run_eval()
