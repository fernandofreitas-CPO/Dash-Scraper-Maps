# Dashboard de Prospecção para Restaurantes em Manaus

Projeto full-stack para diagnóstico de presença digital (Site, Google Meu Negócio e Contato), com processamento de planilha e insights comerciais.

## Stack

- Backend: FastAPI + Pandas
- Frontend: React (Vite) + Tailwind CSS + Lucide React
- IA: OpenAI API (com fallback local) + Serper.dev (maps snapshot)

## Colunas esperadas da planilha

- Nome
- Endereco (ou Endereço)
- Telefone
- Website
- Estrelas_Google
- Numero_Avaliacoes
- Bairro

## 1) Rodar Backend

```bash
cd .
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
uvicorn main:app --reload --port 8000
```

Backend em: `http://localhost:8000`

Healthcheck: `http://localhost:8000/api/health`

## 2) Rodar Frontend

```bash
cd .
npm install
npm run dev
```

Frontend em: `http://localhost:5173`

## Variáveis de ambiente

Use `.env` (backend) e `.env.local` (frontend) se quiser separar:

```env
OPENAI_API_KEY=...
OPENAI_MODEL=gpt-4o-mini
SERPER_API_KEY=...
VITE_API_BASE_URL=http://localhost:8000/api
```

## Integrações IA

- Sem chave OpenAI: sistema usa recomendações por regra local.
- Com OpenAI: gera melhorias GMN, pitch de site e mensagem de WhatsApp personalizada.
- Com Serper: tenta enriquecer rating/reviews/posição no Maps por restaurante.

## Funcionalidades principais

- Upload CSV/XLSX
- Filtro por bairro
- Cards com status colorido
- Classificação de oportunidade (Ouro, Prata, Bronze)
- Pitch comercial para restaurantes sem site ou com baixo score
- Botão de WhatsApp com mensagem pronta
- Botão de relatório PDF com geração real no backend

## Endpoints de PDF

- `GET /api/report/{restaurant_id}`: gera PDF individual de um restaurante
- `GET /api/report?bairro=Adrianopolis`: gera PDF consolidado por filtro
- `GET /api/report`: gera PDF consolidado de todos os bairros
