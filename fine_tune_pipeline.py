"""
Chronos Fine-Tuning Pipeline

Extracts corrected reports from the database (AI draft vs. officer-corrected final)
and prepares a dataset for fine-tuning Whisper on law enforcement vocabulary.

Run on the target machine (RTX 5070 Ti) when sufficient corrected reports exist.

Usage:
    # Extract training pairs from database
    python fine_tune_pipeline.py export --min-pairs 50

    # Fine-tune Whisper on extracted data
    python fine_tune_pipeline.py train --model large-v3-turbo --epochs 3
"""
import argparse
import difflib
import json
import os
import sys
from typing import List, Dict, Optional

from database import get_db_connection
from config import BASE_DIR
from logger import get_logger

logger = get_logger(__name__)


def export_training_pairs(min_pairs: int = 50, output_dir: str = None) -> List[Dict]:
    """
    Export AI-draft vs. corrected-final pairs from the database for fine-tuning.
    Only includes entries where the human made corrections (was_modified_by_human=1).
    """
    if output_dir is None:
        output_dir = os.path.join(BASE_DIR, "training_data")
    os.makedirs(output_dir, exist_ok=True)

    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT incident_id, officer_name, document_type, unedited_ai_draft, final_approved_report
        FROM legal_audit_logs
        WHERE was_modified_by_human = 1
          AND unedited_ai_draft IS NOT NULL
          AND final_approved_report IS NOT NULL
          AND length(unedited_ai_draft) > 50
          AND length(final_approved_report) > 50
        ORDER BY submission_timestamp DESC
    """)

    pairs = []
    for row in cur.fetchall():
        pairs.append({
            "incident_id": row["incident_id"],
            "officer_name": row["officer_name"],
            "document_type": row["document_type"],
            "ai_draft": row["unedited_ai_draft"],
            "corrected": row["final_approved_report"],
        })

    conn.close()

    if len(pairs) < min_pairs:
        logger.warning(
            "Only %d training pairs available (need %d). "
            "Collect more corrected reports before fine-tuning.",
            len(pairs), min_pairs,
        )

    manifest_path = os.path.join(output_dir, "training_manifest.json")
    with open(manifest_path, "w") as f:
        json.dump({"total_pairs": len(pairs), "pairs": pairs}, f, indent=2)

    logger.info("Exported %d training pairs to %s", len(pairs), manifest_path)
    return pairs


def prepare_fine_tune_dataset(pairs: List[Dict], output_dir: str) -> Optional[str]:
    """
    Convert exported pairs into a format suitable for Whisper fine-tuning.
    Creates a JSONL file with 'text' (corrected) and 'ai_text' (original draft) fields.
    """
    jsonl_path = os.path.join(output_dir, "le_corrections_dataset.jsonl")
    with open(jsonl_path, "w") as f:
        for pair in pairs:
            record = {
                "text": pair["corrected"],
                "ai_text": pair["ai_draft"],
                "document_type": pair["document_type"],
                "officer_name": pair["officer_name"],
            }
            f.write(json.dumps(record) + "\n")

    logger.info("Prepared fine-tune dataset: %s (%d samples)", jsonl_path, len(pairs))
    return jsonl_path


def run_training(
    model_name: str = "large-v3-turbo",
    data_path: str = None,
    output_dir: str = None,
    epochs: int = 3,
    batch_size: int = 8,
    learning_rate: float = 1e-5,
):
    """
    Fine-tune Whisper on LE-corrected transcript data.
    Requires: transformers, datasets, torch, evaluate, jiwer
    """
    if output_dir is None:
        output_dir = os.path.join(BASE_DIR, "fine_tuned_model")
    os.makedirs(output_dir, exist_ok=True)

    try:
        import torch
        from transformers import (
            WhisperForConditionalGeneration,
            WhisperProcessor,
            Seq2SeqTrainingArguments,
            Seq2SeqTrainer,
        )
        from datasets import Dataset, load_dataset
    except ImportError as e:
        logger.error(
            "Missing dependency for fine-tuning: %s\n"
            "Install with: pip install transformers datasets evaluate jiwer torch",
            e,
        )
        return

    if data_path is None:
        data_path = os.path.join(BASE_DIR, "training_data", "le_corrections_dataset.jsonl")

    if not os.path.exists(data_path):
        logger.error("Training data not found: %s", data_path)
        return

    logger.info("Loading Whisper model: %s", model_name)
    processor = WhisperProcessor.from_pretrained(model_name)
    model = WhisperForConditionalGeneration.from_pretrained(model_name)

    model.config.forced_decoder_ids = None
    model.config.suppress_tokens = []

    logger.info("Loading training data from %s", data_path)
    dataset = load_dataset("json", data_files=data_path, split="train")
    dataset = dataset.train_test_split(test_size=0.1, seed=42)

    def prepare_dataset(batch):
        batch["text"] = batch["text"]
        return batch

    dataset = dataset.map(prepare_dataset)

    training_args = Seq2SeqTrainingArguments(
        output_dir=output_dir,
        per_device_train_batch_size=batch_size,
        per_device_eval_batch_size=batch_size,
        learning_rate=learning_rate,
        num_train_epochs=epochs,
        evaluation_strategy="epoch",
        save_strategy="epoch",
        logging_steps=10,
        predict_with_generate=True,
        generation_max_length=225,
        fp16=torch.cuda.is_available(),
        report_to="none",
    )

    trainer = Seq2SeqTrainer(
        model=model,
        args=training_args,
        train_dataset=dataset["train"],
        eval_dataset=dataset["test"],
        tokenizer=processor.feature_extractor,
    )

    logger.info("Starting fine-tuning (%d epochs, %d training samples)...",
                epochs, len(dataset["train"]))
    trainer.train()

    model.save_pretrained(output_dir)
    processor.save_pretrained(output_dir)
    logger.info("Fine-tuned model saved to %s", output_dir)


def main():
    parser = argparse.ArgumentParser(description="Chronos Whisper Fine-Tuning Pipeline")
    subparsers = parser.add_subparsers(dest="command")

    # Export command
    export_parser = subparsers.add_parser("export", help="Export training pairs from DB")
    export_parser.add_argument("--min-pairs", type=int, default=50,
                               help="Minimum pairs required (default: 50)")
    export_parser.add_argument("--output-dir", default=None,
                               help="Output directory for training data")

    # Train command
    train_parser = subparsers.add_parser("train", help="Fine-tune Whisper model")
    train_parser.add_argument("--model", default="large-v3-turbo",
                              help="Base Whisper model (default: large-v3-turbo)")
    train_parser.add_argument("--data-path", default=None,
                              help="Path to training JSONL")
    train_parser.add_argument("--output-dir", default=None,
                              help="Output directory for fine-tuned model")
    train_parser.add_argument("--epochs", type=int, default=3,
                              help="Training epochs (default: 3)")
    train_parser.add_argument("--batch-size", type=int, default=8,
                              help="Per-device batch size (default: 8)")
    train_parser.add_argument("--learning-rate", type=float, default=1e-5,
                              help="Learning rate (default: 1e-5)")

    args = parser.parse_args()

    if args.command == "export":
        pairs = export_training_pairs(min_pairs=args.min_pairs, output_dir=args.output_dir)
        if pairs:
            prepare_fine_tune_dataset(pairs, args.output_dir or
                                      os.path.join(BASE_DIR, "training_data"))
            print(f"Exported {len(pairs)} training pairs")

    elif args.command == "train":
        run_training(
            model_name=args.model,
            data_path=args.data_path,
            output_dir=args.output_dir,
            epochs=args.epochs,
            batch_size=args.batch_size,
            learning_rate=args.learning_rate,
        )

    else:
        parser.print_help()


def export_quality_report(output_dir: str = None) -> str:
    from config import BASE_DIR
    pairs = export_training_pairs(min_pairs=1, output_dir=output_dir)
    if not pairs:
        report = {"total_pairs": 0, "average_edit_distance": 0.0, "common_corrections": [], "by_document_type": {}}
    else:
        total = len(pairs)
        distances = []
        for p in pairs:
            matcher = difflib.SequenceMatcher(None, p["ai_draft"], p["corrected"])
            ratio = matcher.ratio()
            distances.append(ratio)
        avg_distance = sum(distances) / total if total else 0.0
        by_type = {}
        for p in pairs:
            dt = p.get("document_type", "unknown")
            by_type.setdefault(dt, 0)
            by_type[dt] += 1
        report = {
            "total_pairs": total,
            "average_edit_distance": round(1 - avg_distance, 4),
            "by_document_type": by_type,
        }
    if output_dir is None:
        output_dir = os.path.join(BASE_DIR, "training_data")
    os.makedirs(output_dir, exist_ok=True)
    report_path = os.path.join(output_dir, "quality_report.json")
    with open(report_path, "w") as f:
        json.dump(report, f, indent=2)
    logger.info("Quality report written to %s", report_path)
    return report_path


if __name__ == "__main__":
    main()
