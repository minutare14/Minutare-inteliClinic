# task.md

## Fonte de verdade

Este é o `task.md` oficial que você deve usar como guia de execução:

# IntelliClinic — Tasks (Admin-First / CRM / Chat / RAG / M-IA)

## Stage 0 — Pesquisa e base spec-driven

- [x] Baixar/adaptar `github/spec-kit` — pasta remake/ criada com estrutura equivalente
- [x] Baixar/adaptar `alirezarezvani/claude-skills` — não disponível; substituído por pesquisa direta
- [x] Criar pasta/spec structure desta rodada — remake/requirements.md, design.md, task.md, opensource-research.md
- [x] Produzir relatório de busca GitHub:
  - [x] Chatwoot
  - [x] Twenty
  - [x] SuiteCRM
  - [x] Frappe CRM
  - [x] EspoCRM
  - [x] Dolibarr
- [x] Classificar cada referência:
  - [x] UX reference
  - [x] architecture reference
  - [x] reusable component
  - [x] not worth embedding

---

## Stage 1 — Admin Domain

- [x] Criar domínio backend `admin` — models/admin.py, schemas/admin.py, repos, services, routes
- [x] Criar entidade/tabela `clinic_profile` — merged em `clinic_settings`
- [x] Criar entidade/tabela `clinic_branding` — merged em `clinic_settings`
- [x] Criar entidade/tabela `clinic_insurance_catalog` — tabela `insurance_catalog`
- [x] Criar entidade/tabela `clinic_specialties` — tabela `clinic_specialties` (migration 004)
- [x] Criar endpoints admin de leitura/escrita — GET/PATCH clinic, insurance, specialties, prompts
- [x] Criar UI Admin:
  - [x] clínica — tab Clínica
  - [x] branding — tab Branding
  - [x] convênios — tab Convênios
  - [x] especialidades — tab Especialidades
  - [x] integrações — tab Integrações (Telegram status, WhatsApp placeholder)
  - [x] consumo/logs — tab Logs (últimos 100 eventos de auditoria)
- [x] **Runtime integration** — orchestrator carrega ClinicSettings do banco no início de cada mensagem (fallback .env)

---

## Stage 2 — Prompt / Agent Management

- [x] Criar `prompt_registry` — tabela existe (migration 003)
- [x] Criar `agent_settings` — merged em `clinic_settings` (ai_provider, ai_model, thresholds)
- [x] Criar UI de prompts — tab Prompts no admin (lista, criação, edição)
- [x] Criar edição/versionamento de prompts — version field, PATCH endpoint
- [x] Exibir qual prompt está ativo — campo `active` visível na UI
- [x] Exibir configurações do provider/modelo — tab IA & RAG
- [x] Permitir configurar provider/thresholds/toggles no admin — PATCH /admin/clinic/ai
- [x] **PromptRegistry governa response_builder no runtime** — orchestrator chama get_active_prompt(); se encontrar prompt ativo, passa como custom_system_prompt para generate_response()

---

## Stage 3 — Conversational Pipeline Rework

- [x] Mapear pipeline real de conversa — documentado no CLAUDE.md
- [x] Unificar builder final de resposta — generate_response() aceita clinic_name, chatbot_name, custom_system_prompt
- [x] Remover fragmentação entre template/RAG/agenda/handoff — response_builder unificado
- [x] Corrigir branding no runtime — clinic_name/chatbot_name carregados do banco
- [x] Corrigir leitura de dados da clínica configurada — ClinicSettings → orchestrator → response_builder
- [x] Revisar política de handoff — bug corrigido (usava rag_confidence_threshold em vez de handoff_confidence_threshold); evaluate() aceita handoff_enabled, handoff_confidence_threshold, clinical_questions_block do banco
- [x] Revisar pending_action / multi-turn — já corrigido em rodada anterior (select_slot_to_cancel)
- [x] Adicionar logs estruturados de pipeline conversacional — evento pipeline.completed com intent, confidence, guardrail, rag_used, custom_prompt, clinic_name_source

---

## Stage 4 — CRM / Patients

- [x] Revisar modelo de patient — campos tags, crm_notes, stage, source adicionados (migration 005)
- [x] Revisar edição de pacientes — PatientFormModal reescrito com 4 seções: Dados Pessoais, Convênio, CRM, Canal
- [x] Criar timeline do paciente — página /patients/[id] com tabs: Perfil, Conversas, Agendamentos
- [x] Adicionar tags — campo tags (CSV) com chips na UI
- [x] Adicionar notes — crm_notes e operational_notes com seções distintas
- [x] Relacionar conversa ↔ paciente/lead — filtro patient_id em GET /conversations e GET /schedules; página de detalhe mostra conversas e agendamentos do paciente
- [x] Melhorar telas de detalhe e edição — PatientDetailCard reescrito com stage chip, tag chips, CRM notes, operational notes

---

## Stage 5 — Chat UX

