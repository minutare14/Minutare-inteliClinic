# design.md

# IntelliClinic — Design (Admin-First Rebuild)

## 1. Estratégia geral
A nova fase do IntelliClinic deve migrar o produto de um sistema muito configurado por código/env para um sistema administrável por painel e endpoints admin.

A arquitetura alvo desta rodada é:

- **Infra/segredos** continuam no `.env`
- **Configuração operacional** migra para Admin API + Admin UI
- **Conversação** ganha uma camada única de orquestração e apresentação
- **RAG** ganha pipeline administrável
- **Prompts/agentes** ganham registry visual
- **Pipelines** ganham representação gráfica
- **CRM** evolui para entidade operacional real
- **M-IA** entra como módulo arquitetural formal

---

## 2. Admin Domain

## 2.1 Admin API
Criar um domínio `admin` com responsabilidades:
- clinic profile
- branding
- convênios
- especialidades
- parâmetros operacionais
- integração/consumo/logs
- prompt registry
- agent settings
- pipeline settings
- rag settings

### Endpoints esperados
- `GET /admin/clinic-profile`
- `PATCH /admin/clinic-profile`
- `GET /admin/branding`
- `PATCH /admin/branding`
- `GET /admin/insurance`
- `PATCH /admin/insurance`
- `GET /admin/ai/providers`
- `PATCH /admin/ai/providers`
- `GET /admin/prompts`
- `PATCH /admin/prompts/:id`
- `GET /admin/pipelines`
- `PATCH /admin/pipelines/:id`
- `GET /admin/logs`
- `GET /admin/usage`

---

## 2.2 Admin UI
Criar uma área de admin dedicada com seções:
- Clínica
- Branding
- Convênios
- Especialidades
- Integrações
- Consumo/APIs
- Logs
- Agentes
- Prompts
- Pipelines
- RAG
- Auditoria (modo admin)

---

## 3. Prompt Registry
Criar um registry formal de prompts com:
- id
- nome
- agente
- escopo (global / clínica / runtime)
- versão
- conteúdo
- status ativo
- data de atualização

### UX desejada
- editor simples
- preview
- comparação de versões
- indicação do prompt ativo
- sem precisar buscar hardcode no código

---

## 4. Pipeline Registry + Pipeline UI
Criar um registry de pipelines com:
- id
- nome
- tipo
- estágio
- nós/etapas
- condições
- ações
- fallback/handoff
- status

### Visualização
Usar uma UI gráfica inspirada em n8n para:
- exibir pipeline
- mostrar fluxo
- mostrar pontos de handoff
- mostrar fallback
- mostrar uso de RAG
- mostrar agentes envolvidos

Não precisa ser um n8n completo agora, mas precisa ser legível como fluxo.

---

## 5. Conversational Pipeline Rework
A pipeline de conversa atual está fragmentada. O design alvo deve unificar:

1. entrada do canal
2. resolução de contexto
3. lookup da clínica
4. lookup do paciente/lead
5. pending action
6. intent classification
7. entity extraction
8. decisão de consulta a RAG
9. decisão de agenda/CRM/handoff
10. builder final de resposta

### Regra central
A resposta final não pode sair de múltiplas camadas desconectadas.  
Deve existir uma **response composition layer** única.

---

## 6. CRM / Patient Management
Criar uma camada operacional real de CRM com:
- patient profile
- lead profile
- tags
- notes
- conversation links
- editable fields
- stage/status
- timeline

### UX
- drawer ou página detalhada
- edição simples
- timeline
- quick actions
- associação clara com chat

---

## 7. Chat UI
A UI de chat deve ser remodelada para parecer CRM/chat real.

### Requisitos de interface
- mensagens em formato de chat
- cabeçalho da conversa
- tags
- status
- bloquear/desbloquear
- atribuição
- vínculo com paciente
- ações rápidas
- histórico claro
- metadados técnicos escondidos por padrão

### Open source reference targets
Avaliar embedding/reuso de:
- Chatwoot para UX/conversation model
- Tiledesk para multi-channel/service patterns
- possíveis componentes de OpenClaw/Ironclaw apenas como inspiração, não como base principal

---

## 8. Handoff UX
A tela de handoff deve traduzir:
- intent técnica → label operacional
- confidence → linguagem humana
- entities → resumo compreensível
- last message → destaque visível
- motivo → explicação curta

Prover:
- visão simples
- visão técnica expandível

---

## 9. Audit UX
Auditoria deve ter dois níveis:
- **modo operacional**: linguagem clara
- **modo técnico**: payload expandível

Se necessário, parte da visualização detalhada pode ficar dentro do Admin.

---

## 10. RAG Domain Rebuild
O RAG precisa de pipeline real:
- upload
- parser
- metadados
- chunking
- embedding
- persistência
- teste
- logs de falha

### Admin/RAG UI
- upload de documento
- status de ingestão
- lista de documentos
- filtros
- teste de query
- visualização de chunks/fontes
- erros de ingestão

---

## 11. AI Management
Criar um domínio de AI settings:
- provider/modelo
- toggles de comportamento
- thresholds
- handoff policy
- RAG usage policy
- prompt selection

Isso deve ser configurável no Admin.

---

## 12. M-IA
Criar o desenho da M-IA como módulo:
- chat interno
- tools internas
- escopo operacional
- leitura de agenda/CRM/handoff/auditoria
- confirmação em ações críticas

Nesta rodada, pode nascer como:
- módulo arquitetural
- endpoints base
- UI inicial
- prompt registry e tool registry preparados

---

## 13. ERP Direction
Formalizar domínios futuros:
- employees
- rooms
- procedures
- products
- inventory
- operational reports

Open source de referência a avaliar:
- Dolibarr como ERP/CRM open source
- eventualmente Frappe/ERP stack como referência conceitual de modularidade

---

## 14. Open source search and embedding policy
### Referências recomendadas para busca/avaliação
- `github/spec-kit`
- `alirezarezvani/claude-skills`
- Chatwoot
- Twenty
- SuiteCRM
- Frappe CRM
- EspoCRM
- Dolibarr

### Política
Cada projeto deve ser classificado em:
- UX reference
- architecture reference
- reusable component
- not worth embedding

Sem incorporar cegamente.

---

## 15. Ordem de implementação
1. Admin domain
2. Prompt/agent registry
3. Conversational pipeline unification
4. CRM/patient editing
5. Chat UI
6. Handoff/audit UX
7. RAG rebuild
8. Pipeline visualization
9. M-IA base
10. ERP roadmap base
