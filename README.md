# ⚡ PriceGlitch & Drop Agent v1.0

Um caçador autônomo multi-marketplace especializado em detectar **erros de precificação (glitches)**, **quedas bruscas de preço** e **mínimos históricos** na **Amazon**, **Mercado Livre** e **Shopee**, convertendo os links em afiliação e disparando alertas imediatos com copy de urgência e FOMO no **Telegram**.

---

## 🏛️ Arquitetura do Sistema

```
c:\Agentes\Error_price\
├── config/
│   └── settings.py          # Gerenciamento de variáveis de ambiente e parâmetros
├── database/
│   └── db.py                # Camada SQLite (produtos, histórico de preços e cooldown de alertas)
├── scrapers/
│   ├── base.py              # Interface abstrata e modelo de dados ScrapedProduct
│   ├── amazon.py            # Coletor Amazon com bypass TLS e filtro 40%+
│   ├── mercadolivre.py      # Coletor Mercado Livre (Ofertas do Dia e Relâmpago)
│   └── shopee.py            # Coletor Shopee (Flash Sales e endpoints públicos)
├── engine/
│   ├── glitch_filter.py     # Filtro de falsos positivos (acessórios, capas, preços zerados)
│   └── anomaly.py           # Motor estatístico (Z-Score, desvio padrão, quedas > 40%/65%)
├── monetizer/
│   └── affiliate.py         # Conversor de links brutos em links de afiliados (Amazon, ML, Shopee, Lomadee)
├── notifier/
│   ├── telegram.py          # Disparador Telegram com foto, botões inline e modo Dry-Run
│   └── copywriter.py        # Copywriting focado em urgência ("erro do estagiário") + IA Gemini opcional
├── .env.example             # Modelo de configuração de ambiente
├── requirements.txt         # Dependências do projeto
├── main.py                  # Orquestrador CLI e loop contínuo do agente
└── README.md                # Documentação técnica
```

---

## 🚀 Como Executar

### 1. Configurar o Ambiente (.env)
Copie o arquivo de exemplo e preencha suas chaves e tags:
```bash
cp .env.example .env
```
Variáveis principais:
- `TELEGRAM_BOT_TOKEN`: Token gerado pelo `@BotFather`.
- `TELEGRAM_CHAT_ID`: ID do chat, grupo ou canal de promoções.
- `AMAZON_TAG`: Sua tag de associado Amazon (ex: `suatag-20`).
- `MERCADOLIVRE_AFFILIATE_TAG`: Tag do programa de afiliados do Mercado Livre.
- `GEMINI_API_KEY`: *(Opcional)* Chave de API do Google Gemini para copies geradas por IA.

### 2. Teste Rápido (Modo Dry-Run / Preview)
Executa uma varredura demonstrativa em todos os marketplaces e exibe as mensagens formatadas no terminal (sem necessidade de configurar o bot do Telegram de imediato):
```bash
python main.py --test
```

### 3. Execução em Marketplace Específico
```bash
# Apenas Amazon
python main.py --once --marketplace amazon

# Apenas Mercado Livre
python main.py --once --marketplace mercadolivre

# Apenas Shopee
python main.py --once --marketplace shopee
```

### 4. Modo Contínuo (Caçador 24/7)
Inicia o ciclo automatizado que executa a cada intervalo de minutos configurado:
```bash
python main.py --interval 30
```

### 5. Micro-Página Web & Histórico (FastAPI)
Inicia o servidor web local com gráficos interativos em tempo real:
```bash
python main.py --web
# Acesse em: http://127.0.0.1:8000
```

### 6. Exportar para GitHub Pages (Hospedagem 100% Gratuita)
Gera os arquivos estáticos na pasta `docs/` prontos para publicação:
```bash
python main.py --export-gh
```

### 7. Consultar Histórico e Estatísticas do SQLite
Exibe o total de produtos monitorados, leituras de preços e alertas já salvos:
```bash
python main.py --stats
```


---

## 🧠 Como Funciona o Algoritmo de Detecção

1. **Bypass de Proteção (Resiliente):**
   Utiliza `curl_cffi` para impersonar assinaturas TLS de navegadores reais (Chrome), contornando bloqueios de bots e requisições 503 na Amazon e Mercado Livre sem custos com proxies pesados.

2. **Filtro de Falsos Positivos (`GlitchFilter`):**
   Impede que capas, películas ou cabos de R$ 20 sejam confundidos com um iPhone ou notebook com 95% de desconto. Também rejeita produtos sem estoque ou abaixo de um piso mínimo configurado.

3. **Classificação de Anomalias (`AnomalyDetector`):**
   - 🚨 **`GLITCH_EXTREME`:** Queda $\ge 65\%$ sobre o preço de tabela **OU** preço $\ge 45\%$ abaixo do menor valor histórico registrado para aquele item **OU** Z-Score $\le -2.5$.
   - ⚡ **`FLASH_DROP`:** Desconto expressivo $\ge 40\%$ em itens de tecnologia/casa.
   - 📉 **`HISTORICAL_LOW`:** Menor preço já registrado na memória SQLite para o produto com pelo menos 20% de desconto.

4. **Cooldown Inteligente:**
   Evita spam no canal. Um mesmo produto não é alertado novamente no período de cooldown (padrão 12h), a menos que o preço caia **mais 10%** em relação ao último alerta disparado.

5. **Copywriting com Gatilhos de Ação Imediata:**
   Textos com foco em urgência, destacando o preço original riscado, o preço anômalo atual e o botão direto para o carrinho via link de afiliado.
