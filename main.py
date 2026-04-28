import io
import json
import os
import re
from datetime import datetime
from typing import Any, Dict, List, Optional

import pandas as pd
import requests
from bs4 import BeautifulSoup
from fastapi import FastAPI, File, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

try:
    from openai import OpenAI
except ImportError:
    OpenAI = None


EXPECTED_COLUMNS = [
    "Nome",
    "Endereco",
    "Telefone",
    "Website",
    "Estrelas_Google",
    "Numero_Avaliacoes",
    "Bairro",
]

COLUMN_ALIASES = {
    "Nome": ["nome", "name", "business_name", "title"],
    "Endereco": ["endereco", "endereço", "address", "location", "full_address"],
    "Telefone": ["telefone", "phone", "whatsapp", "contact_phone", "mobile"],
    "Website": ["website", "site", "url", "domain", "web"],
    "Estrelas_Google": ["estrelas_google", "rating", "stars", "google_rating", "nota_google"],
    "Numero_Avaliacoes": [
        "numero_avaliacoes",
        "numero_de_avaliacoes",
        "reviews",
        "review_count",
        "rating_count",
        "google_reviews",
    ],
    "Bairro": ["bairro", "district", "neighborhood", "region"],
}

MANAUS_BAIRROS = [
    "Adrianopolis",
    "Vieiralves",
    "Ponta Negra",
    "Centro",
    "Flores",
    "Cachoeirinha",
    "Cidade Nova",
    "Dom Pedro",
    "Parque Dez",
    "Aleixo",
]

app = FastAPI(title="Dashboard de Prospeccao - Manaus")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Cache simples para ambiente local de prototipo.
RESTAURANTS_CACHE: List[Dict[str, Any]] = []


def extract_json_block(raw_text: str) -> Optional[Dict[str, Any]]:
    text = raw_text.strip()
    if not text:
        return None


def slugify_filename(value: str) -> str:
    clean = re.sub(r"[^a-zA-Z0-9_-]+", "-", (value or "relatorio").strip())
    clean = clean.strip("-")
    return clean[:60] or "relatorio"


def write_pdf_header(pdf: canvas.Canvas, title: str, subtitle: str) -> int:
    width, height = A4
    y = height - 50
    pdf.setFont("Helvetica-Bold", 16)
    pdf.drawString(40, y, title)
    y -= 18
    pdf.setFont("Helvetica", 10)
    pdf.drawString(40, y, subtitle)
    y -= 20
    pdf.line(40, y, width - 40, y)
    return y - 20


def draw_wrapped_text(pdf: canvas.Canvas, text: str, x: int, y: int, max_chars: int = 95) -> int:
    text = text or "-"
    words = text.split()
    lines: List[str] = []
    current = ""

    for word in words:
        candidate = f"{current} {word}".strip()
        if len(candidate) <= max_chars:
            current = candidate
        else:
            lines.append(current)
            current = word

    if current:
        lines.append(current)

    for line in lines:
        pdf.drawString(x, y, line)
        y -= 14

    return y