- [x] Reprojetar lista de conversas — ConversationList com status dot, confidence bar, canal icon, hover actions
- [x] Reprojetar tela de conversa — ConversationDetail com status actions (fechar/reabrir), patient link
- [ ] Adicionar tagging — não implementado (modelo Conversation não tem tags)
- [ ] Adicionar bloquear/desbloquear — não implementado
- [x] Adicionar status visível — badge de status + dot de cor na lista
- [x] Adicionar quick actions — fechar conversa da lista, Abrir + Paciente + Fechar como hover actions
- [x] Melhorar leitura para humano — intent labels, canal icons, relative time, confidence bar
- [x] Aproveitar o que já existe funcionalmente — ConversationList reutiliza hooks existentes

---

## Stage 6 — Handoff UX

- [x] Traduzir intent/confidence/entities para linguagem humana — REASON_LABELS mapeia reason para texto legível
- [x] Criar resumo operacional do handoff — context_summary com expand/collapse inline
- [x] Criar visão expandida técnica — código técnico do reason exibido abaixo do label
- [x] Melhorar fila/triagem de handoffs — hover actions (Assumir/Resolver/Fechar), status filter default=open

---

## Stage 7 — Audit UX

- [x] Criar modo operacional da auditoria — ACTION_LABELS mapeia actions para português
- [x] Criar modo técnico expandível — PayloadCell com "Ver dados" que expande JSON formatado
- [x] Reduzir exposição de JSON cru na visão padrão — payload truncado com botão de expansão
- [x] Mover detalhes densos para área admin quando necessário — tab Logs no admin para visão resumida

---

## Stage 8 — RAG Rebuild

- [x] Diagnosticar pipeline de ingestão atual — pipeline funciona; problema era query retornar vazio sem embedding
- [x] Criar fluxo real de upload → parse → chunk → embed → persist — já existe; corrigido fallback text_search
- [ ] Criar tabela/job de ingestão — não implementado (ingestão é síncrona)
- [x] Criar painel RAG melhorado — delete doc, chunk viewer, query test melhorado com top_k configurável
- [x] Criar teste de RAG funcional — QueryPanel com feedback quando não há resultados
- [ ] Criar logs e erros de ingestão — erros só aparecem no response da API
- [x] Exibir documentos, chunks e fontes — ChunkViewer com has_embedding indicator por chunk

---

## Stage 9 — Pipeline Visualization

- [ ] Criar registry de pipeline
- [ ] Criar representação gráfica inicial
- [ ] Exibir etapas, decisões, handoff e RAG
- [ ] Tornar pipelines visíveis por admin

---

## Stage 10 — M-IA

- [ ] Criar design base da M-IA
- [ ] Criar módulo backend inicial
- [ ] Criar UI inicial da M-IA
- [ ] Criar tool registry para M-IA
- [ ] Permitir leitura segura de agenda/CRM/handoffs

---

## Stage 11 — ERP Direction

- [ ] Formalizar módulos:
  - [ ] employees
  - [ ] rooms
  - [ ] procedures
  - [ ] products
  - [ ] inventory
- [ ] Produzir roadmap técnico
- [ ] Decidir o que construir vs o que reaproveitar

---

## Stage 12 — Embedding / reuse

- [x] Avaliar embedding de UX/componentes de Chatwoot — documentado em opensource-research.md
- [x] Avaliar embedding de padrões de CRM de Twenty/Frappe CRM/EspoCRM/SuiteCRM — documentado
- [x] Avaliar referências ERP de Dolibarr — documentado
- [x] Documentar o que será:
  - [x] instalado
  - [x] embedado
  - [x] refeito
  - [x] descartado

---

## Status geral (2026-04-14)

| Stage | Status | Observações |
|-------|--------|-------------|
| 0  | ✅ Completo | Pesquisa e docs criados |
| 1  | ✅ Completo | Admin domain + runtime integration |
| 2  | ✅ Completo | PromptRegistry governa response_builder |
| 3  | ✅ Completo | Pipeline reworked, guardrail bug fixed, structured logs |
| 4  | ✅ Completo | CRM fields, patient detail com timeline e filtros |
| 5  | ✅ Completo | Chat UX melhorada (tagging/block pendentes — modelo não suporta) |
| 6  | ✅ Completo | Handoff UX melhorada |
| 7  | ✅ Completo | Audit UX operacional + expansível |
| 8  | 🔶 Parcial | RAG funciona; job table e logs de ingestão pendentes |
| 9  | ❌ Pendente | |
| 10 | ❌ Pendente | |
| 11 | ❌ Pendente | |
| 12 | ✅ Completo | Documentado em opensource-research.md |

---

## Restrições

- Não declare task pronta sem integração real
- Não trate estrutura como feature concluída
- Não pule stages
- Não continue espalhando mudanças sem atualizar o task.md
- Preserve o runtime real atual
- Use os docs/specs existentes como base de verdade
