Quero que você prepare o projeto para eu testar na VPS via **Dokploy com Docker Compose** e, ao final, faça **commit e push na branch atual** ou na branch apropriada, deixando tudo organizado para deploy.

## Objetivo
Preciso subir o projeto na VPS porque lá fica mais fácil debugar.  
Quero que você:

1. revise o estado atual do projeto para deploy
2. ajuste o que for necessário para rodar via **Docker Compose**
3. me entregue um arquivo de ambiente modelo com base no projeto local
4. documente claramente todas as variáveis de ambiente
5. faça **commit e push**
6. me explique exatamente o que foi alterado e o que preciso configurar na VPS

---

## Contexto obrigatório
- O deploy será feito no **Dokploy**
- O método de deploy é **Docker Compose**
- Quero usar a VPS como ambiente de teste/debug
- Preciso de uma visão clara de **toda a configuração de env**
- O projeto deve ficar pronto para eu subir no Dokploy sem adivinhação

---

## O que você deve fazer

### 1. Auditoria de deploy
Analise o projeto e me diga:
- qual serviço sobe no compose
- quais containers existem
- quais portas internas cada serviço usa
- quais portas/hosts/domínios precisam ser configurados
- quais volumes persistentes existem ou deveriam existir
- quais dependências precisam subir juntas
- quais serviços são obrigatórios e quais são opcionais
- quais healthchecks existem
- quais pontos podem quebrar no ambiente de VPS

---

### 2. Revisão do Docker Compose
Revise o `docker-compose.yml` e ajuste o que for necessário para uso real no Dokploy.

Quero que você valide:
- nomes dos serviços
- build contexts
- Dockerfiles
- comandos de start
- env_file / environment
- depends_on
- healthchecks
- volumes
- networking
- restart policies
- compatibilidade com Dokploy
- se há algo no compose que funciona localmente mas tende a quebrar na VPS

Se precisar, corrija o compose.

---

### 3. Arquivo de ambiente para VPS
Crie um arquivo modelo para eu usar na VPS, por exemplo:
- `.env.vps.example`
ou
- `.env.production.example`

Esse arquivo deve conter **todas as variáveis realmente usadas pelo projeto**.

Regras:
- não invente variáveis
- não deixe faltar variáveis necessárias
- não copie segredos reais
- use placeholders claros
- agrupe por seção

Exemplo de organização esperada:
- app
- banco
- frontend
- backend
- auth
- telegram
- openai / anthropic / gemini
- rag
- qdrant / pgvector
- google
- redis / workers
- urls públicas
- domínios / cors
- branding / clínica
- observabilidade

---

### 4. Mapa completo de env
Quero um documento explicando **toda a configuração de ambiente do projeto**.

Crie um markdown como:
`docs/deployment/ENV_REFERENCE.md`

Para cada variável, documente:
- nome
- onde é usada
- se é obrigatória ou opcional
- valor de exemplo
- impacto no sistema
- observações importantes

Quero também:
- quais variáveis são obrigatórias no ambiente local
- quais são obrigatórias na VPS
- quais variáveis são de backend
- quais são de frontend
- quais impactam integrações
- quais impactam deploy no Dokploy
- quais impactam Docker Compose

---

### 5. Checagem de prontidão para VPS
Crie um checklist objetivo do que eu preciso configurar na VPS/Dokploy.

Exemplo do que quero nesse checklist:
- domínio/subdomínio
- portas
- DNS
- envs obrigatórias
- volumes persistentes
- banco
- redis
- webhook do Telegram
- URLs públicas do frontend/backend
- CORS
- healthcheck URLs
- ordem de validação depois que subir

Crie isso em:
`docs/deployment/VPS_DEPLOY_CHECKLIST.md`

---

### 6. Revisão de URLs e deploy real
Verifique no projeto:
- quais URLs precisam ser públicas
- quais endpoints de health devo usar
- quais callbacks/webhooks dependem de URL pública
- quais variáveis NEXT_PUBLIC ou equivalentes precisam apontar para o backend real
- o que precisa mudar do local para a VPS

Quero que isso fique explícito.

---

### 7. Commit e push
Depois de ajustar tudo:
- faça commit com uma mensagem clara
- faça push para o repositório remoto
- me informe:
  - nome da branch
  - hash do commit
  - resumo das mudanças

---

## Restrições importantes
- Não reescreva o projeto inteiro
- Não mude arquitetura sem necessidade
- Foque em preparar o projeto para deploy real via Dokploy + Docker Compose
- Preserve o runtime real atual
- Não remova funcionalidades existentes sem motivo
- Não invente infraestrutura fora do que o projeto já usa
- Se encontrar problemas, corrija de forma mínima e prática

---

## Entregas obrigatórias
Quero que você entregue no final:

1. ajustes reais no projeto para deploy
2. `docker-compose.yml` revisado/corrigido se necessário
3. arquivo `.env.vps.example` ou equivalente
4. `docs/deployment/ENV_REFERENCE.md`
5. `docs/deployment/VPS_DEPLOY_CHECKLIST.md`
6. commit realizado
7. push realizado
8. resumo final com:
   - o que foi alterado
   - o que eu preciso preencher no env
   - como subir no Dokploy
   - quais serviços devo observar primeiro nos logs

---

## Formato da resposta final
Quero sua resposta final organizada assim:

### 1. Diagnóstico do deploy
### 2. Arquivos alterados
### 3. Arquivo de env criado
### 4. Mapa de variáveis de ambiente
### 5. Checklist de deploy na VPS
### 6. Commit e push
### 7. Próximos passos para eu testar no Dokploy