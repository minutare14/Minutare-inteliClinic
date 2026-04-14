# IntelliClinic — Relatório de Pesquisa Open Source

Data: 2026-04-14  
Scope: Chat/CRM/ERP open source avaliados para embedding, reuso e inspiração no IntelliClinic

---

## 1. Chatwoot

**Repositório:** chatwoot/chatwoot  
**Stack:** Ruby on Rails + Vue.js, PostgreSQL, Redis, Sidekiq  
**Stars:** ~22k

### O que é
Plataforma omni-channel de suporte ao cliente open source. Alternativa ao Intercom e Zendesk.  
Suporta Telegram, WhatsApp, email, website chat widget.

### O que vale
- **UX de conversa** é a melhor referência disponível open source para o chat do IntelliClinic:
  - Lista de conversas com status, atribuição, tags
  - Thread de mensagens com cabeçalho de contexto
  - Ações rápidas na conversa (fechar, atribuir, adicionar tag, bloquear)
  - Sidebar de detalhes do contato ao lado do chat
  - Inbox por canal
- **Conversation model** é bem estruturado: status (open/resolved/snoozed), assignee, label, inbox
- **Dashboard Apps** permite embeder ferramentas internas no painel (útil para M-IA)

### O que não vale
- Stack Ruby/Vue incompatível com o backend Python e frontend Next.js do IntelliClinic
- Não recomendado embedar o Chatwoot inteiro — seria um segundo sistema inteiro
- Escopo de suporte ao cliente, não de clínica médica

### Classificação
| Dimensão | Classificação |
|----------|--------------|
| UX Chat | **UX Reference** — modelo de interface a copiar |
| Conversation model | **Architecture Reference** — estrutura de dados a adaptar |
| Componentes UI | **Inspiração** — não recomendado reuso direto (Vue, não React) |
| Embedding do sistema | **Não vale** — stack incompatível, escopo diferente |

### Recomendação
Copiar o modelo de UX do chat (list + thread + sidebar de contato + ações rápidas).  
Adaptar o conversation model para o domínio clínica (paciente, intent, handoff).  
Não instalar o Chatwoot.

---

## 2. Twenty CRM

**Repositório:** twentyhq/twenty  
**Stack:** React + NestJS + GraphQL, PostgreSQL, Redis, BullMQ, Nx monorepo  
**Stars:** ~25k+

### O que é
CRM moderno open source, alternativa ao Salesforce. UI muito polida, totalmente customizável.

### O que vale
- **UX de CRM** é referência de mercado:
  - Views customizáveis por objeto (people, companies, deals)
  - Kanban e lista para pipelines
  - Relacionamentos entre objetos (deals ↔ contacts ↔ companies)
  - Activity feed por contato (timeline)
  - Filtros avançados + busca global
- **Conceito de "objects"** como entidades extensíveis — boa inspiração para modelar lead → paciente
- **Timeline por contato** — exatamente o que falta no IntelliClinic para histórico do paciente
- Kanban para pipeline de atendimento / leads

### O que não vale
- Stack NestJS + GraphQL muito diferente do FastAPI/REST atual
- Escopo de B2B CRM, não de clínica — precisaria adaptação significativa
- Muito pesado para um deploy single-tenant de clínica pequena

### Classificação
| Dimensão | Classificação |
|----------|--------------|
| UX CRM | **UX Reference** — melhor referência de CRM moderno |
| Timeline/activity feed | **Architecture Reference** — padrão a implementar no paciente |
| Kanban pipeline | **UX Reference** — para pipeline de handoffs/leads futuros |
| Object model | **Architecture Reference** — lead → paciente como objeto extensível |
| Embedding do sistema | **Não vale** — stack incompatível |

### Recomendação
Usar como referência visual e conceitual para a evolução do CRM de pacientes.  
Implementar timeline de atividades do paciente seguindo o padrão do Twenty.  
Não instalar o Twenty.

---

## 3. SuiteCRM

