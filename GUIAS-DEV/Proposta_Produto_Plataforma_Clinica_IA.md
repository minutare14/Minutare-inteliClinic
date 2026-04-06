# Proposta Consolidada de Produto: Plataforma Integrada de Gestão Clínica com Inteligência Artificial

**Documento de Especificação Estratégica e Arquitetural**
**Versão 1.0 — Abril 2026**

---

## 1. VISÃO UNIFICADA DO PRODUTO

### Diagnóstico da Convergência

As duas pesquisas abordam, cada uma por um ângulo, o mesmo problema central: **a clínica médica brasileira opera com ferramentas fragmentadas que não conversam entre si**, gerando desperdício financeiro, sobrecarga humana e experiência ruim para o paciente. A pesquisa de atendimento foca na porta de entrada (WhatsApp, RAG, agendamento, follow-up), enquanto a pesquisa de gestão foca no motor interno (agenda inteligente, faturamento, fluxo físico, decisão gerencial). Separadas, cada uma resolve metade do problema. Juntas, formam um produto completo.

### Visão Central

**Uma plataforma única onde a mesma inteligência que conversa com o paciente no WhatsApp é a mesma que organiza a agenda, previne glosas, monitora o fluxo físico e gera relatórios para o gestor.**

A proposta de valor real não é "ter IA". É **eliminar as zonas de transição de informação** — os pontos onde dados se perdem entre sistemas, onde a recepcionista precisa copiar informação de um chat para o ERP, onde o faturista não sabe o que aconteceu na consulta. Cada dado nasce uma vez e percorre o sistema inteiro sem retrabalho humano.

### Os Seis Pilares do Produto

1. **Atendimento Conversacional** — IA que atende o paciente em linguagem natural via WhatsApp, agenda, tira dúvidas com RAG e faz handoff para humano quando necessário.
2. **Gestão Operacional da Clínica** — Agenda inteligente, prontuário eletrônico, faturamento TISS/TUSS, controle financeiro.
3. **Copiloto da Recepção** — IA que assiste a recepcionista em tempo real: sugere encaixes, alerta sobre atrasos, valida elegibilidade.
4. **Inteligência Financeira** — Prevenção preditiva de glosas, projeção de fluxo de caixa, gestão de inadimplência.
5. **Motor de Relacionamento** — Réguas de follow-up, reativação de pacientes inativos, NPS, CRM conversacional.
6. **Inteligência Gerencial** — Dashboards analíticos, detecção de padrões, recomendações operacionais automatizadas.

### Proposta de Valor Real

Para a **recepcionista**: libera da carga cognitiva de responder WhatsApp + telefone + balcão simultaneamente.
Para o **médico**: prontuário mais simples, agenda sem furos, paciente que chega preparado.
Para o **gestor/dono**: visibilidade financeira em tempo real, redução de glosas, previsão de receita.
Para o **paciente**: resposta imediata, confirmação sem atrito, follow-up que demonstra cuidado.

---

## 2. MAPA CONSOLIDADO DE MÓDULOS DO SISTEMA

### Bloco A — Core Operacional (Transacional)

| Módulo | Função | Dependências | Relações | Prioridade |
|--------|--------|--------------|----------|------------|
| **A1. Cadastro de Pacientes** | Registro unificado (dados pessoais, convênio, histórico de contato). Base FHIR Patient. | Nenhuma | Alimenta todos os outros módulos | MVP |
| **A2. Agenda Multiprofissional** | Gestão de horários por médico, sala e equipamento. Blocos elásticos. | A1 | Consome dados de A1, alimenta A5 e B1 | MVP |
| **A3. Prontuário Eletrônico (PEP)** | Registro clínico cronológico, assinatura digital, imutabilidade. Base FHIR Encounter/Observation. | A1, A2 | Alimenta A4 e C3 | MVP |
| **A4. Faturamento TISS/TUSS** | Geração de lotes XML, validação de códigos, submissão a operadoras. | A1, A2, A3 | Consome dados clínicos de A3 | MVP |
| **A5. Financeiro Operacional** | Contas a pagar/receber, fluxo de caixa, NFS-e, conciliação. | A4 | Alimenta D2 | MVP |
| **A6. Controle de Convênios** | Tabelas de cobertura, carência, elegibilidade, autorização prévia. | Nenhuma | Validação para A2 e A4 | MVP |

### Bloco B — Atendimento e Relacionamento

| Módulo | Função | Dependências | Relações | Prioridade |
|--------|--------|--------------|----------|------------|
| **B1. Canal Omnichannel** | Gateway de entrada (WhatsApp API, webchat, Instagram). Fila unificada. | Nenhuma | Alimenta B2 | MVP |
| **B2. Motor Conversacional** | Processamento de linguagem natural, classificação de intenção, geração de resposta. | B1, D1 | Consome RAG (D1), aciona A2 | MVP |
| **B3. Painel da Recepção** | Interface unificada para atendente humano. Visão de filas, chats, alertas. | B1, A2 | Recebe handoffs de B2 | MVP |
| **B4. Motor de Follow-up** | Réguas automatizadas (lembretes, NPS, pós-consulta, reativação). Templates WhatsApp. | A2, A3, B1 | Consome agenda e PEP, dispara via B1 | Fase 2 |
| **B5. CRM Conversacional** | Histórico completo de interações por paciente. Timeline unificada. | B1, A1 | Alimenta D2 e B4 | Fase 2 |

### Bloco C — Inteligência e Automação

| Módulo | Função | Dependências | Relações | Prioridade |
|--------|--------|--------------|----------|------------|
| **C1. Otimizador de Agenda** | Previsão de no-show, overbooking inteligente, blocos elásticos, balanceamento de carga entre médicos. | A2, A1 | Reconfigura A2 automaticamente | Fase 2 |
| **C2. Auditor Anti-Glosa** | Validação preditiva de faturamento antes do envio. Cruzamento CID × TUSS × contrato. | A3, A4, A6 | Bloqueia envios inconsistentes em A4 | Fase 2 |
| **C3. Copiloto Clínico** | Transcrição de consulta, sugestão de prontuário estruturado. SAD básico. | A3 | Grava em A3 com supervisão médica | Fase 3 |
| **C4. Motor Analítico Gerencial** | Detecção de padrões, alertas operacionais, narrativas analíticas, recomendações. | A2, A5, B5 | Consolida dados de todos os blocos | Fase 3 |
| **C5. Gestor de Fluxo Físico** | Kanban de pacientes no espaço, painéis de espera, alertas de gargalo. | A2, hardware local | Comunica com A2 e B3 | Fase 4 |

### Bloco D — Dados, Contexto e Conhecimento

| Módulo | Função | Dependências | Relações | Prioridade |
|--------|--------|--------------|----------|------------|
| **D1. Base de Conhecimento RAG** | Corpus vetorizado (preparos de exames, FAQ, convênios, corpo clínico). | Nenhuma | Alimenta B2 | MVP |
| **D2. Memória Contextual** | Contexto do paciente para personalização (preferências, histórico de interações). | A1, B5 | Alimenta B2 e B4 | Fase 2 |
| **D3. Banco de Decisões** | Decisões humanas de handoff reaproveitáveis. Feedback loop para RAG. | B3 | Enriquece D1 | Fase 3 |

