"""
Interview practice CLI — quiz yourself on your own STAR stories.

Local-only tool, not wired into the web app or RAG. Picks a behavioral
story from resume_content.py, asks you the interview question, takes your
spoken/typed answer, and uses the local Ollama model to grade it against
your real situation/action/result.

Usage:
    python -m backend.scripts.interview_practice            # practice all stories, shuffled
    python -m backend.scripts.interview_practice coin       # filter by theme/title/skill keyword
    python -m backend.scripts.interview_practice --list      # just list available questions
"""
import argparse
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from backend.knowledge.interview_coach import grade_answer  # noqa: E402
from backend.routers import resume_content as rc  # noqa: E402


def _matches(story: dict, keyword: str) -> bool:
    keyword = keyword.lower()
    haystack = " ".join([
        story.get("theme", ""),
        story.get("title", ""),
        story.get("question", ""),
        " ".join(story.get("skills", [])),
    ]).lower()
    return keyword in haystack


def _read_multiline(prompt: str) -> str:
    print(prompt)
    print("(Type your answer. Submit with an empty line, or Ctrl-D to skip grading.)")
    lines = []
    while True:
        try:
            line = input()
        except EOFError:
            break
        if line == "":
            break
        lines.append(line)
    return "\n".join(lines).strip()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "keyword", nargs="?", default=None,
        help="Filter stories by theme, title, or skill keyword (e.g. 'coin', 'genai', 'vault')",
    )
    parser.add_argument("--list", action="store_true", help="List available questions and exit")
    args = parser.parse_args()

    stories = list(rc.RESUME_BEHAVIORAL_STORIES)
    if args.keyword:
        filtered = [s for s in stories if _matches(s, args.keyword)]
        if not filtered:
            print(f"No stories match '{args.keyword}'. Available themes:")
            for s in stories:
                print(f"  - {s['theme']}: {s['title']}")
            return
        stories = filtered

    if args.list:
        for s in stories:
            print(f"[{s['theme']}] {s['question']}\n    -> {s['title']}\n")
        return

    random.shuffle(stories)
    print(f"\n{len(stories)} question(s) loaded. Ctrl-C anytime to quit.\n")

    for i, story in enumerate(stories, 1):
        print("=" * 70)
        print(f"({i}/{len(stories)}) [{story['theme']}]")
        answer = _read_multiline(f"\nQ: {story['question']}\n")

        if not answer:
            print("\n--- Reference answer ---")
            print(f"Situation: {story['situation']}\n")
            print(f"Action: {story['action']}\n")
            print(f"Result: {story['result']}\n")
        else:
            print("\nGrading against your reference answer...\n")
            try:
                print(grade_answer(story["question"], story["situation"], story["action"], story["result"], answer))
            except Exception as exc:
                print(f"(Could not reach local LLM: {exc})")

        print()
        try:
            cont = input("Next question? [Y/n/q] ").strip().lower()
        except EOFError:
            cont = "q"
        if cont in ("n", "q", "no", "quit"):
            break

    print("\nGood luck!")


if __name__ == "__main__":
    main()
