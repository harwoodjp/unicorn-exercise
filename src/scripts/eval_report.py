import json
from collections import Counter, defaultdict
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

from db.connection import connect

PROJECT_ROOT = Path(__file__).resolve().parents[2]
EVAL_FILE = PROJECT_ROOT / "docs" / "ExerciseFiles" / "product_matching_eval.json"


def main() -> None:
    with connect() as conn, conn.cursor() as cur:
        cur.execute("SELECT import_id FROM submission ORDER BY created_at DESC LIMIT 1")
        row = cur.fetchone()
        if row is None:
            print("No submissions found. Run scripts/ingest.sh first.")
            return
        import_id = row[0]

        cur.execute(
            """
            SELECT submission_id, status, decision, matched_product_id,
                   llm_confidence, llm_model
            FROM submission
            WHERE import_id = %s
            """,
            (import_id,),
        )
        db_rows = {r[0]: r[1:] for r in cur.fetchall()}

    labels = json.loads(EVAL_FILE.read_text())["labels"]
    total = len(labels)

    pid_correct = 0
    decision_correct = 0
    false_positives = 0
    misses: list[str] = []

    emitted_decisions: Counter[str] = Counter()
    tier1_count = 0
    tier2_count = 0
    llm_confidences: list[float] = []

    class_stats: dict[str, list[int]] = defaultdict(lambda: [0, 0])  # key -> [correct, total]

    for label in labels:
        sid = label["submission_id"]
        expected_pid = label["expected_product_id"]
        acceptable = label["acceptable_decisions"]
        class_key = "{" + ", ".join(sorted(acceptable)) + "}"
        class_stats[class_key][1] += 1

        row = db_rows.get(sid)
        if row is None:
            misses.append(f"{sid}: not in DB")
            continue
        status, decision, matched_pid, llm_conf, llm_model = row

        if llm_model is None:
            tier1_count += 1
        else:
            tier2_count += 1
            if llm_conf is not None:
                llm_confidences.append(float(llm_conf))

        if "invalid" in acceptable:
            emitted_decisions["invalid (status)"] += 1
            if status == "invalid" and matched_pid is None:
                pid_correct += 1
                decision_correct += 1
                class_stats[class_key][0] += 1
            else:
                misses.append(
                    f"{sid}: expected invalid, got status={status}, "
                    f"decision={decision}, pid={matched_pid}"
                )
            continue

        emitted_decisions[decision or "(null)"] += 1

        pid_ok = matched_pid == expected_pid
        dec_ok = decision in acceptable

        if pid_ok:
            pid_correct += 1
        else:
            misses.append(f"{sid}: pid {matched_pid!r}, expected {expected_pid!r}")
        if dec_ok:
            decision_correct += 1
        else:
            misses.append(f"{sid}: decision {decision!r} not in {acceptable}")
        if pid_ok and dec_ok:
            class_stats[class_key][0] += 1
        if not pid_ok and decision in ("exact_match", "possible_match"):
            false_positives += 1

    def pct(num: int, denom: int) -> str:
        return f"{num / denom * 100:.1f}%" if denom else "-"

    print(f"\nEval results (import_id={import_id}, n={total}):")
    print()
    print("Overall:")
    print(f"  product_id correct:     {pid_correct}/{total} = {pct(pid_correct, total)}")
    print(f"  decision in acceptable: {decision_correct}/{total} = {pct(decision_correct, total)}")
    print(f"  false positives:        {false_positives}")

    print()
    print("Emitted decisions:")
    for d, c in emitted_decisions.most_common():
        print(f"  {d:18} {c}")

    print()
    print("Resolved by:")
    print(f"  tier 1 (deterministic): {tier1_count}")
    if llm_confidences:
        lo, hi = min(llm_confidences), max(llm_confidences)
        mean = sum(llm_confidences) / len(llm_confidences)
        print(f"  tier 2 (LLM):           {tier2_count}  (conf mean={mean:.2f}, range [{lo:.2f}, {hi:.2f}])")
    else:
        print(f"  tier 2 (LLM):           {tier2_count}")

    print()
    print("Accuracy by acceptable-decision set:")
    width = max(len(k) for k in class_stats) if class_stats else 0
    for key in sorted(class_stats):
        correct, n = class_stats[key]
        print(f"  {key:<{width}}  {correct}/{n} ({pct(correct, n)})")

    if misses:
        print()
        print("Misses:")
        for m in misses:
            print(f"  {m}")


if __name__ == "__main__":
    main()