### Bloco E — Observabilidade e Auditoria

| Módulo | Função | Dependências | Relações | Prioridade |
|--------|--------|--------------|----------|------------|
| **E1. Logs de Auditoria** | Registro imutável de todas as ações (humanas e IA). Trilha de rastreabilidade. | Todos | Transversal | MVP |
| **E2. Painel de Governança IA** | Métricas de confiança, taxa de handoff, alucinações detectadas, override humano. | B2, C1-C4 | Alimenta decisões de calibração | Fase 2 |
| **E3. Conformidade LGPD** | Gestão de consentimento, anonimização, direito ao esquecimento, apoio ao DPO. | A1, E1 | Transversal | MVP |

---

## 3. MAPA CONSOLIDADO DOS MÓDULOS DE IA

### 3.1 Orquestrador Central (Roteador de Intenção)

**Papel:** Ponto de entrada único para todos os eventos (mensagem de paciente, erro financeiro detectado, alerta de agenda). Classifica a intenção e despacha para o agente especialista correto. Não possui acesso de escrita direta.

**Dados que consome:** Texto bruto do paciente, eventos do sistema (webhook WhatsApp, triggers de CronJob), metadados de sessão.

**Ações que executa:** Classificação de intenção (agendar, dúvida, urgência, administrativo), seleção do agente subordinado, montagem de contexto inicial.

**Impacto:** Evita o antipadrão de um LLM monolítico tentando fazer tudo. Garante que cada agente receba apenas o contexto necessário, reduzindo custo de tokens e risco de alucinação.

### 3.2 Motor Conversacional (Agente de Linguagem e Acolhimento)

**Papel:** Gera respostas empáticas em linguagem natural. Não altera banco de dados — recebe resultados de ações de outros agentes e os traduz em prosa humanizada.

**Dados que consome:** Intenção classificada pelo Orquestrador, resultados de consultas à agenda, respostas do RAG, contexto do paciente.

**Ações que executa:** Formulação de respostas, análise de sentimento contínua, detecção de urgência emocional, formatação para canal (WhatsApp vs. webchat).

**Impacto:** Centraliza a "voz" do sistema. Garante consistência de tom independente do módulo que gerou a informação.

### 3.3 Motor RAG (Recuperação e Geração Aumentada)

**Papel:** Responde dúvidas factuais com base exclusiva no corpus validado da clínica (preparos, convênios, horários, corpo clínico).

**Dados que consome:** Pergunta vetorizada, metadados de categoria, threshold de confiança.

**Ações que executa:** Busca vetorial (top-5 chunks), cálculo de similaridade de cosseno, geração de resposta ancorada em fontes, anexação de citação de fonte para auditoria.

**Impacto:** Elimina alucinações factuais. Respostas sobre preparos de exame vêm do manual real, não do conhecimento genérico do LLM. Reduz handoff para humano em dúvidas operacionais simples.

### 3.4 Agente de Agenda e Logística

**Papel:** Executa ações transacionais na agenda: reserva, cancelamento, remarcação, encaixe. Único agente com escrita na tabela de agenda.

**Dados que consome:** Intenção de agendamento (médico, especialidade, janela temporal), disponibilidade em tempo real, regras de convênio, perfil do paciente.

**Ações que executa:** Busca de slots disponíveis, bloqueio de horário, validação de elegibilidade, resolução de conflitos temporais.

**Impacto:** Resolve 60% das interações de agendamento sem humano. Opera 24/7, eliminando a dependência do horário comercial.

### 3.5 Copiloto da Recepção

**Papel:** Assistente em tempo real para a recepcionista. Não substitui — potencializa. Exibe sugestões contextuais na tela do atendente.

**Dados que consome:** Status da agenda em tempo real, fila de pacientes, atrasos acumulados, lista de espera, perfil de pacientes aguardando.

**Ações que executa:** Sugere encaixes quando há cancelamento, alerta sobre atrasos em cascata, notifica pacientes sobre tempo de espera, valida documentação de convênio automaticamente.

**Impacto:** Transforma a recepcionista de "gargalo único" em operadora assistida. Reduz tempo de resolução de encaixes de minutos para segundos.

### 3.6 Motor de Follow-up e Relacionamento

**Papel:** Executa réguas automatizadas de comunicação pós-consulta, reativação e retenção.

**Dados que consome:** Eventos do PEP (consulta finalizada, prescrição emitida), calendário de retornos, histórico de engajamento, segmentação de pacientes.

**Ações que executa:** Disparo de templates WhatsApp (utilidade e marketing), coleta de NPS, alertas de abandono terapêutico, campanhas de preenchimento de agenda ociosa.

**Impacto:** Ataca diretamente a evasão de 40-60% pós-primeira consulta. Converte custo de aquisição (CAC) em receita recorrente (LTV).

### 3.7 Motor de Handoff

**Papel:** Gerencia a transferência do bot para humano de forma fluida, preservando contexto completo.

**Dados que consome:** Score de confiança do RAG, análise de sentimento, detecção de palavras-chave de urgência, contagem de loops conversacionais.

**Ações que executa:** Classificação de urgência (clínica vs. frustração vs. limitação epistêmica), transferência com resumo contextual, roteamento para fila correta (recepção vs. coordenação clínica).

**Impacto:** Evita o cenário destrutivo de paciente "preso" em loop de bot. Preserva confiança institucional.

### 3.8 Auditor Financeiro (Anti-Glosa)

**Papel:** Valida 100% dos documentos de faturamento antes do envio às operadoras.

**Dados que consome:** Códigos CID, procedimentos TUSS, regras contratuais por operadora, laudos do PEP, histórico de glosas.

**Ações que executa:** Cruzamento CID × TUSS × cobertura contratual, bloqueio de envios inconsistentes, cálculo de probabilidade de glosa, sugestão de correção.

**Impacto:** Reduz glosas de 15-20% para menos de 5%. ROI mais rápido de toda a plataforma — cada glosa evitada é receita salva.

### 3.9 Motor Analítico e de Decisão Operacional

**Papel:** Consolida microeventos operacionais e gera insights acionáveis para gestores.

**Dados que consome:** Tempos de espera, taxa de ocupação de agenda, performance por profissional, volume de atendimento por canal, indicadores financeiros.

**Ações que executa:** Detecção de anomalias, correlações complexas (dia da semana × complicações), geração de narrativas analíticas, recomendações de alocação de recursos.

**Impacto:** Transforma gestão "pelo retrovisor" (relatórios mensais) em gestão preditiva em tempo real.

---

## 4. RELAÇÃO ENTRE IA DE ATENDIMENTO E IA DE GESTÃO

### Onde se complementam

