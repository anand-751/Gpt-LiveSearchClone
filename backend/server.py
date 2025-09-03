import os
import time
import requests
import json
from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.common.exceptions import TimeoutException, WebDriverException

# === CONFIG ===
load_dotenv()
SERPAPI_KEY = os.getenv("SERPAPI_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

if not SERPAPI_KEY:
    raise RuntimeError("SERPAPI_KEY environment variable not set")
if not GEMINI_API_KEY:
    raise RuntimeError("GEMINI_API_KEY environment variable not set")

app = FastAPI(title="Realtime AI Scraper API")

# === CORS Setup ===
origins = [
    "https://anand-751.github.io",
    "https://anand-751.github.io/Ai-ChatBot",
    "http://localhost:5173"
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# === Utilities ===
def is_valid_text(text):
    return text and len(text.strip()) > 0 and not text.strip().startswith("By ")

def get_links_from_serpapi(query, api_key, max_results=5):
    params = {
        "engine": "google",
        "q": query,
        "api_key": api_key,
        "num": max_results,
        "gl": "IN",
        "hl": "en",
        "location": "India",
    }
    try:
        resp = requests.get("https://serpapi.com/search.json", params=params, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        return [r.get("link") for r in data.get("organic_results", [])[:max_results] if r.get("link")]
    except Exception:
        return []

def scrape_links(links, load_timeout=7):
    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920,1080")
    driver = webdriver.Chrome(options=options)
    driver.set_page_load_timeout(load_timeout)

    extracted = ""

    for url in links:
        try:
            driver.get(url)
            time.sleep(3)
        except (TimeoutException, WebDriverException):
            continue

        try:
            elems = driver.find_elements(By.XPATH, "//h1 | //h2 | //h3 | //p | //a")
            for el in elems:
                tag = el.tag_name.lower()
                text = el.text.strip()
                if tag == "a":
                    href = el.get_attribute("href")
                    if text and href:
                        extracted += f"[{text}]({href})\n"
                elif is_valid_text(text):
                    extracted += text + "\n"
        except:
            continue

        # Cafe-specific scraping
        try:
            cafes = driver.find_elements(By.CLASS_NAME, "sc-1q7bklc-10")
            for cafe in cafes:
                name = cafe.find_element(By.CLASS_NAME, "sc-1hp8d8a-0").text.strip() if cafe.find_elements(By.CLASS_NAME, "sc-1hp8d8a-0") else ""
                category = cafe.find_element(By.CLASS_NAME, "fSxdnq").text.strip() if cafe.find_elements(By.CLASS_NAME, "fSxdnq") else ""
                price = cafe.find_element(By.CLASS_NAME, "KXcjT").text.strip() if cafe.find_elements(By.CLASS_NAME, "KXcjT") else ""
                if name or category or price:
                    extracted += f"\nName: {name}\nCategory: {category}\nPrice for two: {price}\n"
        except:
            continue

        # Additional selectors
        try:
            names = driver.find_elements(By.CSS_SELECTOR, "h3.jsx-7cbb814d75c86232.resultbox_title_anchor")
            ratings = driver.find_elements(By.CSS_SELECTOR, "li.resultbox_totalrate")
            addresses = driver.find_elements(By.CSS_SELECTOR, "div.locatcity")

            for i in range(len(names)):
                name = names[i].text.strip() if i < len(names) else ""
                rating = ratings[i].text.strip() if i < len(ratings) else ""
                address = addresses[i].text.strip() if i < len(addresses) else ""

                if name or rating or address:
                    extracted += f"\nName: {name}\nRating: {rating}\nAddress: {address}\n"
        except:
            continue

        # Tables
        try:
            tables = driver.find_elements(By.TAG_NAME, "table")
            for table in tables:
                rows = table.find_elements(By.TAG_NAME, "tr")
                for row in rows:
                    cells = row.find_elements(By.TAG_NAME, "th") + row.find_elements(By.TAG_NAME, "td")
                    texts = [cell.text.strip() for cell in cells]
                    if any(texts):
                        extracted += "\t".join(texts) + "\n"
        except:
            continue

    driver.quit()
    return extracted

def query_gemini(user_question, scraped_text, api_key):
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={api_key}"
    headers = {"Content-Type": "application/json"}
    prompt = (
        "You are an AI assistant helping the user answer a question using only the provided web data. "
        "If no relevant content is found, use your own intelligence.\n\n"
        "Give verbose output to the user"
        "=== Scraped Web Content Start ===\n"
        f"{scraped_text}\n"
        "=== Scraped Web Content End ===\n\n"
        f"User's question: {user_question}\n"
        "- Don't give reference to the source.\n"
        "- If no data, answer naturally.\n"
    )
    payload = {"contents": [{"parts": [{"text": prompt}]}]}
    try:
        resp = requests.post(url, headers=headers, data=json.dumps(payload))
        if resp.status_code == 200:
            data = resp.json()
            return data["candidates"][0]["content"]["parts"][0]["text"].strip()
        return f"❌ Gemini Error: {resp.status_code}"
    except Exception as e:
        return f"❌ Gemini request failed: {e}"
    
@app.post("/api/gemini")
async def generate_gemini_answer(request: Request):
    data = await request.json()
    question = data.get("question", "")
    if not question:
        return JSONResponse({"answer": "⚠️ Missing 'question' in request."}, status_code=400)

    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={GEMINI_API_KEY}"
    headers = {"Content-Type": "application/json"}
    payload = {
        "contents": [
            {"parts": [{"text": question}]}
        ]
    }

    try:
        resp = requests.post(url, headers=headers, json=payload, timeout=20)
        resp.raise_for_status()
        data = resp.json()
        answer = data["candidates"][0]["content"]["parts"][0]["text"].strip()
        return {"answer": answer}
    except Exception as e:
        return {"answer": f"❌ Gemini request failed: {e}"}


# === Routes ===
@app.get("/")
async def home():
    return {"message": "✅ FastAPI backend is working! POST to /api/realtime"}

@app.post("/api/realtime")
async def handle_query(request: Request):
    data = await request.json()
    question = data.get("question", "")
    if not question:
        return JSONResponse({"answer": "⚠️ Missing 'question' in request."}, status_code=400)

    links = get_links_from_serpapi(question, SERPAPI_KEY)
    if not links:
        return {"answer": "❌ No search results found."}

    scraped = scrape_links(links)
    if not scraped.strip():
        return {"answer": "❌ No content extracted from search results."}

    answer = query_gemini(question, scraped, GEMINI_API_KEY)
    return {"answer": answer}