def build_restaurant_report_pdf(restaurant: Dict[str, Any]) -> io.BytesIO:
    buffer = io.BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=A4)
    y = write_pdf_header(
        pdf,
        title=f"Relatorio de Presenca Digital - {restaurant.get('nome', 'Restaurante')}",
        subtitle=f"Gerado em {datetime.now().strftime('%d/%m/%Y %H:%M')}",
    )

    pdf.setFont("Helvetica-Bold", 12)
    pdf.drawString(40, y, "Resumo do Estabelecimento")
    y -= 20

    pdf.setFont("Helvetica", 10)
    y = draw_wrapped_text(pdf, f"Nome: {restaurant.get('nome', '-')}", 40, y)
    y = draw_wrapped_text(pdf, f"Endereco: {restaurant.get('endereco', '-')}", 40, y)
    y = draw_wrapped_text(pdf, f"Bairro: {restaurant.get('bairro', '-')}", 40, y)
    y = draw_wrapped_text(pdf, f"Telefone: {restaurant.get('telefone', '-')}", 40, y)
    y = draw_wrapped_text(pdf, f"Website: {restaurant.get('website', 'Sem website')}", 40, y)

    y -= 8
    pdf.setFont("Helvetica-Bold", 12)
    pdf.drawString(40, y, "Diagnostico de Site")
    y -= 18
    pdf.setFont("Helvetica", 10)
    site = restaurant.get("site", {})
    y = draw_wrapped_text(pdf, f"Tem website: {'Sim' if site.get('has_website') else 'Nao'}", 40, y)
    y = draw_wrapped_text(pdf, f"Status code: {site.get('status_code', 'N/A')}", 40, y)
    y = draw_wrapped_text(pdf, f"Mobile friendly: {'Sim' if site.get('mobile_friendly') else 'Nao'}", 40, y)
    y = draw_wrapped_text(pdf, f"Score do site: {site.get('score', 0)}/100", 40, y)
    if site.get("pitch"):
        y = draw_wrapped_text(pdf, f"Pitch comercial: {site.get('pitch')}", 40, y)

    y -= 8
    pdf.setFont("Helvetica-Bold", 12)
    pdf.drawString(40, y, "Diagnostico Google Meu Negocio")
    y -= 18
    pdf.setFont("Helvetica", 10)
    gmn = restaurant.get("gmn", {})
    y = draw_wrapped_text(pdf, f"Stars: {gmn.get('stars', 0)} | Avaliacoes: {gmn.get('reviews', 0)}", 40, y)
    y = draw_wrapped_text(pdf, f"Ranking score: {gmn.get('ranking_score', 0)}/100", 40, y)
    y = draw_wrapped_text(pdf, f"Taxa de resposta: {gmn.get('response_rate', '-')}", 40, y)
    y = draw_wrapped_text(pdf, f"Posicao local: {gmn.get('ranking_position', 'Nao mapeado')}", 40, y)

    improvements = gmn.get("improvements", [])
    y -= 4
    pdf.setFont("Helvetica-Bold", 11)
    pdf.drawString(40, y, "3 melhorias recomendadas")
    y -= 16
    pdf.setFont("Helvetica", 10)
    for item in improvements[:3]:
        y = draw_wrapped_text(pdf, f"- {item}", 45, y)

    y -= 8
    pdf.setFont("Helvetica-Bold", 11)
    pdf.drawString(40, y, "Mensagem sugerida para WhatsApp")
    y -= 16
    pdf.setFont("Helvetica", 10)
    draw_wrapped_text(pdf, restaurant.get("whatsapp_message", "-"), 40, y)

    pdf.showPage()
    pdf.save()
    buffer.seek(0)
    return buffer


def build_portfolio_report_pdf(restaurants: List[Dict[str, Any]], bairro: Optional[str]) -> io.BytesIO:
    buffer = io.BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=A4)
    title = "Relatorio Consolidado de Oportunidades"
    area = bairro or "Todos os bairros"
    y = write_pdf_header(
        pdf,
        title=title,
        subtitle=f"Filtro: {area} | Total: {len(restaurants)} | Gerado em {datetime.now().strftime('%d/%m/%Y %H:%M')}",
    )

    pdf.setFont("Helvetica", 10)
    y = draw_wrapped_text(pdf, "Classificacao por oportunidade:", 40, y)
    counts = {"Ouro": 0, "Prata": 0, "Bronze": 0}
    for row in restaurants:
        kind = row.get("oportunidade", "Bronze")
        counts[kind] = counts.get(kind, 0) + 1

    y = draw_wrapped_text(
        pdf,
        f"Ouro: {counts.get('Ouro', 0)} | Prata: {counts.get('Prata', 0)} | Bronze: {counts.get('Bronze', 0)}",
        40,
        y,
    )
    y -= 8

    for restaurant in restaurants:
        if y < 110:
            pdf.showPage()
            y = write_pdf_header(pdf, title=title, subtitle=f"Continua... Filtro: {area}")

        pdf.setFont("Helvetica-Bold", 11)
        y = draw_wrapped_text(
            pdf,
            f"{restaurant.get('nome', '-')} - {restaurant.get('bairro', '-')} [{restaurant.get('oportunidade', 'Bronze')}]",
            40,
            y,
        )

        pdf.setFont("Helvetica", 10)
        gmn = restaurant.get("gmn", {})
        site = restaurant.get("site", {})
        y = draw_wrapped_text(
            pdf,
            f"Site score: {site.get('score', 0)} | Stars: {gmn.get('stars', 0)} | Reviews: {gmn.get('reviews', 0)} | Resposta: {gmn.get('response_rate', '-')}",
            45,
            y,
        )
        top_improvement = (gmn.get("improvements") or ["Sem melhoria mapeada"])[0]
        y = draw_wrapped_text(pdf, f"Prioridade: {top_improvement}", 45, y)
        y -= 6

    pdf.showPage()
    pdf.save()
    buffer.seek(0)
    return buffer

    if text.startswith("```"):
        text = text.strip("`")
        if text.startswith("json"):
            text = text[4:].strip()

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end != -1 and start < end:
            candidate = text[start : end + 1]
            try:
                return json.loads(candidate)
            except json.JSONDecodeError:
                return None
        return None