A IA de atendimento é a **captadora de dados brutos** — cada conversa com paciente gera intenções, preferências, feedbacks e dados transacionais. A IA de gestão é a **consumidora analítica** — transforma esses dados em decisão operacional. Sem o atendimento, a gestão não tem dados frescos. Sem a gestão, o atendimento não tem contexto operacional para responder bem.

Exemplo concreto: quando a IA de atendimento agenda uma consulta via WhatsApp, ela gera um evento que alimenta o modelo preditivo de no-show da IA de gestão. Se a gestão detecta agenda ociosa na quarta-feira, ela aciona a IA de atendimento para disparar campanhas de preenchimento para pacientes do perfil certo.

### Onde uma depende da outra

O **Agente de Agenda** (atendimento) depende completamente das **regras de elegibilidade** (gestão). Não pode confirmar um agendamento sem validar convênio. O **Auditor Anti-Glosa** (gestão) depende dos **dados registrados no PEP** que foram gerados durante o atendimento clínico. O **Motor de Follow-up** (atendimento) depende das **prescrições e evolução** registradas no core operacional (gestão).

### Onde devem compartilhar contexto

O contexto do paciente precisa ser **bidirecional**: se o paciente mencionou no WhatsApp que está com medo do procedimento, a recepcionista precisa ver isso no painel. Se o médico prescreveu um medicamento com preparo específico, o follow-up automático precisa saber disso para incluir as orientações corretas.

O modelo de compartilhamento recomendado é um **barramento de eventos (event bus)**: cada módulo publica eventos tipados, e os módulos interessados se inscrevem. Exemplo: evento `consulta.finalizada` é publicado pelo PEP e consumido pelo Motor de Follow-up, pelo Auditor Anti-Glosa e pelo Motor Analítico.

### Onde devem permanecer separadas

**Dados clínicos sensíveis** (prontuário, diagnóstico, prescrição) nunca devem ser acessíveis pela IA de atendimento conversacional. O bot que conversa no WhatsApp não pode ter acesso ao PEP completo — apenas aos dados operacionais (agenda, preparo, FAQ). Essa separação é obrigatória pela Resolução CFM 2.454/2026 e pela LGPD.

**Separação de permissões de escrita:** O Agente de Linguagem (que gera texto para o paciente) nunca deve ter permissão de escrita no banco transacional. Quem escreve na agenda é o Agente de Agenda. Quem escreve no PEP é o Copiloto Clínico (com validação médica). O princípio é: quem gera texto não altera dados, quem altera dados não conversa diretamente.

### Orquestração Central — Como evitar duplicidade

O Orquestrador Central é o ponto de convergência. Ele recebe todos os eventos e despacha para o agente correto. Não há dois agentes fazendo a mesma coisa. A regra é:
- **Uma ação, um dono.** Agendar = Agente de Agenda. Responder dúvida = RAG + Linguagem. Validar faturamento = Auditor.
- **Comunicação por eventos, não por chamada direta.** Módulos não chamam outros módulos — publicam eventos e o Orquestrador coordena.

---

## 5. FLUXOS FIM A FIM MAIS IMPORTANTES

### Fluxo 1: Paciente novo agenda via WhatsApp

**Percurso:** Paciente → WhatsApp → Orquestrador → Agente de Linguagem + RAG → Agente de Agenda → Confirmação → Follow-up T-48h e T-24h → Recepção acompanha → Consulta → NPS → Follow-up pós

| Etapa | Módulo | Automação vs. Humano | Dados registrados |
|-------|--------|----------------------|-------------------|
| Mensagem inicial do paciente | B1 (Canal) → Orquestrador | Automação total | Timestamp, canal, texto bruto |
| Classificação de intenção | Orquestrador | Automação total | Intenção classificada, confiança |
| Coleta de dados e verificação de convênio | B2 (Conversacional) + A6 (Convênios) | Automação total | CPF, operadora, elegibilidade |
| Apresentação de horários e confirmação | Agente de Agenda + B2 | Automação total | Slot selecionado, reserva provisória |
| Confirmação final e instrução de preparo | B2 + D1 (RAG) | Automação total | Agendamento confirmado, preparo enviado |
| Lembrete T-48h | B4 (Follow-up) | Automação total | Status de confirmação |
| Lembrete T-24h com botão interativo | B4 | Automação total | Confirmação/reagendamento |
| Check-in na recepção | B3 (Painel Recepção) | Humano assistido | Horário de chegada, validação presencial |
| Consulta médica | A3 (PEP) | Humano (médico) | Evolução clínica, prescrição |
| NPS automático (60-120min pós) | B4 | Automação total | Nota NPS, comentário |
| Follow-up terapêutico (D+8 se antibiótico) | B4 | Automação total | Resposta do paciente, flag para equipe se necessário |

### Fluxo 2: Paciente falta (No-Show)

**Percurso:** Sistema detecta → Agenda reorganiza → Encaixe da lista de espera → Follow-up ao faltante

| Etapa | Módulo | Automação vs. Humano | Dados registrados |
|-------|--------|----------------------|-------------------|
| Horário passa sem check-in | A2 (Agenda) + E1 (Logs) | Automação (detecção) | Flag de no-show, timestamp |
| Notificação para recepção | C5 ou B3 | Automação | Alerta visual no painel |
| Varredura de lista de espera | C1 (Otimizador) | Automação total | Candidatos identificados por perfil e proximidade |
| Oferta de horário para paciente da espera | B2 (Conversacional) via B1 | Automação total | Mensagem enviada, resposta registrada |
| Contato com paciente faltante (reagendamento) | B4 (Follow-up) | Automação total | Tentativa de remarcação |
| Registro no perfil do paciente | A1 + D2 | Automação total | Histórico de no-show atualizado para modelo preditivo |

### Fluxo 3: Agenda ociosa detectada

**Percurso:** IA de gestão identifica ociosidade → IA de atendimento aciona campanhas

| Etapa | Módulo | Automação vs. Humano | Dados registrados |
|-------|--------|----------------------|-------------------|
| Detecção de ociosidade crônica (ex: quartas à tarde) | C1 (Otimizador) + C4 (Analítico) | Automação total | Padrão identificado, médico, período |
| Segmentação de pacientes-alvo | D2 (Memória) + A1 | Automação total | Lista segmentada por especialidade e perfil |
| Aprovação do gestor (se campanha de marketing) | Painel gerencial | Humano (gestor) | Aprovação registrada |
| Disparo de campanha via WhatsApp (template marketing) | B4 + B1 | Automação total | Templates enviados, custo por mensagem |
| Priorização na sugestão do chatbot | B2 | Automação total | Quando paciente sem preferência de médico pedir agenda, priorizar slots ociosos |

### Fluxo 4: Dúvida complexa → Handoff → Conhecimento estruturado

**Percurso:** Paciente faz pergunta → RAG não tem resposta → Handoff → Humano resolve → Resposta vira conhecimento

