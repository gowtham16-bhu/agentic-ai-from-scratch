import os
from step6_hardened import traced_orchestrator

# One notes file PER WORKER -- this is the actual isolation. math_worker's
# memory and writing_worker's memory never mix, same principle as their
# separate tools/context within a single run (Module 3), just extended
# across runs now.
NOTES_FILES = {
    "math": "notes_math.txt",
    "writing": "notes_writing.txt",
}

def read_notes(worker):
    path = NOTES_FILES[worker]
    if not os.path.exists(path):
        return ""
    with open(path, "r") as f:
        return f.read()

def append_note(worker, line):
    with open(NOTES_FILES[worker], "a") as f:
        f.write(line + "\n")

def remembering_orchestrator(question):
    # routing decision uses the raw question only -- we don't know which
    # worker will be picked yet, so we hand the orchestrator ALL workers'
    # notes and let IT pick the right one after routing (see orchestrator()
    # docstring in step4_orchestrator.py)
    extra_context_by_worker = {
        worker: f"(You remember this from before:\n{notes})"
        for worker in NOTES_FILES
        if (notes := read_notes(worker))
    }

    answer, worker = traced_orchestrator(question, extra_context_by_worker=extra_context_by_worker)

    if worker in NOTES_FILES:
        append_note(worker, f"Q: {question}\nA: {answer}")

    return answer, worker

if __name__ == "__main__":
    print("Run 1 (math question):")
    answer, worker = remembering_orchestrator("My favorite number is 7. What is 7 * 8?")
    print(f"A ({worker}): {answer}")

    print("\nRun 2 (writing question -- should NOT see the math worker's memory):")
    answer, worker = remembering_orchestrator("Write a one-word slogan for a bakery.")
    print(f"A ({worker}): {answer}")

    print("\nRun 3 (math question again -- SHOULD remember the favorite number):")
    answer, worker = remembering_orchestrator("What is my favorite number times 10?")
    print(f"A ({worker}): {answer}")
