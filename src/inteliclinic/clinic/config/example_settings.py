"""Example clinic settings — for documentation and testing only.

This file shows what a typical per-clinic configuration looks like.
DO NOT use these values in production.

For a real deploy:
    1. Copy config/examples/clinic.example.yaml
    2. Fill in real values
    3. Set CLINIC_* environment variables or use .env file

See docs/clinic-onboarding/new-clinic.md for the full onboarding guide.
"""

EXAMPLE_CLINIC_CONFIG = {
    # Identity
    "CLINIC_ID": "clinica_exemplo_sp",
    "CLINIC_NAME": "Clínica Exemplo Saúde",
    "CLINIC_SHORT_NAME": "Clínica Exemplo",
    "CLINIC_CNPJ": "00.000.000/0001-00",
    "CLINIC_DOMAIN": "bot.clinicaexemplo.com.br",
    "CLINIC_TIMEZONE": "America/Sao_Paulo",
    "CLINIC_LANGUAGE": "pt-BR",

    # Contact
    "CLINIC_PHONE": "(11) 0000-0000",
    "CLINIC_ADDRESS": "Rua Exemplo, 123, Sala 45",
    "CLINIC_CITY": "São Paulo",
    "CLINIC_STATE": "SP",

    # Features
    "CLINIC_FEATURE_SCHEDULING": True,
    "CLINIC_FEATURE_INSURANCE_QUERY": True,
    "CLINIC_FEATURE_FINANCIAL": False,
    "CLINIC_FEATURE_GLOSA_DETECTION": False,

    # AI
    "CLINIC_LLM_PROVIDER": "openai",
    "CLINIC_LLM_MODEL": "gpt-4o-mini",
    "CLINIC_MIN_CONFIDENCE": 0.65,

    # RAG
    "CLINIC_QDRANT_URL": "http://localhost:6333",
    "CLINIC_RAG_TOP_K": 5,
    "CLINIC_RAG_MIN_SCORE": 0.70,

    # Business hours
    "CLINIC_BUSINESS_HOURS_START": "08:00",
    "CLINIC_BUSINESS_HOURS_END": "18:00",
    "CLINIC_BUSINESS_DAYS": [1, 2, 3, 4, 5],

    # Insurance
    "CLINIC_ACCEPTED_INSURANCES": ["Unimed", "Bradesco Saúde", "Amil"],
    "CLINIC_ACCEPTS_PRIVATE": True,

    # Branding
    "CLINIC_CHATBOT_NAME": "Ana",
    "CLINIC_CHATBOT_GREETING": "Olá! Sou a Ana, assistente virtual da {clinic_name}. Como posso ajudá-lo?",
    "CLINIC_PRIMARY_COLOR": "#0066CC",
}
