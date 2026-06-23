╔══════════════════════════════════════════════════════════════════╗
║                    SISTEMA 4X CRM                               ║
║         Sistema para gestão de leads via Google Ads             ║
╚══════════════════════════════════════════════════════════════════╝

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 COMO RODAR O SISTEMA (PASSO A PASSO)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

1. ABRIR O TERMINAL (PowerShell)
   ─────────────────────────────
   Pressione as teclas  Windows + X  e clique em "Terminal" ou
   "Windows PowerShell".

2. NAVEGAR ATÉ A PASTA DO PROJETO
   ────────────────────────────────
   Digite o comando abaixo e pressione Enter:

   cd "C:\Users\danie\OneDrive\Documentos\Gestão de tráfego\CRM"

3. INSTALAR AS DEPENDÊNCIAS (só na primeira vez)
   ────────────────────────────────────────────
   Digite e pressione Enter:

   pip install flask

   Aguarde até aparecer "Successfully installed flask".

4. INICIAR O SISTEMA
   ──────────────────
   Digite e pressione Enter:

   python app.py

   Você verá esta mensagem:
   ✅ CRM iniciado com sucesso!
   📌 Acesse: http://localhost:5000

5. ACESSAR NO NAVEGADOR
   ──────────────────────
   Abra o Google Chrome (ou qualquer navegador) e acesse:

   http://localhost:5000

   O sistema abrirá com 6 leads de exemplo já cadastrados.

6. PARAR O SISTEMA
   ─────────────────
   No terminal, pressione  Ctrl + C  para encerrar.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 PRÓXIMAS VEZES (uso diário)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Você só precisa fazer os passos 1, 2 e 4 (pip install não é mais
necessário após a primeira vez).

Dica: crie um arquivo "iniciar.bat" com o conteúdo:
   python "C:\Users\danie\OneDrive\Documentos\Gestão de tráfego\CRM\app.py"
E dê dois cliques nele para iniciar sem abrir o terminal.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 FUNCIONALIDADES
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

• Pipeline Kanban com drag-and-drop
• Regras de transição entre etapas (campos obrigatórios)
• Cadastro completo de leads
• Histórico de interações com timeline
• Dashboard com gráficos e alertas de follow-up
• Busca e filtros por etapa, origem e segmento
• Dados salvos em arquivo local (banco.db)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 ESTRUTURA DE ARQUIVOS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

CRM/
├── app.py              ← Servidor Flask (backend)
├── banco.db            ← Banco de dados (criado automaticamente)
├── requirements.txt    ← Dependências Python
├── README.txt          ← Este arquivo
├── templates/          ← Páginas HTML
│   ├── base.html
│   ├── dashboard.html
│   ├── pipeline.html
│   ├── leads.html
│   ├── lead_detalhe.html
│   └── form_lead.html
└── static/
    ├── css/style.css   ← Estilos
    └── js/
        ├── app.js      ← JavaScript geral
        └── kanban.js   ← Lógica do drag-and-drop

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
