# experiments/slm-parser/models/llm_models.py

import time
import os
from dotenv import load_dotenv

load_dotenv()


# ── Model Registry ────────────────────────────────────────────────

CLOUD_MODELS = {
    "gemini_flash": {
        "name":        "gemini-3.7-flash",
        "provider":    "gemini",
        "file_tag":    "Gemini_3_7_Flash",
        "description": "Gemini 3.7 Flash — fast",
        "enabled":     False
    },
    "gemini_3_6_flash": {
        "name":         "gemini-3.6-flash",
        "provider":     "gemini",
        "file_tag":     "Gemini_3_6_Flash",
        "description":  "Gemini 3.6 Flash — strong balance of speed and capability",
        "enabled":      True,
    },
    "gemini_flash_3_5": {
        "name":        "gemini-3.5-flash",
        "provider":    "gemini",
        "file_tag":    "Gemini_3_5_Flash",
        "description": "Gemini 3.5 Flash — fast",
        "enabled":     True
    },
    "gemini_flash_lite": {
        "name":        "gemini-3.5-flash-lite",
        "provider":    "gemini",
        "file_tag":    "Gemini_3_5_Flash_Lite",
        "description": "Gemini 3.5 Flash-Lite — lightweight and fast",
        "enabled":     True
    },
    "groq_gpt_oss_20b": {
        "name":        "openai/gpt-oss-20b",
        "provider":    "groq",
        "file_tag":    "Groq_GPT_OSS_20B",
        "description": "GPT-OSS 20B via Groq — fast inference",
        "enabled":     False
    },
    "groq_gpt_oss_120b": {
        "name":        "openai/gpt-oss-120b",
        "provider":    "groq",
        "file_tag":    "Groq_GPT_OSS_120B",
        "description": "GPT-OSS 120B via Groq",
        "enabled":     False
    },
    "groq_qwen_3_6_27b": {
        "name":        "qwen/qwen3.6-27b",
        "provider":    "groq",
        "file_tag":    "Groq_Qwen3_6_27B",
        "description": "Qwen 3.6 27B via Groq",
        "enabled":     False
    },
    "groq_qwen_3_8_27b": {
        "name":        "qwen/qwen3.8-27b",
        "provider":    "groq",
        "file_tag":    "Groq_Qwen3_8_27B",
        "description": "Qwen 3.8 27B via Groq",
        "enabled":     False
    },
    "groq_allam_2_7b": {
        "name":        "allam-2-7b",
        "provider":    "groq",
        "file_tag":    "Groq_Allam_2_7B",
        "description": "ALLaM 2 7B via Groq",
        "enabled":     False
    },
    "nvidia_deepseek_v4_flash": {
        "name":        "deepseek-ai/deepseek-v4-flash-0731",
        "provider":    "nvidia",
        "file_tag":    "NVIDIA_DeepSeek_V4_Flash",
        "description": "DeepSeek V4 Flash via NVIDIA",
        "enabled":     True
    },
    "nvidia_deepseek_v4_pro": {
        "name":        "deepseek-ai/deepseek-v4-pro-0813",
        "provider":    "nvidia",
        "file_tag":    "NVIDIA_DeepSeek_V4_Pro",
        "description": "DeepSeek V4 Pro via NVIDIA",
        "enabled":     False
    },
    "nvidia_gemma_4_31b": {
        "name":        "google/gemma-4-31b-it",
        "provider":    "nvidia",
        "file_tag":    "NVIDIA_Gemma_4_31B",
        "description": "Gemma 4 31B via NVIDIA",
        "enabled":     True 
    },
    "nvidia_minimax_m3": {
        "name":        "minimaxai/minimax-m3",
        "provider":    "nvidia",
        "file_tag":    "NVIDIA_MiniMax_M3",
        "description": "MiniMax M3 via NVIDIA",
        "enabled":     True 
    },
    "nvidia_mistral_large": {
        "name":        "mistralai/mistral-large",
        "provider":    "nvidia",
        "file_tag":    "NVIDIA_Mistral_Large",
        "description": "Mistral Large via NVIDIA",
        "enabled":     False
    },
    "nvidia_kimi_k2_6": {
        "name":        "moonshotai/kimi-k2.6",
        "provider":    "nvidia",
        "file_tag":    "NVIDIA_Kimi_K2_6",
        "description": "Kimi K2.6 via NVIDIA",
        "enabled":     False
    },
    "nvidia_kimi_k3": {
        "name":        "moonshotai/kimi-k3",
        "provider":    "nvidia",
        "file_tag":    "NVIDIA_Kimi_K3",
        "description": "Kimi K3 via NVIDIA",
        "enabled":     False
    },
    "nvidia_nemotron_3_5_lightning": {
        "name":        "nvidia/nemotron-3.5-lightning-30b-a3b",
        "provider":    "nvidia",
        "file_tag":    "NVIDIA_Nemotron_3_5_Lightning",
        "description": "Nemotron 3.5 Lightning 30B A3B via NVIDIA",
        "enabled":     True
    },
    "nvidia_nemotron_3_super": {
        "name":        "nvidia/nemotron-3-super-120b-a12b",
        "provider":    "nvidia",
        "file_tag":    "NVIDIA_Nemotron_3_Super",
        "description": "Nemotron 3 Super 120B A12B via NVIDIA",
        "enabled":     True
    },
    "nvidia_nemotron_3_ultra": {
        "name":        "nvidia/nemotron-3-ultra-550b-a55b",
        "provider":    "nvidia",
        "file_tag":    "NVIDIA_Nemotron_3_Ultra",
        "description": "Nemotron 3 Ultra 550B A55B via NVIDIA",
        "enabled":     False
    },
    "nvidia_gpt_oss_20b": {
        "name":        "openai/gpt-oss-20b",
        "provider":    "nvidia",
        "file_tag":    "NVIDIA_GPT_OSS_20B",
        "description": "GPT-OSS 20B via NVIDIA",
        "enabled":     False
    },
    "nvidia_gpt_oss_120b": {
        "name":        "openai/gpt-oss-120b",
        "provider":    "nvidia",
        "file_tag":    "NVIDIA_GPT_OSS_120B",
        "description": "GPT-OSS 120B via NVIDIA",
        "enabled":     False
    }

}