| Etapa | Módulo | Automação vs. Humano | Dados registrados |
|-------|--------|----------------------|-------------------|
| Pergunta do paciente | B2 + D1 (RAG) | Automação total | Pergunta, chunks recuperados, score de confiança |
| RAG abaixo do threshold de confiança | Motor de Handoff | Automação total | Score de confiança, razão do handoff |
| Transferência para atendente com contexto | B3 (Painel Recepção) | Automação (transferência) | Resumo da conversa, pergunta original |
| Atendente humano responde | B3 | Humano | Resposta redigida, tempo de resolução |
| Resposta marcada como candidata a RAG | D3 (Banco de Decisões) | Humano (validação) | Pergunta + resposta validada |
| Curadoria e ingestão no RAG | D1 | Humano (curador) + Automação (vetorização) | Novo chunk, metadados, revisor responsável |

---

## 6. ESTRUTURA UNIFICADA DE DADOS, MEMÓRIA E RAG

### Camada 1 — Banco Transacional (PostgreSQL)

**O que fica aqui:** Tudo que exige consistência ACID — cadastros de pacientes (modelo FHIR Patient), agendamentos (FHIR Encounter), evolução clínica (FHIR Observation), faturamento (lotes TISS XML), financeiro (contas a pagar/receber), convênios, usuários do sistema.

**Características:** Relacional estrito, backup diário, criptografia at-rest e in-transit, retenção conforme CFM (mínimo 20 anos para prontuários), RBAC granular por tabela e coluna.

### Camada 2 — Histórico de Atendimento (Append-Only)

**O que fica aqui:** Todas as mensagens trocadas com pacientes (WhatsApp, webchat), logs de conversação da IA, timestamps de cada interação, classificações de intenção, scores de sentimento.

**Características:** Tabelas append-only (nunca deletar, apenas inserir). Particionamento por mês. Indexação por paciente_id e canal. Serve como base para o CRM conversacional e para auditoria.

### Camada 3 — Contexto do Paciente (Memória Operacional)

**O que fica aqui:** Perfil consolidado por paciente: preferências de horário, canal preferido, histórico de no-shows, score de engajamento, último atendimento, próximo retorno previsto, flags de atenção (alergia mencionada no chat, preferência por Dr. X).

**Características:** Key-value store ou documento JSON por paciente. Atualizado por eventos em tempo real. Leitura rápida para personalização de interações. Dados não-clínicos — sem diagnóstico nem prescrição.

### Camada 4 — Base de Conhecimento RAG (Vetorial)

**O que fica aqui:** Corpus vetorizado da clínica — manuais de preparo de exames, FAQ operacional, tabelas de convênios aceitos, perfil do corpo clínico, protocolos de atendimento. Chunks de ~500 palavras com overlap de 15-25%.

**Características:** Banco vetorial (pgvector no PostgreSQL ou Qdrant). Cada chunk possui envelope de metadados obrigatório: documento_fonte, página, data_efetivação, categoria, médico_revisor. Modelo de embeddings ajustado para português brasileiro. Score de confiança mínimo de 0.75 para respostas — abaixo disso, handoff.

**Estratégia de mitigação de alucinação:** System prompt restritivo ("responda exclusivamente com base no contexto recuperado"), citação obrigatória de fonte, disclaimers automáticos em respostas sobre saúde.

### Camada 5 — Decisões Humanas Reaproveitáveis

**O que fica aqui:** Perguntas que causaram handoff + resposta dada pelo humano + validação de que a resposta pode ser incorporada ao RAG. Funciona como pipeline de enriquecimento contínuo.

**Características:** Tabela relacional com status (pendente_curadoria, validada, ingerida_no_rag, descartada). Cada entrada precisa de aprovação humana antes de entrar no RAG.

### Camada 6 — Trilhas de Auditoria

**O que fica aqui:** Log imutável de toda ação no sistema — quem visualizou qual prontuário, quem cancelou qual agendamento, quando a IA sugeriu algo, quando o humano fez override, quando um faturamento foi bloqueado pela IA.

**Características:** Write-once, replicação remota, retenção mínima de 5 anos (LGPD + CFM). Campos obrigatórios: ator (user_id ou ai_agent_id), ação, recurso, timestamp, IP, resultado.

### Regras de Separação

| Dado | Camada | Razão |
|------|--------|-------|
| CPF, nome, telefone | Transacional | Dado pessoal, ACID, LGPD |
| Diagnóstico, prescrição | Transacional (PEP) | Dado sensível, CFM, imutável |
| "Paciente prefere manhãs" | Contexto | Operacional, não-clínico |
| "Preparo de colonoscopia exige 12h jejum" | RAG | Conhecimento factual validado |
| "Paciente perguntou X, humano respondeu Y" | Decisões Reaproveitáveis | Pipeline para RAG |
| "IA bloqueou faturamento por CID incompatível" | Auditoria | Rastreabilidade regulatória |

---

## 7. GOVERNANÇA, AUTONOMIA E CONTROLE

### Matriz de Autonomia da IA

| Ação | IA sozinha | Confirmação humana | Proibido para IA |
|------|------------|-------------------|------------------|
| Responder dúvida com base no RAG (score > 0.75) | ✅ | | |
| Agendar consulta com dados completos e convênio validado | ✅ | | |
| Enviar lembrete de confirmação (template utilidade) | ✅ | | |
| Enviar NPS pós-consulta | ✅ | | |
| Remarcar consulta a pedido do paciente | ✅ | | |
| Sugerir encaixe para paciente da lista de espera | ✅ (sugerir) | ✅ (executar se regra ativa) | |
| Disparar campanha de marketing | | ✅ (gestor aprova) | |
| Fazer overbooking calculado | | ✅ (gestor configura limites) | |
| Bloquear faturamento por suspeita de glosa | ✅ (bloquear) | ✅ (liberar após revisão humana) | |
| Comunicar diagnóstico ou resultado de exame | | | ❌ (CFM 2.454) |
| Sugerir tratamento diretamente ao paciente | | | ❌ (CFM 2.454) |
| Deletar registro de prontuário | | | ❌ (imutabilidade clínica) |
| Deletar registro financeiro | | | ❌ (auditoria fiscal) |
| Enviar dados clínicos para terceiros | | | ❌ (LGPD) |

### Permissões por Perfil (RBAC)

| Perfil | Agenda | PEP | Financeiro | Relatórios | Config. IA | Auditoria |
|--------|--------|-----|------------|------------|------------|-----------|
| **Recepcionista** | Leitura/Escrita | Dados de contato apenas | Guias/Faturamento básico | Operacionais próprios | Nenhum | Nenhum |
| **Médico** | Própria agenda | Leitura/Escrita completa | Visualizar procedimentos | Próprios pacientes | Nenhum | Próprios logs |
| **Gestor** | Todas as agendas | Indicadores agregados (sem PEP individual) | Completo | Todos | Configurar réguas e limites | Visualizar |
| **Administrador** | Todas as agendas | Indicadores agregados | Completo | Todos | Completo | Completo |
| **IA** | Leitura + Escrita restrita (agendar/cancelar) | Nenhum acesso direto (via API controlada) | Validação de faturamento | Geração de relatórios | Nenhum | Gravação automática |

