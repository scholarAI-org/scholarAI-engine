import os
import json
import re
import asyncio
import requests
from groq import AsyncGroq, Groq

from Section_Extractor import extract_key_sections
from Compact_JSON_Writer import Compact_List_Encoder

# استيراد كافة المتغيرات من ملف config
import config

# تهيئة الـ Semaphore اعتماداً على القيم من config
primary_semaphore = asyncio.Semaphore(config.PRIMARY_SEMAPHORE_LIMIT)
fallback_semaphore = asyncio.Semaphore(config.FALLBACK_SEMAPHORE_LIMIT)

# تهيئة العملاء
client = Groq(api_key=config.GROQ_API_KEY)
async_client = AsyncGroq(api_key=config.GROQ_API_KEY)

print("API KEY:", config.GROQ_API_KEY is not None)

# --- Functions for fetching  data ---
def fetch_scholarships():
    response = requests.get(config.BACKEND_ENDPOINT, timeout=90)
    response.raise_for_status()
    return response.json()


def clean_html(text):
    if not text:
        return ""
    text = text.replace("\\n", " ")
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def load_and_clean():
    data = fetch_scholarships()  
    for item in data:
        eligibility_text = extract_key_sections(item.get("description", ""))
        item["eligibility_text"] = clean_html(eligibility_text) 
    with open(config.RAW_DATA_FILE, "w", encoding="utf-8") as f:
        f.write(Compact_List_Encoder(data))
    return data

# --- Functions for calling the models ---
async def call_primary(item, semaphore, max_retries=3):
    async with semaphore:
        for attempt in range(max_retries):
            try:
                response = await async_client.chat.completions.create(
                    model=config.PRIMARY_MODEL,
                    max_tokens=1500,
                    reasoning_effort="low",
                    response_format={"type": "json_object"},
                    messages=[
                        {"role": "system", "content": config.SYSTEM_PROMPT},
                        {"role": "user", "content": f"""Scholarship title: {item.get("title", "")}
                        Scholarship eligibility description:{item.get("eligibility_text", "")}
                        """.strip()}] )
                content = response.choices[0].message.content
                extracted = json.loads(content)
                return {"id": item["id"], "title": item.get("title"), "deadline": item.get("deadline"),
                        "model_used": config.PRIMARY_MODEL, **extracted}
            except Exception as e:
                error_str = str(e)
                if attempt < max_retries - 1:
                    match = re.search(r"try again in ([\d.]+)s", error_str)
                    wait_time = float(match.group(1)) + 0.5 if match else 3 * (attempt + 1)
                    await asyncio.sleep(wait_time)
                    continue
                return {"id": item["id"], "error": error_str}
    return {"id": item["id"], "error": "unreachable"}

# --- Function for calling the fallback model --- When the primary model fails, this function is called to attempt extraction using the fallback model. It also implements retry logic in case of transient errors.
async def call_fallback(item, semaphore, max_retries=3):
    async with semaphore:
        for attempt in range(max_retries):
            try:
                response = await async_client.chat.completions.create(
                    model=config.FALLBACK_MODEL,
                    max_tokens=800,
                    response_format={"type": "json_object"},
                    messages=[
                        {"role": "system", "content": config.SYSTEM_PROMPT},
                        {"role": "user", "content": f"""Scholarship title: {item.get("title", "")}
                        Scholarship eligibility description:{item.get("eligibility_text", "")}
                        """.strip()}] )
                content = response.choices[0].message.content
                extracted = json.loads(content)
                return {"id": item["id"], "title": item.get("title"), "deadline": item.get("deadline"),
                        "model_used": config.FALLBACK_MODEL, **extracted}
            except Exception as e:
                error_str = str(e)
                if attempt < max_retries - 1:
                    match = re.search(r"try again in ([\d.]+)s", error_str)
                    wait_time = float(match.group(1)) + 0.5 if match else 3 * (attempt + 1)
                    await asyncio.sleep(wait_time)
                    continue
                return {"id": item["id"], "error": error_str}
    return {"id": item["id"], "error": "unreachable"}

# --- Function for handling fallback logic ---
async def extract_with_fallback(item):
    result = await call_primary(item, primary_semaphore)
    if "error" not in result:
        return result
        
    fallback_result = await call_fallback(item, fallback_semaphore)
    if "error" not in fallback_result:
        return fallback_result
        
    return {"id": item["id"], "title": item.get("title"), "deadline": item.get("deadline"),
            "model_used": None, "error": fallback_result["error"]}

# --- Functions for running the extraction and saving results ---
async def run_all_with_fallback(data):
    results = []
    tasks = [extract_with_fallback(item) for item in data]
    for i, coro in enumerate(asyncio.as_completed(tasks)):
        result = await coro
        results.append(result)
        print(f"[{i+1}/{len(data)}] done - id={result.get('id')} - model={result.get('model_used')}")
        
        results_sorted = sorted(results, key=lambda r: r["id"])
        with open(config.EXTRACTED_FILE, "w", encoding="utf-8") as f:
            json.dump(results_sorted, f, ensure_ascii=False, indent=2)
            
    return results_sorted



async def run_remaining_and_retry(data):
    with open(config.EXTRACTED_FILE, "r", encoding="utf-8") as f:
        existing_results = json.load(f)

    done_ids = {r["id"] for r in existing_results if "error" not in r and r.get("model_used") is not None}
    remaining_data = [item for item in data if item["id"] not in done_ids]

    print(f"Previously successful Scholarships (Remain as is): {len(done_ids)}")
    print(f"Scholarships to be retried (Previous failures + new): {len(remaining_data)}")

    tasks = [extract_with_fallback(item) for item in remaining_data]
    new_results = []
    for i, coro in enumerate(asyncio.as_completed(tasks)):
        result = await coro
        new_results.append(result)
        print(f"[{i+1}/{len(remaining_data)}] done - id={result.get('id')} - model={result.get('model_used')}")

        new_ids = {nr["id"] for nr in new_results}
        combined = [r for r in existing_results if r["id"] not in new_ids] + new_results
        combined_sorted = sorted(combined, key=lambda r: r["id"])
        with open(config.EXTRACTED_FILE, "w", encoding="utf-8") as f:
            json.dump(combined_sorted, f, ensure_ascii=False, indent=2)

    return combined_sorted

if __name__ == "__main__":
    data = load_and_clean()
    results = asyncio.run(run_remaining_and_retry(data))
    failed = [r for r in results if "error" in r]
    print(f"\nfinished: {len(results)} | failed: {len(failed)}")