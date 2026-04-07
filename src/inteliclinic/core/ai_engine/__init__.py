"""AI Engine — Orquestração LangGraph para fluxos de atendimento clínico.

Este módulo contém o grafo principal de orquestração (LangGraph StateGraph),
os nós de processamento (reception, scheduling, insurance, financial, glosa,
supervisor, fallback, response) e o estado compartilhado da sessão clínica.

Cada clínica pode customizar o grafo via GraphConfig, habilitando/desabilitando
nós e ajustando limiares de confiança para handoff humano.
"""