# ── Call Gemini ───────────────────────────────────────────────────

def call_gemini(model_name: str, prompt: str):
    from google import genai
    from google.genai import types

    client   = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
    response = client.models.generate_content(
        model    = model_name,
        contents = prompt,
        config   = types.GenerateContentConfig(
            temperature = 0,   # deterministic output — better for evaluation
        )
    )
    return response.text



# ── Call Groq ─────────────────────────────────────────────────────

def call_groq(model_name: str, prompt: str):
    from groq import Groq

    client   = Groq(api_key=os.getenv("GROQ_API_KEY"))
    response = client.chat.completions.create(
        model    = model_name,
        messages = [{"role": "user", "content": prompt}]
    )

    return response.choices[0].message.content


def call_nvidia(model_name: str, prompt: str):
    from openai import OpenAI

    client = OpenAI(
        api_key=os.getenv("NVIDIA_API_KEY"),
        base_url="https://integrate.api.nvidia.com/v1",
        timeout=120.0
    )

    kwargs = {
        "model": model_name,
        "messages": [
            {
                "role": "user",
                "content": prompt
            }
        ],
        "max_tokens": 4096,
        "stream": False
    }

    if model_name == "openai/gpt-oss-20b":
        kwargs["reasoning_effort"] = "low"

    elif model_name == "deepseek-ai/deepseek-v4-flash-0731":
        kwargs["extra_body"] = {
            "chat_template_kwargs": {
                "thinking": False
            }
        }

    elif model_name == "deepseek-ai/deepseek-v4-pro-0813":
        kwargs["reasoning_effort"] = "none"

    elif model_name == "google/gemma-4-31b-it":
        kwargs["extra_body"] = {
            "chat_template_kwargs": {
                "enable_thinking": False
            }
    }


    response = client.chat.completions.create(**kwargs)

    return response.choices[0].message.content



# ── Main Call Function ────────────────────────────────────────────

def call_cloud_model(model_key: str, instruction: str, prompt_template: str):
    from models.ollama_models import parse_output

    entry = CLOUD_MODELS.get(model_key)

    if not entry:
        raise ValueError(f"Model key '{model_key}' not found in CLOUD_MODELS")
    if not entry["enabled"]:
        raise ValueError(f"Model '{model_key}' is disabled")

    prompt   = prompt_template.replace("{instruction}", instruction)
    start    = time.time()
    provider = entry["provider"]

    try:
        if provider == "gemini":
            time.sleep(4)  
            raw = call_gemini(entry["name"], prompt)
        elif provider == "groq":
            raw = call_groq(entry["name"], prompt)
        elif provider == "nvidia":
            raw = call_nvidia(entry["name"], prompt)
        else:
            raise ValueError(f"Unknown provider: {provider}")

    except Exception as e:
        # Return failed result instead of crashing entire run
        print(f"  ⚠️  API error: {str(e)[:80]}")
        return False, [], round(time.time() - start, 2), None

    latency      = round(time.time() - start, 2)
    valid, steps = parse_output(raw)

    return valid, steps, latency, raw


# ── Utilities ─────────────────────────────────────────────────────
def get_enabled_cloud_models():
    return [key for key, e in CLOUD_MODELS.items() if e["enabled"]]

def get_cloud_file_tag(model_key: str):
    return CLOUD_MODELS[model_key]["file_tag"]


def print_cloud_registry():
    print("\n☁️  Cloud Models:")
    print("-" * 60)
    for key, entry in CLOUD_MODELS.items():
        status = "✅ enabled" if entry["enabled"] else "⏸️  disabled"
        print(f"  {key:<20} {status}   {entry['name']}")
        print(f"  {'':20} tag: {entry['file_tag']}")
        print(f"  {'':20} {entry['description']}\n")