class UploadResponse(BaseModel):
    total: int
    bairros: List[str]
    data: List[Dict[str, Any]]


class HealthResponse(BaseModel):
    status: str
    server_time: str


def normalize_phone(phone: Any) -> str:
    if pd.isna(phone):
        return ""
    return re.sub(r"\D", "", str(phone))


def extract_contact_numbers(phone: Any) -> List[str]:
    if pd.isna(phone):
        return []

    raw_value = str(phone or "").strip()
    if not raw_value:
        return []

    matches = re.findall(
        r"(?:\+?55\s*)?(?:\(?\d{2}\)?\s*)?(?:9?\d{4}[-.\s]?\d{4})|0800[-.\s]?\d{3}[-.\s]?\d{4}",
        raw_value,
    )

    candidates = [normalize_phone(match) for match in matches if normalize_phone(match)]
    if not candidates:
        normalized = normalize_phone(raw_value)
        candidates = [normalized] if normalized else []

    deduped: List[str] = []
    for candidate in candidates:
        if candidate not in deduped:
            deduped.append(candidate)
    return deduped


def local_phone_digits(phone: str) -> str:
    digits = normalize_phone(phone)
    if digits.startswith("55") and len(digits) in {12, 13}:
        return digits[2:]
    return digits


def format_phone_display(phone: str) -> str:
    digits = local_phone_digits(phone)
    if digits.startswith("0800") and len(digits) == 11:
        return f"0800 {digits[4:7]} {digits[7:]}"
    if len(digits) == 11:
        return f"({digits[:2]}) {digits[2:7]}-{digits[7:]}"
    if len(digits) == 10:
        return f"({digits[:2]}) {digits[2:6]}-{digits[6:]}"
    return digits


def classify_contact_channel(phone: str) -> str:
    digits = local_phone_digits(phone)
    if not digits:
        return "desconhecido"
    if digits.startswith("0800"):
        return "central"
    if len(digits) == 11 and digits[2] == "9":
        return "whatsapp"
    if len(digits) in {10, 11}:
        return "telefone"
    return "desconhecido"


def build_contact_targets(phone: Any, whatsapp_message: str) -> List[Dict[str, str]]:
    targets: List[Dict[str, str]] = []
    for candidate in extract_contact_numbers(phone):
        local_digits = local_phone_digits(candidate)
        status = contact_status(local_digits)
        channel = classify_contact_channel(local_digits)
        action_url = ""

        if channel == "whatsapp" and status == "Ativo":
            action_url = f"https://wa.me/55{local_digits}?text={requests.utils.quote(whatsapp_message)}"
        elif channel in {"telefone", "central"} and status != "Inativo":
            dial_number = local_digits if channel == "central" else f"+55{local_digits}"
            action_url = f"tel:{dial_number}"

        targets.append(
            {
                "numero": local_digits,
                "display": format_phone_display(local_digits),
                "status": status,
                "canal": channel,
                "action_url": action_url,
            }
        )

    return targets


def normalize_column_name(value: str) -> str:
    value = str(value or "").strip().lower()
    replacements = {
        "á": "a",
        "à": "a",
        "â": "a",
        "ã": "a",
        "é": "e",
        "ê": "e",
        "í": "i",
        "ó": "o",
        "ô": "o",
        "õ": "o",
        "ú": "u",
        "ç": "c",
    }
    for source, target in replacements.items():
        value = value.replace(source, target)
    value = re.sub(r"[^a-z0-9]+", "_", value)
    return value.strip("_")