### Auditoria e Rastreabilidade

Toda ação da IA gera um registro com: identificador do agente, prompt utilizado (hash), contexto fornecido, resposta gerada, score de confiança, tempo de processamento, ação executada no sistema, resultado. Quando um humano faz override de uma sugestão da IA, o motivo deve ser registrado. Esses dados alimentam calibração contínua.

---

## 8. RISCOS, CONFLITOS E PONTOS DE ATENÇÃO

### Risco 1: Alucinação em Respostas de Saúde

**Impacto:** Crítico — paciente pode tomar decisão prejudicial à saúde com base em informação incorreta.
**Probabilidade:** Média (mitigada por RAG, mas nunca zero).
**Mitigação:** RAG com threshold de confiança rígido (score mínimo 0.75), system prompt restritivo proibindo especulação, disclaimers automáticos em respostas de saúde, handoff obrigatório abaixo do threshold, curadoria humana periódica do corpus, monitoramento de respostas com baixa confiança.

### Risco 2: Conflito Recepção vs. IA

**Impacto:** Alto — resistência cultural pode sabotar adoção.
**Probabilidade:** Alta (muito comum em implementações de IA).
**Mitigação:** Posicionar IA como assistente (copiloto), não substituta. Recepcionista mantém controle final. Métricas de sucesso incluem redução de carga da recepção (não redução de headcount). Treinamento prático. Início com IA apenas em horários fora do expediente, expandindo gradualmente.

### Risco 3: Dependência Excessiva da IA

**Impacto:** Alto — se a IA sair do ar, a clínica não pode parar.
**Probabilidade:** Média.
**Mitigação:** Modo degradado obrigatório: se a IA falhar, o sistema continua operando como ERP tradicional (agenda funciona sem otimização, WhatsApp cai para fila manual no painel). Cache local para operações críticas. Timeout rigoroso em chamadas de LLM (3 segundos para respostas conversacionais).

### Risco 4: Risco Jurídico / LGPD

**Impacto:** Crítico — multas, processos, dano reputacional.
**Probabilidade:** Média (depende da implementação).
**Mitigação:** Privacy by design desde o MVP. Consentimento explícito para uso de IA no atendimento. Anonimização antes de enviar dados para LLMs externos. Opção do paciente recusar interação com IA sem prejuízo. DPO integrado ao sistema com dashboards de conformidade. Logs de auditoria imutáveis.

### Risco 5: Excesso de Automação no MVP

**Impacto:** Alto — entregar demais no início aumenta bugs, atrasa lançamento e confunde o usuário.
**Probabilidade:** Alta (tentação natural de querer "mostrar tudo").
**Mitigação:** MVP brutalmente enxuto (seção 9). Funcionalidades de IA avançada (overbooking, transcrição, anti-glosa) entram apenas nas fases 2 e 3. Validação com clínica-piloto antes de expansão.

### Risco 6: Custo da API WhatsApp Descontrolado

**Impacto:** Médio — pode comprometer margem operacional.
**Probabilidade:** Média (modelo de cobrança por template em 2026).
**Mitigação:** Segmentação inteligente para campanhas de marketing (nunca disparo massivo). Priorização de templates de utilidade (custo menor e maior ROI). Dashboard de custo por disparo integrado ao financeiro. Limites configuráveis por clínica.

### Risco 7: Falha de Integração entre Atendimento e Operação

**Impacto:** Alto — agendamento via WhatsApp não reflete na agenda = caos.
**Probabilidade:** Média-baixa (se arquitetura for bem desenhada).
**Mitigação:** Arquitetura orientada a eventos com transações atômicas. Se a reserva de agenda falhar, a confirmação ao paciente não é enviada. Testes de integração automatizados cobrindo os fluxos fim a fim da seção 5.

---

## 9. PROPOSTA DE MVP CONSOLIDADO EM 30 DIAS

### Filosofia do MVP

O MVP deve provar uma tese: **"A IA pode resolver o agendamento via WhatsApp de ponta a ponta, integrada à agenda real da clínica, com qualidade suficiente para que o paciente não perceba que está falando com uma máquina na maioria dos casos."**

### Módulos no MVP

| Módulo | Escopo no MVP |
|--------|---------------|
| **A1. Cadastro de Pacientes** | CRUD básico. CPF como chave. Dados de contato e convênio. |
| **A2. Agenda** | Agenda por médico, visualização de slots, bloqueio/reserva. Blocos fixos (20min ou 30min). Sem otimização inteligente ainda. |
| **A6. Convênios** | Tabela estática de convênios aceitos por especialidade. Validação básica de elegibilidade. |
| **B1. Canal WhatsApp** | Integração com WhatsApp Business API (via BSP). Recebimento e envio de mensagens. |
| **B2. Motor Conversacional** | Orquestrador simples (roteador de intenção por classificação de texto). Agente de Linguagem para respostas. Agente de Agenda para ações transacionais. |
| **B3. Painel da Recepção** | Tela web mostrando fila de chats, com opção de assumir conversa (handoff recebido). |
| **D1. RAG (básico)** | Corpus inicial: FAQ da clínica (horários, endereço, convênios aceitos), preparos dos 10 exames mais comuns, perfil dos médicos. |
| **E1. Logs** | Registro de todas as interações (IA e humanas). |
| **E3. LGPD (básico)** | Mensagem de consentimento no primeiro contato. Opt-out disponível. |

### Capacidades de IA no MVP

- Classificação de intenção (agendar, remarcar, cancelar, dúvida, falar com humano)
- Extração de entidades (médico, especialidade, janela temporal, convênio)
- Respostas de FAQ via RAG
- Agendamento transacional completo (buscar slots → apresentar → confirmar → registrar)
- Handoff para humano (por pedido explícito, urgência detectada ou confiança baixa)
- Lembrete de confirmação T-24h (template de utilidade)

### Integrações Obrigatórias

- WhatsApp Business API (via BSP como 360dialog, Gupshup ou similar)
- Banco PostgreSQL para dados transacionais
- Banco vetorial (pgvector) para RAG
- API de LLM (Claude API ou OpenAI)

### Fluxos Funcionando Ponta a Ponta

1. Paciente manda mensagem → IA identifica intenção → agenda consulta → paciente recebe confirmação com preparo
2. Paciente pede remarcação → IA cancela original → oferece novos horários → confirma
3. Paciente faz pergunta sobre preparo de exame → RAG responde com base no manual
4. Paciente pede para falar com humano → handoff com contexto → recepcionista assume no painel
5. T-24h → sistema envia lembrete → paciente confirma ou remarca

### O que fica de fora do MVP

- Otimização inteligente de agenda (overbooking, blocos elásticos)
- Predição de no-show
- Follow-up pós-consulta e NPS
- Auditor anti-glosa
- Faturamento TISS/TUSS automatizado
- CRM conversacional
- Transcrição de consulta
- Fluxo físico e Kanban
- Dashboards analíticos avançados
- Campanhas de reativação/marketing
- Integração com múltiplos canais (só WhatsApp no MVP)

