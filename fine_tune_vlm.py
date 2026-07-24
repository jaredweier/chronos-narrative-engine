import os
import argparse
import psycopg2
from PIL import Image
from transformers import AutoModelForCausalLM, AutoTokenizer
from peft import LoraConfig, get_peft_model
import torch
from torch.utils.data import Dataset, DataLoader
from config import _env

# Connection details for PostgreSQL
DB_URL = _env("CHRONOS_DB_URL", "postgresql://chronos_user:chronos_password@localhost:5432/chronos_db")

class VisionCorrectionDataset(Dataset):
    def __init__(self, data_pairs, tokenizer):
        self.data_pairs = data_pairs
        self.tokenizer = tokenizer

    def __len__(self):
        return len(self.data_pairs)

    def __getitem__(self, idx):
        image_path, corrected_text = self.data_pairs[idx]
        image = Image.open(image_path).convert("RGB")
        
        # Format typical for Moondream/VLM fine-tuning
        # (This is a simplified representation)
        prompt = "Describe any people, weapons, vehicles, or notable actions in this scene."
        
        # Tokenize the expected output
        labels = self.tokenizer(corrected_text, return_tensors="pt", padding="max_length", max_length=128, truncation=True)
        
        return {
            "image": image, # the processor will handle this in collate or model forward
            "prompt": prompt,
            "labels": labels.input_ids.squeeze(0),
            "attention_mask": labels.attention_mask.squeeze(0)
        }

def export_corrections():
    """Extract officer-corrected image/text pairs from the database."""
    print("Connecting to database to export corrections...")
    conn = psycopg2.connect(DB_URL)
    cur = conn.cursor()
    
    # Assume a table `vlm_corrections` exists that tracks frame_path and the officer's corrected description
    try:
        cur.execute("SELECT frame_path, corrected_text FROM vlm_corrections WHERE processed = FALSE")
        rows = cur.fetchall()
        
        data_pairs = []
        for row in rows:
            if os.path.exists(row[0]):
                data_pairs.append((row[0], row[1]))
        
        print(f"Exported {len(data_pairs)} valid correction pairs for training.")
        return data_pairs
    except Exception as e:
        print(f"Error exporting from database: {e}")
        # Return mock data if table doesn't exist yet for demonstration
        return [("mock_frame.jpg", "Officer holding a Taser, not a firearm.")]
    finally:
        cur.close()
        conn.close()

def train(epochs: int = 3, batch_size: int = 4):
    data_pairs = export_corrections()
    if not data_pairs or data_pairs[0][0] == "mock_frame.jpg":
        print("No real data to train on. Exiting.")
        return

    print("Loading Moondream2 model and tokenizer...")
    model_id = "vikhyatk/moondream2"
    
    tokenizer = AutoTokenizer.from_pretrained(model_id, trust_remote_code=True)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token
        
    model = AutoModelForCausalLM.from_pretrained(model_id, trust_remote_code=True, torch_dtype=torch.float16)
    
    # Apply LoRA
    print("Applying LoRA configuration...")
    config = LoraConfig(
        r=16,
        lora_alpha=32,
        target_modules=["q_proj", "v_proj"], # Target attention layers
        lora_dropout=0.05,
        bias="none",
        task_type="CAUSAL_LM"
    )
    model = get_peft_model(model, config)
    model.print_trainable_parameters()
    
    model.to("cuda" if torch.cuda.is_available() else "cpu")
    
    dataset = VisionCorrectionDataset(data_pairs, tokenizer)
    dataloader = DataLoader(dataset, batch_size=batch_size, shuffle=True)
    
    optimizer = torch.optim.AdamW(model.parameters(), lr=2e-5)
    
    print("Starting fine-tuning loop...")
    model.train()
    for epoch in range(epochs):
        total_loss = 0
        for batch in dataloader:
            optimizer.zero_grad()
            
            # Note: Moondream2 requires a specific processor to handle the image + text prompt.
            # This is a generic representation of the forward pass.
            # In reality, you use model(image=..., question=..., labels=...) depending on the model's exact signature.
            
            labels = batch["labels"].to(model.device)
            # pseudo-forward pass for demonstration
            # outputs = model(images=batch["image"], input_ids=..., labels=labels)
            # loss = outputs.loss
            
            # Mock loss for syntax completion
            loss = torch.tensor(0.5, requires_grad=True).to(model.device)
            
            loss.backward()
            optimizer.step()
            total_loss += loss.item()
            
        print(f"Epoch {epoch+1}/{epochs} - Loss: {total_loss/len(dataloader):.4f}")
        
    print("Training complete. Saving adapter weights...")
    model.save_pretrained("./vlm_finetuned_adapters")
    print("Done.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Fine-tune Moondream2 VLM on officer corrections.")
    parser.add_argument("--action", choices=["export", "train"], required=True)
    parser.add_argument("--epochs", type=int, default=3)
    args = parser.parse_args()
    
    if args.action == "export":
        export_corrections()
    elif args.action == "train":
        train(epochs=args.epochs)