def extract_bairro_from_address(address: str) -> str:
    if not address:
        return ""

    match = re.search(r"-\s*([^,]+),\s*Manaus(?:\s*-\s*AM)?", str(address), flags=re.IGNORECASE)
    if match:
        return match.group(1).strip()

    parts = [part.strip() for part in str(address).split(",") if part.strip()]
    for part in reversed(parts):
        if part.lower() in {"manaus", "amazonas", "brasil", "am"}:
            continue
        if re.search(r"\d{5}-?\d{3}", part):
            continue
        if re.search(r"\b\d+\b", part) and len(part.split()) <= 2:
            continue
        return part
    return ""


def harmonize_spreadsheet_columns(df: pd.DataFrame) -> pd.DataFrame:
    normalized_lookup = {
        normalize_column_name(column): column for column in df.columns
    }

    rename_map: Dict[str, str] = {}
    for target, aliases in COLUMN_ALIASES.items():
        if target in df.columns:
            continue

        for alias in aliases:
            source = normalized_lookup.get(normalize_column_name(alias))
            if source:
                rename_map[source] = target
                break

    if rename_map:
        df = df.rename(columns=rename_map)

    if "Bairro" not in df.columns:
        if "Endereco" in df.columns:
            df["Bairro"] = df["Endereco"].apply(extract_bairro_from_address)
        else:
            df["Bairro"] = ""

    return df


def contact_status(phone: str) -> str:
    digits = local_phone_digits(phone)
    if not digits:
        return "Necessita Validacao"
    if digits.startswith("0800") and len(digits) == 11:
        return "Ativo"
    if len(digits) in {10, 11}:
        return "Ativo"
    if len(digits) < 10:
        return "Inativo"
    return "Necessita Validacao"


def select_primary_contact(targets: List[Dict[str, str]]) -> Dict[str, str]:
    if not targets:
        return {
            "numero": "",
            "display": "",
            "status": "Necessita Validacao",
            "canal": "desconhecido",
            "action_url": "",
        }

    for preferred_channel in ["whatsapp", "telefone", "central"]:
        for target in targets:
            if target["canal"] == preferred_channel and target["status"] == "Ativo":
                return target
    return targets[0]


def filter_restaurants_by_bairro(bairro: Optional[str] = None) -> List[Dict[str, Any]]:
    if not bairro:
        return RESTAURANTS_CACHE

    return [
        item
        for item in RESTAURANTS_CACHE
        if item.get("bairro", "").lower() == bairro.lower()
    ]


def build_contacts_export_csv(restaurants: List[Dict[str, Any]]) -> io.BytesIO:
    csv_buffer = io.StringIO()
    headers = [
        "restaurant_id",
        "nome",
        "bairro",
        "oportunidade",
        "contato_canal",
        "contato_status",
        "telefone",
        "action_url",
        "mensagem_base",
    ]
    csv_buffer.write(",".join(headers) + "\n")

    def escape_csv(value: Any) -> str:
        text = str(value or "")
        text = text.replace('"', '""')
        return f'"{text}"'

    for restaurant in restaurants:
        targets = restaurant.get("contato", {}).get("targets", []) or []
        for target in targets:
            row = [
                restaurant.get("id", ""),
                restaurant.get("nome", ""),
                restaurant.get("bairro", ""),
                restaurant.get("oportunidade", ""),
                target.get("canal", ""),
                target.get("status", ""),
                target.get("display", ""),
                target.get("action_url", ""),
                restaurant.get("whatsapp_message", ""),
            ]
            csv_buffer.write(",".join(escape_csv(item) for item in row) + "\n")

    encoded = io.BytesIO(csv_buffer.getvalue().encode("utf-8-sig"))
    encoded.seek(0)
    return encoded


def safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if pd.isna(value):
            return default
        return float(value)
    except (ValueError, TypeError):
        return default


def safe_int(value: Any, default: int = 0) -> int:
    try:
        if pd.isna(value):
            return default
        return int(float(value))
    except (ValueError, TypeError):
        return default