---

## 10. ROADMAP CONSOLIDADO DE 90 DIAS

### Fase 1: MVP Funcional (Dias 1-30)

**Entregas:**
- Infraestrutura base: PostgreSQL, servidor de aplicação, integração WhatsApp API
- Cadastro de pacientes e agenda funcional
- Motor conversacional com classificação de intenção e agendamento transacional
- RAG básico com FAQ, preparos e corpo clínico
- Painel web da recepção com fila de chats e handoff
- Lembrete T-24h automatizado
- Logs de auditoria e consentimento LGPD básico

**Dependências:** BSP do WhatsApp aprovado, clínica-piloto definida, corpus inicial de documentos coletado.

**Ganhos esperados:** Atendimento 24/7 no WhatsApp para agendamento. Redução imediata de carga na recepção em horário comercial. Primeiras métricas de taxa de resolução autônoma e volume de handoff.

### Fase 2: Consolidação Operacional (Dias 31-60)

**Entregas:**
- Motor de follow-up: lembretes T-48h + T-24h, NPS pós-consulta, follow-up terapêutico básico (D+8)
- CRM conversacional: timeline de interações por paciente
- Predição de no-show (modelo inicial com histórico de faltas, dia da semana, antecedência de agendamento)
- Auditor anti-glosa (versão 1): validação de CID × TUSS × cobertura básica antes do envio
- Módulo financeiro básico: contas a receber, conciliação de convênios
- Faturamento TISS simplificado: geração de lotes XML para os convênios mais comuns
- Memória contextual do paciente: preferências, score de engajamento

**Dependências:** MVP validado com clínica-piloto, dados históricos de no-show disponíveis, tabelas TISS/TUSS atualizadas.

**Ganhos esperados:** Redução de no-show de ~25% para ~10%. Primeiras glosas evitadas. Receita recorrente visível via reativação de pacientes. NPS coletado automaticamente.

### Fase 3: Inteligência Avançada e Expansão (Dias 61-90)

**Entregas:**
- Otimizador de agenda: blocos elásticos, overbooking controlado, balanceamento entre médicos
- Copiloto da recepção: sugestões de encaixe em tempo real, alertas de atraso
- Motor analítico gerencial: dashboard operacional, detecção de anomalias, narrativas analíticas
- Campanhas de preenchimento de agenda ociosa (integração follow-up + otimizador)
- Enriquecimento do RAG via pipeline de decisões humanas (D3)
- Painel de governança IA: métricas de confiança, handoff rate, override humano

**Dependências:** Dados de 60 dias de operação para calibrar modelos preditivos. Feedback da recepção sobre usabilidade do copiloto.

**Ganhos esperados:** Ocupação de agenda maximizada. Gestão por dados em tempo real. Recepção operando como equipe assistida. Base de conhecimento RAG em crescimento contínuo.

---

## 11. PRIORIZAÇÃO MoSCoW CONSOLIDADA

### MUST — Obrigatório para o produto existir

| Funcionalidade | Justificativa |
|----------------|---------------|
| Agendamento via WhatsApp com IA | Core da proposta de valor. Sem isso, é só mais um ERP. |
| Agenda multiprofissional digital | Sem agenda, não há operação de clínica. |
| RAG para FAQ e preparos de exames | Diferencia de chatbot burro. Respostas precisas reduzem handoff. |
| Handoff para humano com contexto | Sem isso, paciente fica preso no bot = destruição de confiança. |
| Painel da recepção com fila unificada | Recepcionista precisa de uma tela para trabalhar. |
| Lembrete de confirmação T-24h | ROI mais direto: reduz no-show imediatamente. |
| Cadastro de pacientes com convênio | Base de tudo. Sem cadastro, nada funciona. |
| Logs de auditoria | LGPD e CFM exigem. Não é opcional. |
| Consentimento LGPD | Obrigação legal. |
| Validação básica de elegibilidade | Sem isso, agenda convênio não aceito = retrabalho. |

### SHOULD — Alto valor, implementar logo após o MVP

| Funcionalidade | Justificativa |
|----------------|---------------|
| Predição de no-show | Alto impacto financeiro. Modelo simples já entrega valor. |
| Follow-up pós-consulta e NPS | Ataca evasão de 40-60%. Custo baixo, impacto alto. |
| Auditor anti-glosa | ROI financeiro direto. Cada glosa evitada é receita. |
| CRM conversacional | Dá contexto ao atendimento. Paciente percebe que é lembrado. |
| Faturamento TISS básico | Commodity do setor. Sem isso, clínica com convênio não opera. |
| Memória contextual do paciente | Personalização eleva satisfação e conversão. |

### COULD — Desejável, diferencial competitivo

| Funcionalidade | Justificativa |
|----------------|---------------|
| Otimização de agenda com blocos elásticos | Diferencial real vs. agendas estáticas tradicionais. |
| Copiloto da recepção em tempo real | "Wow factor" mas depende de maturidade do sistema. |
| Dashboard analítico com narrativas | Valor gerencial alto, mas gestores podem esperar. |
| Campanhas de reativação segmentadas | Marketing inteligente, mas requer base de dados madura. |
| Overbooking calculado | Otimização avançada. Requer dados históricos. |
| Pipeline de enriquecimento do RAG | Melhoria contínua da base de conhecimento. |
| Transcrição de consulta (copiloto clínico) | Alto impacto para médico, mas complexidade regulatória enorme. |

### WON'T FOR NOW — Visão futura, não para os próximos 90 dias

| Funcionalidade | Justificativa |
|----------------|---------------|
| Visão computacional e fluxo físico | Exige hardware, edge computing, investimento alto. |
| Kanban de pacientes no espaço | Depende de visão computacional. |
| SAD de apoio ao diagnóstico | Regulação CFM severíssima. Fine-tuning complexo. Risco altíssimo. |
| Integração HL7 FHIR completa | Importante para interoperabilidade futura, mas não bloqueia MVP. |
| Multicanal (Instagram, webchat) | WhatsApp resolve 90% no Brasil. Outros canais podem esperar. |
| Integração com laboratórios externos | Valor alto, mas complexidade de parceria. |
| Teleconsulta embarcada | Concorrência já estabelecida. Melhor integrar via API. |

---

## 12. KPIs E MÉTRICAS DO PRODUTO COMPLETO

### Operação da Clínica

| KPI | Por que importa | Como orienta o produto |
|-----|----------------|----------------------|
| **Taxa de Ocupação de Agenda** (%) | Mede eficiência do ativo mais caro: tempo do médico. | Se baixa, ativa otimizador e campanhas de preenchimento. |
| **Tempo Médio de Espera na Recepção** (min) | Correlação direta com NPS e percepção de qualidade. | Se alto, valida necessidade do copiloto de recepção. |
| **Tempo Médio entre Check-in e Início da Consulta** (min) | Mede eficiência do fluxo interno. | Justifica investimento em fluxo físico inteligente (fase 4). |

### Agenda

