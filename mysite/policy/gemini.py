import fitz  # PyMuPDF
import re
import requests
import time

API_KEY = "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"
MODEL = "mistralai/mistral-small-3.2-24b-instruct-2506:free"

headers = {
    "Authorization": f"Bearer {API_KEY}",
    "Referer": "http://localhost:8000",  # Fixed header key (was HTTP-Referer)
    "Content-Type": "application/json",
}

def extract_text(file):
    try:
        with fitz.open(stream=file.read(), filetype="pdf") as doc:
            return " ".join(page.get_text() for page in doc)
    except Exception as e:
        print("❌ PDF read error:", e)
        return ""

def ask_model(prompt):
    try:
        res = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers=headers,
            json={
                "model": MODEL,
                "messages": [
                    {"role": "system", "content": "You are a helpful policy analysis assistant."},
                    {"role": "user", "content": prompt}
                ]
            },
            timeout=30
        )
        data = res.json()
        if 'choices' in data:
            return data['choices'][0]['message']['content'].strip()
        elif 'error' in data:
            print("❌ API error:", data)
            return f"[Error] {data['error']['message']}"
        else:
            print("❌ Unknown response:", data)
            return "[Error] Unknown response structure"
    except Exception as e:
        print("❌ Exception during OpenRouter call:", e)
        return "[Error] Request failed"

def extract_title_and_date(text):
    title_match = re.search(r"cited as the (.*?) Act", text, re.IGNORECASE)
    title = title_match.group(1).strip() + " Act" if title_match else text[:100].split("\n")[0].strip()
    date_match = re.search(
        r"\b\d{1,2}(st|nd|rd|th)?\s+(January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{4}", text)
    date = date_match.group(0) if date_match else "Not specified"
    return title, date

def get_sector_impacts(text):
    sectors = {
        "Banking": "banking sector",
        "Insurance": "insurance sector",
        "Healthcare": "healthcare sector",
        "Legal": "legal sector",
        "Technology": "technology sector",
        "Education": "education sector",
        "Public": "public sector",
        "Environment": "environmental sector",
        "Employment": "employment sector"
    }

    impacts = {}
    for sector, phrase in sectors.items():
        prompt = (
            f"From the following policy document, provide a short professional summary (4–6 lines) "
            f"of how this policy affects the {phrase}. Use only what's stated in the text.\n\n{text[:1500]}"
        )
        ans = ask_model(prompt)
        if ans and "[Error]" not in ans and ans.lower() not in ["not mentioned", "none", "n/a", ""]:
            impacts[sector] = ans
        time.sleep(1)  # Optional: throttle requests to avoid rate limits

    if impacts:
        most_sector = max(impacts.items(), key=lambda x: len(x[1].split()))
        return impacts, most_sector[0], most_sector[1]
    else:
        return {}, "None", "No sector significantly mentioned."

def analyze_policy_pdf(file):
    text = extract_text(file)
    title, date = extract_title_and_date(text)

    summary_prompt = f"Provide a clear professional summary (5–7 lines) for the following policy document.\n\n{text[:2000]}"
    summary = ask_model(summary_prompt)

    affected_prompt = f"From the text, briefly list (in 2–3 lines) which groups, individuals, or sectors are affected by this policy.\n\n{text[:2000]}"
    affected = ask_model(affected_prompt)

    sector_impacts, most_sector, most_text = get_sector_impacts(text)

    return {
        "title": title,
        "date": date,
        "summary": summary,
        "affected": affected,
        "sector_impacts": sector_impacts,
        "most_sector": most_sector,
        "most_text": most_text
    }