def check_website_status(url: str) -> Dict[str, Any]:
    if not url:
        return {
            "has_website": False,
            "status_code": None,
            "mobile_friendly": False,
            "score": 0,
            "pitch": "Seu restaurante pode aumentar pedidos com um site rapido, responsivo e integrado ao WhatsApp.",
        }

    normalized_url = url.strip()
    if not normalized_url.startswith(("http://", "https://")):
        normalized_url = f"https://{normalized_url}"

    status_code: Optional[int] = None
    mobile_friendly = False

    try:
        response = requests.get(normalized_url, timeout=6)
        status_code = response.status_code
        if response.ok:
            soup = BeautifulSoup(response.text[:120000], "html.parser")
            viewport = soup.find("meta", attrs={"name": "viewport"})
            mobile_friendly = viewport is not None
    except requests.RequestException:
        status_code = None

    # Score hibrido: saude tecnica + heuristica simples.
    base = 35
    if status_code and 200 <= status_code < 400:
        base += 25
    elif status_code and status_code >= 400:
        base -= 10

    if mobile_friendly:
        base += 20

    # Pequena variacao deterministica para simular avaliacao de UX por IA.
    pseudo_ai_adjust = (abs(hash(normalized_url)) % 21) - 10
    score = max(0, min(100, base + pseudo_ai_adjust))

    pitch = ""
    if score < 50:
        pitch = (
            "Seu restaurante tem potencial de vendas maior: um novo site mobile-first, com cardapio claro e CTA no WhatsApp, "
            "pode converter mais visitas em pedidos."
        )

    return {
        "has_website": True,
        "status_code": status_code,
        "mobile_friendly": mobile_friendly,
        "score": score,
        "pitch": pitch,
    }


def fetch_serper_maps_snapshot(name: str, bairro: str) -> Dict[str, Any]:
    api_key = os.getenv("SERPER_API_KEY")
    if not api_key:
        return {
            "enabled": False,
            "found": False,
            "position": None,
            "stars": None,
            "reviews": None,
        }

    query = f"{name} {bairro} Manaus restaurante"
    url = "https://google.serper.dev/maps"
    headers = {"X-API-KEY": api_key, "Content-Type": "application/json"}
    payload = {"q": query, "hl": "pt", "gl": "br"}

    try:
        response = requests.post(url, headers=headers, json=payload, timeout=8)
        response.raise_for_status()
        data = response.json()

        places = data.get("places", []) if isinstance(data, dict) else []
        if not places:
            return {
                "enabled": True,
                "found": False,
                "position": None,
                "stars": None,
                "reviews": None,
            }

        first = places[0]
        return {
            "enabled": True,
            "found": True,
            "position": safe_int(first.get("position"), default=1),
            "stars": safe_float(first.get("rating"), default=0.0),
            "reviews": safe_int(first.get("ratingCount"), default=0),
        }
    except (requests.RequestException, ValueError):
        return {
            "enabled": True,
            "found": False,
            "position": None,
            "stars": None,
            "reviews": None,
        }


def gmn_diagnostics(stars: float, reviews: int) -> Dict[str, Any]:
    ranking_score = round(((stars / 5.0) * 60) + (min(reviews, 500) / 500 * 40), 2)

    # Simulacao de taxa de resposta baseada no volume de reviews.
    if reviews >= 200:
        response_rate = "Alta"
    elif reviews >= 60:
        response_rate = "Media"
    else:
        response_rate = "Baixa"

    improvements: List[str] = []
    if stars < 4.2:
        improvements.append("Criar rotina de pedido de feedback no pos-venda para elevar nota media.")
    if reviews < 80:
        improvements.append("Aumentar volume de avaliacoes com QR Code em mesa e delivery.")
    if reviews > 0 and stars >= 4.2:
        improvements.append("Destacar pratos campeoes em fotos profissionais no perfil do Google.")
    if response_rate != "Alta":
        improvements.append("Responder avaliacoes em ate 24h para melhorar confianca e ranqueamento local.")

    while len(improvements) < 3:
        improvements.append("Atualizar descricao do GMN com termos locais e bairros de atendimento em Manaus.")

    return {
        "ranking_score": max(0, min(100, ranking_score)),
        "reviews": reviews,
        "stars": stars,
        "response_rate": response_rate,
        "improvements": improvements[:3],
    }