**Repositório:** salesagility/SuiteCRM  
**Stack:** PHP + MySQL, legado  
**Stars:** ~4k

### O que é
Fork do SugarCRM Community Edition. CRM enterprise open source com módulos completos: contas, contatos, leads, oportunidades, cotações, relatórios, campanhas.

### O que vale
- **Referência de domínio** para definir o que um CRM completo deve ter
- **Estrutura de módulos** — referência para o roadmap de ERP do IntelliClinic
- **Relatórios operacionais** — estrutura de relatórios customizáveis

### O que não vale
- Stack PHP legada, UI ultrapassada
- Extremamente pesado para o contexto da clínica
- Sem alinhamento com a stack moderna do projeto

### Classificação
| Dimensão | Classificação |
|----------|--------------|
| UX | **Não vale** — UI ultrapassada |
| Domain model | **Architecture Reference** — o que um CRM deve cobrir |
| Embedding | **Não vale** |

### Recomendação
Usar apenas como referência de checklist de domínio CRM (quais módulos existem).  
Não instalar, não embedar.

---

## 4. Frappe CRM

**Repositório:** frappe/crm  
**Stack:** Python (Frappe Framework) + Vue.js  
**Stars:** ~2k+

### O que é
CRM moderno construído em 2023 sobre o Frappe Framework. Leads, deals, pipeline, kanban, activity tracking.  
Integra nativamente com ERPNext para fechar deals e gerar pedidos.

### O que vale
- **Pipeline de leads → deals** com stages configuráveis — referência para lead → paciente do IntelliClinic
- **Activity stream** por deal — padrão limpo e implementável
- **Frappe como plataforma** — se o IntelliClinic evoluir para um ERP completo, o Frappe/ERPNext é a stack de referência mais usada no mercado open source
- UI mais moderna que SuiteCRM, construída em Vue

### O que não vale
- Frappe Framework tem curva de aprendizado e acoplamento forte
- Stack diferente da atual (Frappe Python, não FastAPI)
- Integração com o sistema atual seria complexa

### Classificação
| Dimensão | Classificação |
|----------|--------------|
| Pipeline de leads | **UX Reference** |
| Activity stream | **Architecture Reference** |
| Frappe como ERP future | **Referência de ERP** — a considerar se o IntelliClinic decidir migrar para ERP completo |
| Embedding | **Não vale por agora** |

### Recomendação
Não instalar agora. Manter como opção de longo prazo se o roadmap de ERP exigir framework de aplicativos completo.  
Copiar o padrão de pipeline de leads e activity stream.

---

## 5. EspoCRM

**Repositório:** espocrm/espocrm  
**Stack:** PHP + JavaScript (in-house framework)  
**Stars:** ~1.5k

### O que é
CRM leve, self-hosted, orientado para mid-market. Fácil de customizar por admin sem código.  
Tem streams por entidade, relacionamentos, layouts editáveis, roles.

### O que vale
- **Admin-configurável sem código** — exatamente o modelo que o IntelliClinic quer para clínicas sem dev
- **Entity Relationship model** — relacionamentos entre paciente, consulta, convênio, profissional
- **Streams (activity feed)** — padrão limpo de feed por entidade

### O que não vale
- Stack PHP + JS in-house, nenhuma compatibilidade com o projeto atual
- UI mediana, não é referência visual de mercado

### Classificação
| Dimensão | Classificação |
|----------|--------------|
| Admin-configurável | **Architecture Reference** — objetivo de produto a copiar |
| Entity model | **Architecture Reference** |
| UX | **Inspiração fraca** |
| Embedding | **Não vale** |

### Recomendação
Usar como referência conceitual de "admin sem código".  
Não instalar, não embedar.

---

## 6. Dolibarr ERP/CRM

**Repositório:** Dolibarr/dolibarr  
**Stack:** PHP + MySQL/PostgreSQL  
**Stars:** ~5k

