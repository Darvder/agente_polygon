import os, json, asyncio
from groq import AsyncGroq

GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")
cliente_llm = AsyncGroq(api_key=GROQ_API_KEY)

PROMPT_TEMPLATE = "Eres un analista cuantitativo experto en mercados de predicción. Estima la probabilidad REAL del evento usando base rates. NO ancles al precio del mercado automáticamente.\n\nMercado: {pregunta}\nPrecio mercado: {precio:.1%}\nDías restantes: {dias}\nSpread: {spread:.1%}\nNoticias: Sin noticias recientes.\n\nRESPONDE SOLO JSON: {{\"estimacion\": 50, \"confianza\": 0.50, \"hay_noticia\": false, \"razonamiento\": \"...\"}}"

MERCADOS_TEST = [
    {"pregunta": "Will Bitcoin reach $150,000 by end of 2026?",   "mid_price": 0.38, "dias": 110, "spread": 0.03},
    {"pregunta": "Will the Fed cut rates in November 2026?",       "mid_price": 0.55, "dias": 60,  "spread": 0.02},
    {"pregunta": "Will Apple become the first $5T company?",       "mid_price": 0.25, "dias": 300, "spread": 0.03},
    {"pregunta": "Will Elon Musk remain CEO of Tesla in 2027?",    "mid_price": 0.70, "dias": 450, "spread": 0.04},
]

async def test():
    print(f"GROQ KEY: {'OK' if GROQ_API_KEY else 'FALTA'}")
    for m in MERCADOS_TEST:
        prompt = PROMPT_TEMPLATE.format(**m)
        try:
            msg = await cliente_llm.chat.completions.create(
                model="openai/gpt-oss-120b", temperature=0.0,
                messages=[{"role":"user","content":prompt}],
                max_tokens=200, response_format={"type": "json_object"}
            )
            an = json.loads(msg.choices[0].message.content.strip())
            est = float(an.get("estimacion", m["mid_price"]*100))
            if est > 1.0: est /= 100.0
            conf = float(an.get("confianza", 0.5))
            diff = est - m["mid_price"]
            edge = round(abs(diff) - m["spread"], 4)
            ok = edge >= 0.02 and conf >= 0.50
            print(f"{'OK' if ok else 'NO'} | {m['pregunta'][:50]} | mkt={m['mid_price']:.0%} llm={est:.0%} edge={edge:.2%} conf={conf:.2f}")
        except Exception as e:
            print(f"ERROR: {e}")

asyncio.run(test())