def classify_opportunity(site_score: int, gmn_score: float, has_website: bool) -> str:
    if not has_website or (site_score < 45 and gmn_score >= 60):
        return "Ouro"
    if gmn_score < 55:
        return "Prata"
    return "Bronze"


def is_third_party_menu_link(website: str) -> bool:
    normalized = (website or "").lower()
    if not normalized:
        return False

    known_providers = [
        "menudino",
        "goomer",
        "cardapioweb",
        "anota.ai",
        "ifood.com.br",
        "linktr.ee",
    ]
    return any(provider in normalized for provider in known_providers)


def build_whatsapp_pitch(name: str, bairro: str, stars: float, website: str, site_score: int) -> str:
    bairro_text = bairro or "sua regiao"
    if is_third_party_menu_link(website):
        intro = (
            f"Opa, tudo bem? Vi que voces sao referencia em cafe aqui no {bairro_text}, "
            "mas notei que voces ainda usam link de terceiros (tipo MenuDino/Goomer) no Instagram."
        )
    else:
        intro = (
            f"Opa, tudo bem? Vi que voces sao referencia em cafe aqui no {bairro_text}, "
            "mas notei que o link atual de voces no Instagram ainda depende de plataforma de terceiros."
        )

    return (
        f"{intro} "
        "Como eu sou programador, fiz um scan tecnico e vi que esse link atual esta 'escondendo' voces do Google. "
        "Quem busca por cafe na regiao acaba caindo na concorrencia porque o link de voces nao ranqueia. "
        "Eu desenvolvo sites de alta conversao que sao seus, sem taxas, e que colocam voces no topo das buscas em Manaus. "
        "Bora transformar esse cardapio numa maquina de vendas de verdade?"
    )


def ai_enrich_restaurant(
    name: str,
    bairro: str,
    stars: float,
    reviews: int,
    has_website: bool,
    site_score: int,
    mobile_friendly: bool,
    response_rate: str,
) -> Dict[str, Any]:
    default_result = {
        "provider": "rule-based",
        "improvements": [
            "Padronizar respostas de avaliacoes em ate 24h para melhorar visibilidade local.",
            "Publicar fotos reais de pratos e ambiente 2x por semana no perfil Google.",
            "Criar campanha de incentivo a reviews via WhatsApp pos-entrega.",
        ],
        "site_pitch": "Um site rapido e mobile-first pode aumentar conversoes de delivery e reservas.",
        "whatsapp_message": build_whatsapp_pitch(
            name=name,
            bairro=bairro,
            stars=stars,
            website="" if not has_website else "ok",
            site_score=site_score,
        ),
    }

    api_key = os.getenv("OPENAI_API_KEY")
    model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

    if not api_key or OpenAI is None:
        return default_result

    prompt = (
        "Voce e consultor de SEO local e vendas B2B para restaurantes de Manaus. "
        "Retorne apenas JSON valido com as chaves: improvements (array com 3 strings curtas), "
        "site_pitch (string), whatsapp_message (string persuasiva, ate 280 caracteres). "
        "Considere estes dados: "
        f"nome={name}, bairro={bairro}, estrelas={stars:.1f}, reviews={reviews}, "
        f"tem_site={has_website}, site_score={site_score}, mobile_friendly={mobile_friendly}, "
        f"taxa_resposta={response_rate}."
    )

    try:
        client = OpenAI(api_key=api_key)
        completion = client.chat.completions.create(
            model=model,
            temperature=0.35,
            messages=[
                {"role": "system", "content": "Responda sempre em portugues do Brasil."},
                {"role": "user", "content": prompt},
            ],
        )
        text = completion.choices[0].message.content or ""
        parsed = extract_json_block(text)
        if not parsed:
            return default_result

        improvements = parsed.get("improvements", [])
        if not isinstance(improvements, list):
            improvements = []

        site_pitch = str(parsed.get("site_pitch", default_result["site_pitch"]))[:400]
        whatsapp_message = str(parsed.get("whatsapp_message", default_result["whatsapp_message"]))[:320]

        return {
            "provider": "openai",
            "improvements": [str(item) for item in improvements][:3] or default_result["improvements"],
            "site_pitch": site_pitch,
            "whatsapp_message": whatsapp_message,
        }
    except Exception:
        return default_result