| KPI | Por que importa | Como orienta o produto |
|-----|----------------|----------------------|
| **Taxa de No-Show** (%) | Cada falta = receita perdida irrecuperável. Meta: <10%. | Principal métrica de sucesso do modelo preditivo + lembretes. |
| **Taxa de Remarcação** (%) | Diferencia cancelamento (perde) de remarcação (retém). | Se alta, IA está facilitando remarcar em vez de faltar. Bom sinal. |
| **Taxa de Encaixe após Cancelamento** (%) | Mede velocidade de recuperação de slots perdidos. | Valida eficácia do otimizador + lista de espera inteligente. |

### Atendimento com IA

| KPI | Por que importa | Como orienta o produto |
|-----|----------------|----------------------|
| **Taxa de Resolução Autônoma** (%) | % de interações resolvidas sem humano. Meta: >60%. | Mede maturidade da IA. Se baixa, RAG precisa de enriquecimento. |
| **Taxa de Handoff** (%) | Complemento da resolução autônoma. | Se alta demais, IA não está resolvendo. Se zero, talvez não esteja transferindo quando deveria. |
| **Tempo Médio de Primeira Resposta** (seg) | Paciente abandona se não recebe resposta em minutos. | Mede performance técnica do sistema. |
| **Score Médio de Confiança RAG** | Mede qualidade das respostas geradas. | Se caindo, corpus precisa de atualização. |

### Follow-up e Conversão

| KPI | Por que importa | Como orienta o produto |
|-----|----------------|----------------------|
| **Taxa de Confirmação por Lembrete** (%) | Mede eficácia dos lembretes na redução de no-show. | Se baixa, mudar cadência ou formato do template. |
| **Taxa de Retorno (Retenção)** (%) | % de pacientes que voltam após primeira consulta. Meta: >60%. | Valida régua de follow-up e relacionamento. |
| **NPS** | Termômetro geral de satisfação. | Detratores geram alerta de ouvidoria. Promotores = candidatos a indicação. |
| **LTV do Paciente** (R$) | Valor total gerado por paciente ao longo do tempo. | Justifica investimento em retenção vs. aquisição. |

### Eficiência da Recepção

| KPI | Por que importa | Como orienta o produto |
|-----|----------------|----------------------|
| **Volume de Atendimentos por Recepcionista/dia** | Mede produtividade. | Se subindo com IA, valida que IA está aliviando carga. |
| **Tempo Médio de Resolução de Chat** (min) | Mede eficiência do atendimento digital. | Se caindo, IA está resolvendo mais rápido. |

### Financeiro

| KPI | Por que importa | Como orienta o produto |
|-----|----------------|----------------------|
| **Taxa de Glosa** (%) | Cada glosa = receita perdida. Meta: <5%. | Principal métrica do auditor anti-glosa. |
| **Ciclo de Conversão de Caixa** (dias) | Tempo entre atendimento e recebimento. | Se encurtando, faturamento está mais eficiente. |
| **Receita por Slot de Agenda** (R$) | Mede monetização do tempo médico. | Se subindo, otimização de agenda está funcionando. |

### Qualidade da Automação

| KPI | Por que importa | Como orienta o produto |
|-----|----------------|----------------------|
| **Taxa de Override Humano** (%) | Quando humano rejeita sugestão da IA. | Se alta, IA está errando. Precisa recalibrar. |
| **Taxa de Alucinação Detectada** (%) | Respostas sem base no RAG. | Deve ser zero. Qualquer ocorrência = investigação. |
| **Custo por Interação de IA** (R$) | Custo de API de LLM + WhatsApp por atendimento. | Monitorar para garantir viabilidade econômica. |

---

## 13. DIFERENCIAIS E POSICIONAMENTO DE PRODUTO

### vs. Chatbot Comum (Cloudia, Secretária IA)

O chatbot comum vive isolado na porta de entrada. Ele agenda, mas não sabe se o convênio cobre, não previne glosa, não faz follow-up inteligente, não alimenta a gestão. **O diferencial é a integração vertical**: a mesma IA que conversa é a que agenda, que dispara o lembrete, que previne a glosa do faturamento gerado por aquela consulta e que reativa o paciente 6 meses depois.

### vs. Sistema de Agenda Comum (iClinics, Versatilis)

Agendas tradicionais são estáticas — blocos fixos, sem predição, sem otimização. **O diferencial é a agenda viva**: blocos elásticos por perfil do paciente, previsão de no-show que ajusta automaticamente a cadência de confirmação, overbooking calculado matematicamente, recuperação automática de slots via lista de espera inteligente.

### vs. CRM Comum (RD Station, HubSpot)

CRMs genéricos não entendem a jornada clínica. Não sabem que um paciente que tomou antibiótico precisa de follow-up no D+8, não sabem que uma paciente ginecológica deve retornar em 6 meses. **O diferencial é o CRM clínico**: réguas baseadas em eventos do prontuário, não em pipeline de vendas. A "conversão" aqui é retorno terapêutico, não lead.

### vs. Software de Clínica Tradicional (MedPlus, Doctor Max)

Softwares tradicionais são repositórios passivos — armazenam dados, mas não agem. **O diferencial é a proatividade**: o sistema não espera o gestor pedir relatório, ele detecta o padrão e alerta. Não espera a recepcionista perceber o atraso, ele já notificou os pacientes. Não espera a glosa acontecer, ele bloqueou o envio antes.

### O que torna o produto defensável

1. **Efeito de rede interna de dados**: quanto mais a clínica usa, mais dados alimentam os modelos preditivos (no-show, glosa, otimização), gerando vantagem crescente.
2. **Base de conhecimento RAG proprietária**: cada clínica acumula um corpus de respostas validadas que é caro de replicar.
3. **Integração vertical completa**: a barreira de entrada para um concorrente replicar atendimento + agenda + faturamento + IA + follow-up é enorme.
4. **Lock-in operacional positivo**: uma vez que a recepção opera com o copiloto e o médico com o prontuário otimizado, voltar para o modelo antigo é inaceitável.

---

## 14. ARQUITETURA FUNCIONAL UNIFICADA

### Diagrama em Camadas

