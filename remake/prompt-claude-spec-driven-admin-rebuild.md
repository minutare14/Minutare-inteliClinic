# prompt-claude-spec-driven-admin-rebuild.md

## Objetivo
Quero que você execute uma nova rodada de **Spec-Driven Development** no IntelliClinic para corrigir problemas estruturais de produto, admin, CRM, chat, RAG, IA interna e visualização de pipelines.

Você deve usar como base:
- os PRDs e specs já existentes do projeto
- o estado real do código
- a arquitetura atual em produção
- as dores reais encontradas no uso
- as novas mudanças listadas abaixo

Além disso, quero que você **baixe e integre o uso prático** das referências abaixo no fluxo de desenvolvimento:

### Referências obrigatórias
1. `github/spec-kit`
   - usar como base de processo spec-driven
   - estruturar requisitos, design, tasks e governança
   - usar a lógica de constitution/spec/plan/tasks como disciplina de execução

2. `alirezarezvani/claude-skills`
   - baixar e usar skills relevantes no projeto
   - principalmente skills de:
     - product
     - architecture
     - backend
     - frontend
     - docs
     - debugging
     - refactor
     - testing
     - prompt engineering

### Referências para busca e avaliação de embedding no sistema
3. Projetos de chat/CRM/open source pesquisados no GitHub para avaliar reaproveitamento e embedding:
- Chatwoot
- Twenty CRM
- SuiteCRM
- Frappe CRM
- EspoCRM
- Dolibarr ERP/CRM

Você não deve copiar cegamente esses projetos, mas deve:
- avaliar o que vale reaproveitar
- identificar o que pode ser embedado
- identificar o que pode virar base de UX
- identificar o que deve ser apenas inspiração
- documentar isso

---

## Problemas que devem ser tratados nesta rodada

### Admin / configuração
1. criação de um endpoint admin para configuração de branding e informações da clínica
2. configuração de pipeline via admin endpoint
3. configuração de RAG e IAs pelo painel admin
4. visualização e configuração fácil dos prompts dos agentes
5. visualização das pipelines de maneira gráfica
6. logs, consumo, APIs e integrações devem ser visíveis no admin
7. reduzir dependência de `.env` para dados operacionais/configuráveis por clínica

### CRM / pacientes / chat
8. CRM está incompleto
9. edição de pacientes está ruim/incompleta
10. chat precisa ter aparência e comportamento real de chat
11. chat precisa suportar tagging, bloqueio e funções operacionais já existentes
12. buscar no GitHub projetos de chats de Telegram embedados em CRM
13. buscar no GitHub projetos de CRM e gestão de clientes
14. melhorar UX de handoffs
15. melhorar UX da auditoria

### RAG / IA
16. RAG disfuncional: ingestão não funciona
17. painel RAG precisa ser melhorado
18. teste de RAG não funciona
19. não existe a M-IA (IA interna de gerenciamento)
20. configuração de agentes, prompts e pipelines deve ser mais acessível
21. instalar/adaptar/embedar no sistema os projetos open source que realmente fizerem sentido

### ERP
22. ERP não existe e precisa entrar como direção concreta de produto

---

## O que eu quero que você faça

### Etapa 1 — Reorganizar em SDD
Transforme essas mudanças em artefatos spec-driven:
- requirements
- design
- task list

### Etapa 2 — Buscar e avaliar open source
Faça buscas reais e análise de reaproveitamento para:
- chat embedado em CRM
- CRM open source moderno
- UX de pipelines
- UX de handoffs e auditoria
- admin configuration patterns
- prompt management patterns
- graphical pipeline builders

### Etapa 3 — Proposta de arquitetura
Entregue uma proposta clara para:
- Admin Endpoint / Admin Panel
- CRM real
- chat operacional real
- RAG funcional
- prompt management
- pipeline management gráfico
- M-IA
- ERP roadmap

### Etapa 4 — Classificação por prioridade
Classifique tudo em:
- fundação obrigatória
- fase 1
- fase 2
- fase 3
- opcional / inspiração
- não vale embutir

---

## Regras
- Não invente implementação pronta se ela não existe.
- Diferencie claramente:
  - já existe
  - existe parcial
  - não existe
  - precisa refatorar
- Não reescreva tudo do zero sem justificativa.
- Preserve o runtime real e use evolução incremental.
- Use as skills e o spec-kit para organizar o trabalho.
- Quero análise crítica, não marketing.

---

## Entregas obrigatórias
Quero que você me devolva:
1. requirements.md
2. design.md
3. task.md
4. relatório de busca/open source recomendando o que instalar, o que embedar, o que reaproveitar e o que não usar

---

## Formato de resposta
### 1. Resumo executivo
### 2. Requirements
### 3. Design
### 4. Tasks
### 5. GitHub/Open source research
### 6. Recomendações de embedding/reuse
### 7. Próximos passos