def process_row(row: pd.Series, idx: int) -> Dict[str, Any]:
    name = str(row.get("Nome", "")).strip()
    address = str(row.get("Endereco", "")).strip()
    raw_phone = row.get("Telefone", "")
    website = str(row.get("Website", "")).strip()
    stars = safe_float(row.get("Estrelas_Google", 0))
    reviews = safe_int(row.get("Numero_Avaliacoes", 0))
    bairro = str(row.get("Bairro", "")).strip()

    site_data = check_website_status(website)

    serper_data = fetch_serper_maps_snapshot(name=name, bairro=bairro)
    if serper_data.get("found"):
        if serper_data.get("stars"):
            stars = serper_data["stars"]
        if serper_data.get("reviews"):
            reviews = serper_data["reviews"]

    gmn_data = gmn_diagnostics(stars=stars, reviews=reviews)
    gmn_data["ranking_position"] = serper_data.get("position")
    gmn_data["source"] = "serper" if serper_data.get("found") else "planilha"

    opportunity = classify_opportunity(
        site_score=site_data["score"],
        gmn_score=gmn_data["ranking_score"],
        has_website=site_data["has_website"],
    )

    ai_data = ai_enrich_restaurant(
        name=name,
        bairro=bairro,
        stars=stars,
        reviews=reviews,
        has_website=site_data["has_website"],
        site_score=site_data["score"],
        mobile_friendly=site_data["mobile_friendly"],
        response_rate=gmn_data["response_rate"],
    )

    gmn_data["improvements"] = ai_data["improvements"]

    if not site_data["has_website"] or site_data["score"] < 50:
        site_data["pitch"] = ai_data["site_pitch"]

    whatsapp_message = build_whatsapp_pitch(
        name=name,
        bairro=bairro,
        stars=stars,
        website=website,
        site_score=site_data["score"],
    )
    use_ai_whatsapp = os.getenv("USE_AI_WHATSAPP_PITCH", "false").lower() == "true"
    if use_ai_whatsapp and ai_data.get("whatsapp_message"):
        whatsapp_message = ai_data["whatsapp_message"]

    contact_targets = build_contact_targets(raw_phone, whatsapp_message)
    primary_contact = select_primary_contact(contact_targets)

    return {
        "id": idx,
        "nome": name,
        "endereco": address,
        "telefone": primary_contact["numero"],
        "website": website,
        "bairro": bairro,
        "site": site_data,
        "gmn": gmn_data,
        "contato": {
            "status": primary_contact["status"],
            "telefone": primary_contact["numero"],
            "telefone_display": primary_contact["display"],
            "canal": primary_contact["canal"],
            "action_url": primary_contact["action_url"],
            "targets": contact_targets,
            "total_targets": len(contact_targets),
        },
        "oportunidade": opportunity,
        "whatsapp_message": whatsapp_message,
        "integrations": {
            "openai": ai_data["provider"] == "openai",
            "serper": bool(serper_data.get("enabled")),
        },
    }


def read_spreadsheet(file_name: str, content: bytes) -> pd.DataFrame:
    lower = file_name.lower()
    if lower.endswith(".csv"):
        return pd.read_csv(io.BytesIO(content))
    if lower.endswith(".xlsx") or lower.endswith(".xls"):
        return pd.read_excel(io.BytesIO(content))
    raise HTTPException(status_code=400, detail="Formato invalido. Envie CSV ou XLSX.")


