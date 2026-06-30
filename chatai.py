from openai import OpenAI
import os
import requests

models = ["deepseek-ai/DeepSeek-V4-Pro:novita","deepseek-ai/DeepSeek-V4-Flash:novita"]
HFAPI = os.getenv("HFAPI")
client = OpenAI(
    base_url="https://router.huggingface.co/v1",
    api_key= os.getenv("api_key"),
)
API_URL = "https://router.huggingface.co/hf-inference/models/BAAI/bge-base-en-v1.5"


def acc(prompt,sysprompt = ""):
    completion = client.chat.completions.create(
    model= "deepseek-ai/DeepSeek-V4-Pro:novita",
    messages=[
         {"role": "system", "content": f"You are an AI assistant. Always respond in English only. {sysprompt}"},
    
        {
            "role": "user",
            "content": prompt
        }
    ],
    )
    return(completion.choices[0].message.content)

def fast(prompt,sysprompt = ""):
    completion = client.chat.completions.create(
    model= "deepseek-ai/DeepSeek-V4-Flash:novita",
    messages=[
         {"role": "system", "content": f"You are an AI assistant. Always respond in English only. {sysprompt}"},
    
        {
            "role": "user", "content": prompt
        }
    ],
    )

    return(completion.choices[0].message.content)

def vector(prompt):
    headers = {
    "Authorization": f"Bearer {HFAPI}"
    }

    data = {
        "inputs":prompt
    }

    response = requests.post(API_URL, headers=headers, json=data)
    return(response.json())


def airesponse(user_message=""):
    response = fast(user_message)
    return (response)
