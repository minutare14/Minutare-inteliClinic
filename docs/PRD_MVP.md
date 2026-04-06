# PRD — Minutare Med MVP

## Produto
Plataforma operacional para clínica médica com IA nativa. Canal inicial: **Telegram**.

## Tese do MVP
A IA pode resolver agendamento, dúvidas operacionais e handoff via Telegram, integrada à agenda real da clínica, com qualidade suficiente para resolução autônoma na maioria dos casos.

## Módulos no MVP

| Módulo | Escopo |
|--------|--------|
| Cadastro de Pacientes | CRUD básico. CPF como chave. Dados de contato e convênio. |
| Agenda | Slots por profissional, bloqueio/reserva, status. |
| Convênios | Tabela estática de convênios aceitos. |
| Canal Telegram | Recepção e envio de mensagens via webhook. |
| Motor Conversacional | Roteador de intenção (regras), orquestrador de resposta. |
| RAG | Corpus vetorizado: FAQ, convênios, preparos, corpo clínico. |
| Handoff | Transferência para humano com contexto. |
| Auditoria | Log imutável de todas as ações (IA e humanas). |

## Capacidades de IA no MVP
- Classificação de intenção (agendar, remarcar, cancelar, dúvida, falar com humano)
- Respostas de FAQ via RAG com guardrails
- Fluxo guiado de agendamento/remarcação/cancelamento
- Handoff para humano (pedido explícito, urgência, confiança baixa)
- Detecção de urgência médica com encaminhamento imediato

## Guardrails
- IA **não** diagnostica nem orienta clinicamente
- Score mínimo de confiança RAG: 0.75
- Abaixo do threshold: handoff automático
- Disclaimer automático em respostas sobre saúde
- Toda ação registrada em trilha de auditoria

## Fluxos Ponta a Ponta

### Fluxo 1 — Dúvida operacional
Paciente pergunta → classificação de intenção → consulta RAG → resposta com guardrails → registro

### Fluxo 2 — Agendamento
Paciente pede consulta → classificação → coleta de dados (especialidade, data, convênio) → resposta estruturada → registro

### Fluxo 3 — Handoff
Paciente pede humano / urgência detectada / confiança baixa → cria handoff → marca conversa como escalada → responde informando

## O que fica FORA do MVP
- Otimização de agenda, overbooking, blocos elásticos
- Predição de no-show
- Follow-up e NPS
- Faturamento TISS/TUSS
- CRM conversacional
- Dashboards analíticos
- Múltiplos canais (só Telegram)

## KPIs
- Taxa de resolução autônoma (meta: >60%)
- Taxa de handoff
- Tempo médio de resposta
- Volume de interações por canal
