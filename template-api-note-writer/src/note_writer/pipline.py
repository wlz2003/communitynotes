from transformers import AutoTokenizer, AutoModel
import torch
import os
import random
from openai import BadRequestError, OpenAI
import time

def get_note(post: str, comments: str):
    client = OpenAI(
        base_url="https://api.gpt.ge/v1",
        api_key="sk-UsyUUOMgImAWV5bxD1910253264f44AeA15c93041bA83e35",
    )
    response = client.chat.completions.create(
        model="cc-3-7-sonnet-20250219",
        messages=[
            {"role": "system", "content": "X has a crowd-sourced fact-checking program, called Community Notes. Here, users can write ’notes’ on potentially misleading content. Community Notes will be shown publicly alongside the piece of content.\nYou will be provided with a post from X and some comments.  Your job is to find fact-check information in those comments that indicates that there are some thing inaccurate in the post and use those information to write a piece of Community Note of yourself.  It should be in unbiased language, not argumentative. It should also be within 280 characters."},
            # {"role": "system", "content": "You will be provided with a post from X along with additional information. Identify any inaccurate or misleading content in the post based on this information, and summarize the correct or clarified facts in the form of a single, well-organized paragraph. Present the information as if it reflects your own understanding, without referencing any sources or indicating where the information comes from. Answer in English."},
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "POST: " + post},
                    {"type": "text", "text": "COMMENTS: " + comments},
                    {"type": "text", "text": "Do not use the word \"comments\" in your answer. Regard the comments as your own thoughts and opinions. Do not start with \" Community Note:\",just start with content"},
                ],
            }
        ],
    )
    return str(response.choices[0].message.content)

# Custom model class (must be the same as the one used for training)
class E5ForSequenceClassification(torch.nn.Module):
    def __init__(self, model_name, num_labels=2):
        super().__init__()
        self.base_model = AutoModel.from_pretrained(model_name)
        self.classifier = torch.nn.Linear(self.base_model.config.hidden_size, num_labels)
        self.loss_fct = torch.nn.CrossEntropyLoss()
        
    def forward(self, input_ids, attention_mask, labels=None, **kwargs):
        outputs = self.base_model(input_ids=input_ids, attention_mask=attention_mask)
        pooled_output = outputs.last_hidden_state[:, 0]
        logits = self.classifier(pooled_output)
        
        loss = None
        if labels is not None:
            loss = self.loss_fct(logits.view(-1, self.classifier.out_features), labels.view(-1))
            
        return {"logits": logits, "loss": loss}

# 路径配置
save_path = r"E:\projects\srt\code\final_model_e5_v2"
state_dict_path = os.path.join(save_path, "final_model_e5_v2.pth")

# 检查设备
device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

# 加载分词器和模型
tokenizer = AutoTokenizer.from_pretrained(save_path)
# Instantiate the custom model class
model = E5ForSequenceClassification(model_name="intfloat/e5-base-v2", num_labels=2)
# Load the saved state dictionary
model.load_state_dict(torch.load(state_dict_path, map_location=device))
model.to(device)

# ---
# You can only modify the following function
def predict(post, comment):
    """
    Predicts the class of a comment based on a post using the E5 model fine-tuned for classification.
    """
    model.eval()
    
    # E5-specific input format: "query: {post} passage: {comment}"
    text = f"query: {post} passage: {comment}"
    
    encoding = tokenizer(
        text,
        return_tensors="pt",
        max_length=256,
        truncation=True,
        padding="max_length"
    ).to(device)
    
    with torch.no_grad():
        # Pass the encoding to the custom model
        outputs = model(input_ids=encoding['input_ids'], attention_mask=encoding['attention_mask'])
        logits = outputs["logits"]
        pred = torch.argmax(logits, dim=-1).item()
        
    return pred

def filter_comments(comments:list, post:str):
    res = []
    for comment in comments:
        pred = predict(post, comment)
        if pred == 1:
            res.append(comment)
    return res

def synthesize(post:str, comments:list):
    if len(comments) == 0:
        return None
    sampled_comments = random.sample(comments, min(300, len(comments)))
    comments ="\n".join(sampled_comments)
    note = get_note(post, comments)
    return note