```
┌─────────────────────────────────────────────────────────────────┐
│                    CANAIS DE ENTRADA                             │
│  WhatsApp API  │  Webchat (futuro)  │  Painel Recepção  │ API   │
└────────┬───────┴──────────┬─────────┴──────────┬────────┴───────┘
         │                  │                    │
┌────────▼──────────────────▼────────────────────▼────────────────┐
│                CAMADA DE ATENDIMENTO                             │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────┐   │
│  │ Orquestrador │─▶│  Agente de   │  │    Motor de          │   │
│  │   Central    │  │  Linguagem   │  │    Handoff           │   │
│  └──────┬───────┘  └──────────────┘  └──────────────────────┘   │
│         │                                                        │
│  ┌──────▼───────┐  ┌──────────────┐  ┌──────────────────────┐   │
│  │  Agente de   │  │   Motor      │  │    Motor de          │   │
│  │    Agenda    │  │    RAG       │  │    Follow-up         │   │
│  └──────────────┘  └──────────────┘  └──────────────────────┘   │
└─────────────────────────┬───────────────────────────────────────┘
                          │ Event Bus (Eventos Tipados)
┌─────────────────────────▼───────────────────────────────────────┐
│               CAMADA OPERACIONAL DA CLÍNICA                      │
│  ┌──────────┐  ┌─────────┐  ┌───────────┐  ┌────────────────┐  │
│  │ Cadastro │  │ Agenda  │  │    PEP    │  │  Faturamento   │  │
│  │ Paciente │  │ Multi.  │  │           │  │  TISS/TUSS     │  │
│  └──────────┘  └─────────┘  └───────────┘  └────────────────┘  │
│  ┌──────────┐  ┌─────────┐  ┌───────────┐                      │
│  │Financeiro│  │Convênios│  │ Copiloto  │                      │
│  │          │  │         │  │ Recepção  │                      │
│  └──────────┘  └─────────┘  └───────────┘                      │
└─────────────────────────┬───────────────────────────────────────┘
                          │
┌─────────────────────────▼───────────────────────────────────────┐
│                  CAMADA DE INTELIGÊNCIA                           │
│  ┌─────────────┐  ┌──────────────┐  ┌────────────────────────┐  │
│  │ Otimizador  │  │   Auditor    │  │    Motor Analítico     │  │
│  │  de Agenda  │  │  Anti-Glosa  │  │    Gerencial           │  │
│  └─────────────┘  └──────────────┘  └────────────────────────┘  │
└─────────────────────────┬───────────────────────────────────────┘
                          │
┌─────────────────────────▼───────────────────────────────────────┐
│                   CAMADA DE DADOS                                │
│  ┌────────────────┐  ┌──────────────┐  ┌─────────────────────┐  │
│  │   PostgreSQL   │  │  pgvector    │  │   Logs Imutáveis    │  │
│  │ (Transacional) │  │   (RAG)      │  │   (Auditoria)       │  │
│  └────────────────┘  └──────────────┘  └─────────────────────┘  │
│  ┌────────────────┐  ┌──────────────┐                           │
│  │   Memória      │  │   Decisões   │                           │
│  │  Contextual    │  │ Reaproveit.  │                           │
│  └────────────────┘  └──────────────┘                           │
└─────────────────────────────────────────────────────────────────┘
```

### Fluxo de Dados entre Camadas

**De cima para baixo:** Evento entra pelo canal → Orquestrador classifica → despacha para agente especialista → agente executa ação na camada operacional → registra na camada de dados.

**De baixo para cima:** Evento operacional (consulta finalizada, agenda alterada, no-show detectado) → publicado no event bus → consumido pela camada de inteligência (predição, auditoria, análise) → resultado entregue via camada de atendimento (follow-up, alerta para recepção) ou camada operacional (dashboard gerencial).

### Como Evitar Acoplamento Excessivo

1. **Event bus como espinha dorsal**: módulos não se chamam diretamente. Publicam eventos tipados (ex: `agenda.slot_cancelado`, `consulta.finalizada`, `faturamento.glosa_detectada`) e outros se inscrevem.
2. **APIs internas com contratos**: cada módulo expõe API REST com schema definido. Mudanças são versionadas.
3. **Banco de dados não compartilhado entre camadas**: a camada de atendimento não faz SELECT direto na tabela de prontuário. Acessa via API do módulo PEP, que aplica RBAC.

### Como Permitir Expansão Futura

A arquitetura orientada a eventos permite adicionar novos agentes (ex: Agente de Teleconsulta, Agente de Estoque) sem alterar os existentes. Basta que o novo agente se inscreva nos eventos relevantes e exponha suas APIs. O Orquestrador aprende a despachar para ele via configuração, não via reescrita de código.

---

## 15. RECOMENDAÇÃO FINAL DE PRODUTO

### Posicionamento

Posicionar como **"Sistema Operacional da Clínica Médica com IA"** — não como chatbot, não como ERP, não como CRM. É a plataforma que unifica tudo. O pitch é: "Você não precisa de 5 ferramentas. Precisa de uma que entende que o agendamento, o atendimento, o faturamento e o follow-up são a mesma jornada."

### O que construir primeiro

O **agendamento via WhatsApp integrado à agenda real**, com RAG para dúvidas e handoff para humano. Isso resolve a dor mais aguda (recepção sobrecarregada, pacientes não respondidos fora do horário) e é o ponto de entrada natural para demonstrar valor. Toda clínica que recebe 200+ mensagens por dia no WhatsApp sente essa dor.

### O que gera valor mais rápido

1. **Lembretes inteligentes de confirmação** → redução de no-show = receita recuperada no dia seguinte. ROI imediato.
2. **Agendamento 24/7 via WhatsApp** → captura de pacientes que mandavam mensagem à noite e não eram respondidos.
3. **Auditor anti-glosa** → cada glosa evitada é R$ direto no caixa. Clínicas que faturam convênio sentem isso em semanas.

### O que é mais sensível e exige mais controle

1. **Qualquer coisa que toque dados clínicos** (prontuário, diagnóstico, prescrição) → LGPD + CFM = risco jurídico máximo. Copiloto clínico e SAD são fase 3+ com validação médica rigorosa.
2. **Respostas de saúde via RAG** → alucinação = risco de dano ao paciente. Threshold de confiança alto, disclaimers automáticos, curadoria constante do corpus.
3. **Overbooking** → se mal calibrado, superlota e destrói experiência. Só com dados históricos sólidos e limites configuráveis.

### Arquitetura mais sustentável para escalar

**Microserviços orientados a eventos, API-first**, com PostgreSQL como banco transacional e pgvector para RAG. Não começar com arquitetura multi-agente completa no dia 1 — começar com um orquestrador simples (classificação de intenção + dispatch para funções) e evoluir para MAS quando houver complexidade real que justifique.

O erro mais comum seria tentar construir a orquestração MAS perfeita antes de ter os agentes funcionando. A recomendação é: **faça cada agente funcionar bem isoladamente, depois conecte-os**. O Orquestrador Central vem por último, quando já existe o que orquestrar.

A decisão entre LLM em nuvem (API) vs. on-premises deve ser pragmática: **nuvem no MVP** (menor investimento, mais rápido), com arquitetura que permita migração para modelos locais quando volume e regulação justificarem.

### Resumo Executivo

Este produto não é um chatbot com agenda. É uma plataforma que trata a clínica médica como um sistema integrado onde **cada dado nasce uma vez e serve a toda a cadeia** — do primeiro WhatsApp do paciente até o faturamento da operadora, passando pelo follow-up que traz o paciente de volta. A IA não substitui ninguém: ela absorve o trabalho repetitivo e cognitivamente exaustivo para que a recepcionista acolha, o médico escute e o gestor decida com dados. Construir isso de forma incremental — provando valor em 30 dias, consolidando em 60 e expandindo em 90 — é a única abordagem realista para um produto dessa ambição.