@app.get("/api/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(status="ok", server_time=datetime.utcnow().isoformat())


@app.post("/api/upload", response_model=UploadResponse)
async def upload_spreadsheet(file: UploadFile = File(...)) -> UploadResponse:
    content = await file.read()
    df = read_spreadsheet(file.filename or "", content)

    df = harmonize_spreadsheet_columns(df)

    missing = [col for col in EXPECTED_COLUMNS if col not in df.columns]
    if missing:
        raise HTTPException(
            status_code=400,
            detail=f"Colunas obrigatorias ausentes: {', '.join(missing)}",
        )

    processed = [process_row(row, idx) for idx, (_, row) in enumerate(df.iterrows(), start=1)]

    global RESTAURANTS_CACHE
    RESTAURANTS_CACHE = processed

    bairros = sorted({item.get("bairro", "") for item in processed if item.get("bairro")})

    return UploadResponse(total=len(processed), bairros=bairros, data=processed)


@app.get("/api/restaurants")
def list_restaurants(bairro: Optional[str] = Query(default=None)) -> Dict[str, Any]:
    filtered = filter_restaurants_by_bairro(bairro)

    return {
        "total": len(filtered),
        "data": filtered,
    }


@app.get("/api/bairros")
def list_bairros() -> Dict[str, Any]:
    source = {item.get("bairro", "") for item in RESTAURANTS_CACHE if item.get("bairro")}
    source.update(MANAUS_BAIRROS)
    bairros = sorted(b for b in source if b)
    return {"bairros": bairros}


@app.get("/api/ai-suggestion/{restaurant_id}")
def ai_suggestion(restaurant_id: int) -> Dict[str, Any]:
    target = next((item for item in RESTAURANTS_CACHE if item["id"] == restaurant_id), None)
    if not target:
        raise HTTPException(status_code=404, detail="Restaurante nao encontrado")

    openai_key = os.getenv("OPENAI_API_KEY")
    serper_key = os.getenv("SERPER_API_KEY")

    ai_data = ai_enrich_restaurant(
        name=target["nome"],
        bairro=target["bairro"],
        stars=safe_float(target.get("gmn", {}).get("stars"), 0.0),
        reviews=safe_int(target.get("gmn", {}).get("reviews"), 0),
        has_website=bool(target.get("site", {}).get("has_website")),
        site_score=safe_int(target.get("site", {}).get("score"), 0),
        mobile_friendly=bool(target.get("site", {}).get("mobile_friendly")),
        response_rate=str(target.get("gmn", {}).get("response_rate", "Baixa")),
    )

    recommendation = " ".join(ai_data["improvements"])

    return {
        "restaurant_id": restaurant_id,
        "integration_hint": {
            "openai_configured": bool(openai_key),
            "serper_configured": bool(serper_key),
        },
        "provider": ai_data["provider"],
        "site_pitch": ai_data["site_pitch"],
        "whatsapp_message": ai_data["whatsapp_message"],
        "recommendation": recommendation,
    }


@app.get("/api/report/{restaurant_id}")
def generate_restaurant_report(restaurant_id: int) -> StreamingResponse:
    target = next((item for item in RESTAURANTS_CACHE if item["id"] == restaurant_id), None)
    if not target:
        raise HTTPException(status_code=404, detail="Restaurante nao encontrado")

    pdf_buffer = build_restaurant_report_pdf(target)
    filename = slugify_filename(target.get("nome", "restaurante"))
    headers = {"Content-Disposition": f'attachment; filename="relatorio-{filename}.pdf"'}
    return StreamingResponse(pdf_buffer, media_type="application/pdf", headers=headers)


@app.get("/api/report")
def generate_portfolio_report(bairro: Optional[str] = Query(default=None)) -> StreamingResponse:
    target = filter_restaurants_by_bairro(bairro)

    if not target:
        raise HTTPException(status_code=404, detail="Nenhum restaurante encontrado para gerar relatorio")

    pdf_buffer = build_portfolio_report_pdf(target, bairro=bairro)
    label = slugify_filename(bairro) if bairro else "manaus"
    headers = {"Content-Disposition": f'attachment; filename="relatorio-consolidado-{label}.pdf"'}
    return StreamingResponse(pdf_buffer, media_type="application/pdf", headers=headers)


@app.get("/api/contacts/export")
def export_contacts_csv(bairro: Optional[str] = Query(default=None)) -> StreamingResponse:
    target = filter_restaurants_by_bairro(bairro)
    if not target:
        raise HTTPException(status_code=404, detail="Nenhum restaurante encontrado para exportar contatos")

    csv_buffer = build_contacts_export_csv(target)
    label = slugify_filename(bairro) if bairro else "manaus"
    headers = {"Content-Disposition": f'attachment; filename="cadencia-contatos-{label}.csv"'}
    return StreamingResponse(csv_buffer, media_type="text/csv", headers=headers)
