# Status Empresarial por CUIT

Genera informes de status empresarial a partir de un CUIT (solo personas jurídicas).

## Requisitos

- Python 3.11+
- Cuenta de Supabase (PostgreSQL + Storage + Auth)
- API key de Anthropic

## Instalación

```bash
git clone [repo]
cd Twiter/backend
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env         # completar las variables
```

## Cómo correr

```bash
# Backend (desde backend/)
uvicorn main:app --reload

# Tests
pytest

# Chequeo de salud
curl http://localhost:8000/health   # -> {"status": "ok"}
```