### O que é
ERP/CRM open source para PMEs. Módulos: contatos, pedidos, faturas, estoque, agenda, contabilidade, RH.  
Arquitetura modular — ativa só o que precisa.

### O que vale
- **Domínio de ERP** — melhor referência para o roadmap de ERP do IntelliClinic:
  - Módulo de terceiros (contatos/pacientes)
  - Módulo de agenda/recursos (salas, equipamentos)
  - Módulo de produtos/procedimentos
  - Módulo de estoque
  - Módulo de RH/funcionários
  - Módulo de relatórios
- **Arquitetura modular** — ativar só o que a clínica precisa
- **Deploy simples** — PHP + uma tabela de configuração por módulo

### O que não vale
- Stack PHP, UI ultrapassada
- Não embedável no IntelliClinic diretamente
- Não é referência visual

### Classificação
| Dimensão | Classificação |
|----------|--------------|
| Domain coverage ERP | **Architecture Reference** — quais módulos o ERP deve ter |
| Arquitetura modular | **Architecture Reference** — como estruturar ativação de módulos |
| UX | **Não vale** |
| Embedding | **Não vale** |

### Recomendação
Usar o Dolibarr como mapa de domínio para o roadmap do ERP do IntelliClinic.  
Não instalar, não embedar.

---

## 7. spec-kit (github/spec-kit)

**Propósito:** Framework para Spec-Driven Development (SDD)  
**Uso:** Estruturar requirements, design, tasks e governança com Constitution/Spec/Plan/Tasks

### Classificação
| Dimensão | Classificação |
|----------|--------------|
| Processo SDD | **Adotar como processo** — esta rodada já usa a estrutura |
| Templates | **Reusable** — usar requirements/design/task templates |

---

## 8. alirezarezvani/claude-skills

**Propósito:** Skills específicas para uso com Claude no desenvolvimento  
**Uso:** Skills de product, architecture, backend, frontend, docs, debugging, refactor, testing, prompt engineering

### Classificação
| Dimensão | Classificação |
|----------|--------------|
| Skills de produto/arquitetura | **Reusable** — usar nas próximas fases |
| Skills de prompt engineering | **Reusable** — útil para o Prompt Registry |

---

## Resumo de Recomendações

| Projeto | Ação |
|---------|------|
| **Chatwoot** | Copiar UX do chat. Não instalar. |
| **Twenty CRM** | Copiar UX do CRM + timeline. Não instalar. |
| **SuiteCRM** | Usar como checklist de domínio. Não instalar. |
| **Frappe CRM** | Referência de pipeline. Opção de longo prazo para ERP. |
| **EspoCRM** | Referência conceitual de admin-configurável. Não instalar. |
| **Dolibarr** | Mapa de domínio de ERP. Não instalar. |
| **spec-kit** | Adotar como processo SDD imediatamente. |
| **claude-skills** | Usar skills de produto e prompt engineering nas próximas fases. |

---

## O que Instalar / Embedar Agora

### Instalar: Nenhum dos CRMs/ERPs acima
Todos têm stacks incompatíveis e escopo diferente. O custo de manutenção de um segundo sistema seria maior que o benefício.

### Embedar como componente: Avaliar no Stage 5 (Chat UX)
- Componentes React de chat podem ser construídos inspirados no Chatwoot sem usar o Chatwoot
- Bibliotecas específicas de UI de chat a avaliar quando implementar Stage 5:
  - `@stream-io/stream-chat-react` (componentes de chat prontos)
  - `react-chat-ui` (componentes simples de chat)
  - Ou construir do zero com Tailwind + inspiração do Chatwoot (recomendado para controle total)

### O que reaproveitar internamente
1. O modelo de conversation do Chatwoot → adaptar para paciente/conversa/handoff
2. O timeline de contato do Twenty → implementar em `patient/{id}` no Stage 4
3. A arquitetura modular do Dolibarr → estrutura de módulos ERP no Stage 11
4. O conceito de pipeline configurável do Frappe → Stage 3 (conversational pipeline rework)
