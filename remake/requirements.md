# requirements.md

# IntelliClinic — Requirements (Admin Rebuild + CRM + Chat + RAG + M-IA)

## 1. Objetivo
Esta spec redefine a próxima fase do IntelliClinic para resolver bloqueios reais de produto e desenvolvimento:
- configuração demais via `.env`
- ausência de admin operacional forte
- CRM incompleto
- chat ruim para uso real
- RAG disfuncional
- prompts e pipelines pouco administráveis
- inexistência da M-IA
- ausência de direção concreta para ERP

---

## 2. Princípios
1. Configuração operacional deve sair do `.env` e migrar para Admin Panel / Admin API quando fizer sentido.
2. O sistema precisa ficar administrável por interface, não apenas por código.
3. O chat deve funcionar como chat real de operação e atendimento.
4. O RAG deve funcionar de verdade: ingestão, teste, consulta e governança.
5. Prompts, agentes e pipelines devem ser fáceis de ver e editar.
6. O produto deve continuar evoluindo em modelo:
   - 1 clínica = 1 VPS
   - 1 clínica = 1 banco
   - 1 clínica = 1 KB
7. As mudanças devem seguir SDD.
8. Reaproveitamento open source deve ser crítico e seletivo.

---

## 3. Requisitos funcionais

## RF-001 — Admin central de configuração da clínica
O sistema deve possuir um Admin Panel / Admin API para configurar:
- nome da clínica
- branding
- dados institucionais
- convênios aceitos
- especialidades
- informações de atendimento
- parâmetros operacionais
- canais e integrações
- providers/modelos de IA
- URLs e webhooks derivados

### Critério de aceite
A maior parte da configuração clínica não depende mais de editar `.env`, exceto segredos e infra.

---

## RF-002 — Admin de observabilidade operacional
O admin deve permitir visualizar:
- consumo de APIs
- status de integrações
- logs operacionais
- logs de atendimento
- logs de agentes
- métricas básicas de uso

### Critério de aceite
O dev/admin consegue inspecionar o estado da clínica sem navegar por JSONs crus ou arquivos soltos.

---

## RF-003 — Configuração de pipelines via admin
O sistema deve permitir visualizar e configurar pipelines por interface, incluindo:
- pipeline de atendimento
- pipeline de handoff
- pipeline de follow-up
- pipeline de RAG
- pipeline de agentes

### Critério de aceite
Existe ao menos uma visualização administrável e compreensível da pipeline atual.

---

## RF-004 — Gestão de prompts e agentes
O sistema deve permitir:
- visualizar prompt por agente
- editar prompt por agente
- versionar prompts
- diferenciar prompt global, prompt da clínica e prompt do agente
- visualizar qual prompt está ativo

### Critério de aceite
O fluxo de edição de prompt fica parecido com a clareza de ferramentas como n8n, sem exigir procurar hardcode no código.

---

## RF-005 — CRM utilizável
O CRM deve suportar minimamente:
- cadastro e edição real de pacientes
- visualização de histórico
- tags
- notas
- vínculo com conversas
- lead → paciente
- status/estágio
- ações operacionais rápidas

### Critério de aceite
Paciente e lead deixam de ser cadastros engessados e passam a ser entidades realmente gerenciáveis.

---

## RF-006 — Chat operacional real
O chat deve ter comportamento de chat real:
- interface de conversa robusta
- tagging
- bloqueio
- status da conversa
- vínculo com paciente/lead
- histórico claro
- ações operacionais visíveis
- melhor leitura para humano

### Critério de aceite
A experiência deixa de parecer log técnico e passa a parecer ferramenta de atendimento/CRM.

---

## RF-007 — Handoffs compreensíveis
A tela de handoffs deve traduzir sinais técnicos em linguagem de operação:
- intenção
- confiança
- última mensagem
- motivo do handoff
- dados relevantes

### Critério de aceite
Uma pessoa não técnica entende por que o handoff aconteceu.

---

## RF-008 — Auditoria compreensível
A auditoria deve:
- traduzir eventos técnicos em eventos entendíveis
- esconder complexidade irrelevante
- permitir drill-down técnico quando necessário

### Critério de aceite
A auditoria serve para operação, não só para dev.

---

## RF-009 — RAG funcional
O sistema deve permitir:
- ingestão de documentos
- processamento
- versionamento
- teste de consulta
- painel de status
- depuração de falha

### Critério de aceite
O painel RAG permite subir documento, acompanhar ingestão e testar retrieval de verdade.

---

## RF-010 — Admin de IA e RAG
O painel admin deve permitir:
- configurar provider/modelo
- configurar parâmetros de agentes
- ver status dos agentes
- ligar/desligar comportamentos
- gerenciar base de conhecimento
- testar respostas

### Critério de aceite
A configuração da IA deixa de ficar espalhada entre env, código e heurística.

---

## RF-011 — M-IA
O sistema deve incluir direção concreta para M-IA:
- agente interno de gerenciamento
- interface própria
- tools internas
- leitura dos módulos reais
- ação segura e auditável

### Critério de aceite
Existe um módulo claro e planejado para IA interna operacional.

---

## RF-012 — ERP roadmap concreto
O projeto deve formalizar e iniciar direção para ERP:
- produtos
- estoque
- procedimentos
- salas
- funcionários
- relatórios operacionais

### Critério de aceite
ERP deixa de ser “não existe” e passa a ter domínio, escopo e ordem de implementação.

---

## 4. Requisitos não funcionais
- UX operacional compreensível
- mínima exposição de JSON cru
- admin-first para configuração
- alta auditabilidade
- deploy preservado por clínica
- compatibilidade com o runtime atual
- evolução incremental
- forte documentabilidade

---

## 5. Escopo desta rodada
Entram agora:
- admin configuration
- prompt/agent management
- pipeline visualization
- CRM/patient editing
- chat UX
- handoff/audit UX
- RAG panel funcional
- pesquisa e avaliação open source
- desenho da M-IA
- direção concreta do ERP

Ficam fora da implementação imediata:
- ERP completo pronto
- GraphRAG pesado
- reescrita total do produto
