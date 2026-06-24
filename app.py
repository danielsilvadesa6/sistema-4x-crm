from flask import Flask, render_template, request, jsonify, redirect, url_for, make_response
import sqlite3
import os
import re
from datetime import datetime, timedelta
from fpdf import FPDF
from fpdf.enums import XPos, YPos

app = Flask(__name__)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH  = os.path.join(BASE_DIR, "banco.db")

DATABASE_URL = os.environ.get("DATABASE_URL", "")
USE_PG = bool(DATABASE_URL)

if USE_PG:
    import psycopg2
    import psycopg2.extras

ETAPAS          = ["Novo Lead", "Tentando Contato", "Contato Feito", "Consulta Agendada", "Fechado", "Perdido"]
SEGMENTOS       = ["Advocacia", "Clínica Médica", "Odontologia", "Psicologia", "Veterinária", "Outro"]
ORIGENS         = ["Google Ads", "Instagram", "Indicação", "Site", "WhatsApp direto", "Outro"]
TIPOS_INTERACAO = ["WhatsApp", "Ligação", "E-mail", "Reunião", "Presencial", "Outro"]

# ─── Camada de compatibilidade SQLite ↔ PostgreSQL ───────────────────────────

_SQLITE_ADAPT = [
    ("criado_em::timestamp >= NOW() - INTERVAL '30 days'",   "criado_em >= datetime('now', '-30 days', 'localtime')"),
    ("criado_em::timestamp >= NOW() - INTERVAL '12 months'", "criado_em >= datetime('now', '-12 months', 'localtime')"),
    ("TO_CHAR(criado_em::timestamp, 'YYYY-MM')",             "strftime('%Y-%m', criado_em)"),
    ("DEFAULT NOW()::text",                                  "DEFAULT (datetime('now', 'localtime'))"),
    ("NOW()::text",                                          "datetime('now', 'localtime')"),
    ("NOW()",                                                "datetime('now', 'localtime')"),
    ("%s",                                                   "?"),
    ("SERIAL PRIMARY KEY",                                   "INTEGER PRIMARY KEY AUTOINCREMENT"),
]

def _adapt(query):
    if USE_PG:
        return query
    for pg, sq in _SQLITE_ADAPT:
        query = query.replace(pg, sq)
    return query


class CompatRow(dict):
    """Dict que também aceita acesso por índice inteiro (row[0])."""
    def __getitem__(self, key):
        if isinstance(key, int):
            return list(self.values())[key]
        return super().__getitem__(key)


class CompatCursor:
    """Wrapper sobre cursor do psycopg2 ou sqlite3 com API uniforme."""
    def __init__(self, cur, pg=False):
        self._cur = cur
        self._pg  = pg

    def fetchone(self):
        row = self._cur.fetchone()
        if row is None:
            return None
        return CompatRow(row) if self._pg else row

    def fetchall(self):
        rows = self._cur.fetchall()
        return [CompatRow(r) for r in rows] if self._pg else rows

    def __iter__(self):
        for row in self._cur:
            yield CompatRow(row) if self._pg else row

    @property
    def lastrowid(self):
        return self._cur.lastrowid


class DB:
    """Conexão unificada SQLite / PostgreSQL."""

    def __init__(self):
        if USE_PG:
            url = DATABASE_URL.replace("postgres://", "postgresql://", 1)
            self._conn = psycopg2.connect(url)
        else:
            self._conn = sqlite3.connect(DB_PATH)
            self._conn.row_factory = sqlite3.Row
            self._conn.execute("PRAGMA foreign_keys = ON")

    def execute(self, query, params=()):
        q = _adapt(query)
        if USE_PG:
            cur = self._conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            cur.execute(q, list(params) if params else [])
            return CompatCursor(cur, pg=True)
        else:
            return CompatCursor(self._conn.execute(q, params), pg=False)

    def commit(self):
        self._conn.commit()

    def close(self):
        try:
            self._conn.close()
        except Exception:
            pass


def get_db():
    return DB()


# ─── Inicialização do banco ───────────────────────────────────────────────────

def init_db():
    conn = get_db()

    conn.execute("""
        CREATE TABLE IF NOT EXISTS leads (
            id             SERIAL PRIMARY KEY,
            nome           TEXT NOT NULL,
            whatsapp       TEXT NOT NULL,
            email          TEXT,
            segmento       TEXT,
            origem         TEXT,
            observacoes    TEXT,
            etapa          TEXT DEFAULT 'Novo Lead',
            valor_servico  REAL,
            data_consulta  TEXT,
            hora_consulta  TEXT,
            motivo_perda   TEXT,
            custo_aquisicao REAL,
            lembrete_em    TEXT,
            lembrete_nota  TEXT,
            criado_em      TEXT DEFAULT NOW()::text,
            atualizado_em  TEXT DEFAULT NOW()::text
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS interacoes (
            id        SERIAL PRIMARY KEY,
            lead_id   INTEGER NOT NULL,
            tipo      TEXT NOT NULL,
            anotacao  TEXT,
            data_hora TEXT DEFAULT NOW()::text,
            FOREIGN KEY (lead_id) REFERENCES leads(id) ON DELETE CASCADE
        )
    """)
    conn.commit()

    # Migração de banco existente: adiciona colunas novas se não existirem
    if USE_PG:
        colunas = [r["column_name"] for r in conn.execute(
            "SELECT column_name FROM information_schema.columns WHERE table_name = 'leads'"
        ).fetchall()]
    else:
        colunas = [r[1] for r in conn.execute("PRAGMA table_info(leads)").fetchall()]

    for col, tipo in [("custo_aquisicao", "REAL"), ("lembrete_em", "TEXT"), ("lembrete_nota", "TEXT")]:
        if col not in colunas:
            conn.execute(f"ALTER TABLE leads ADD COLUMN {col} {tipo}")
    conn.commit()

    # Dados de exemplo apenas se o banco estiver vazio
    if conn.execute("SELECT COUNT(*) FROM leads").fetchone()[0] == 0:
        seed_data(conn)
        conn.commit()

    conn.close()


def seed_data(conn):
    now = datetime.now()

    def dt(days_ago, hour=10):
        return (now - timedelta(days=days_ago)).replace(hour=hour, minute=0, second=0).strftime("%Y-%m-%d %H:%M:%S")

    def d(days_ago):
        return (now - timedelta(days=days_ago)).strftime("%Y-%m-%d")

    leads = [
        # Google Ads (10 leads)
        ("Dr. Rafael Borges",   "11991110001", "rafael@borgesadv.com",    "Advocacia",      "Google Ads",      "Escritório trabalhista, 3 advogados.",         "Fechado",           4800.0, d(45), "14:00", None,                                         dt(45)),
        ("Dra. Camila Rocha",   "11991110002", "camila@clinicavida.com",  "Clínica Médica", "Google Ads",      "Clínica de nutrologia e estética.",            "Fechado",           5200.0, d(38), "10:00", None,                                         dt(60)),
        ("Dr. Thiago Ferreira", "11991110003", "thiago@odontomax.com",    "Odontologia",    "Google Ads",      "Consultório odonto, foco em ortodontia.",      "Fechado",           3900.0, d(20), "09:00", None,                                         dt(35)),
        ("Dra. Ana Lima",       "11991110004", "ana.lima@email.com",      "Advocacia",      "Google Ads",      "Captação para família e herança.",             "Consulta Agendada", None,   (now + timedelta(days=3)).strftime("%Y-%m-%d"), "15:00", None, dt(8)),
        ("Dr. Carlos Mendes",   "11991110005", "carlos.m@cardio.com",     "Clínica Médica", "Google Ads",      "Cardiologista, quer pacientes particulares.",  "Contato Feito",     None,   None,  None,   None,                                         dt(9)),
        ("Dra. Juliana Pires",  "11991110006", "ju.pires@psi.com",        "Psicologia",     "Google Ads",      "Psicóloga infantil, consultório próprio.",     "Tentando Contato",  None,   None,  None,   None,                                         dt(5)),
        ("Dr. Eduardo Matos",   "11991110007", None,                      "Advocacia",      "Google Ads",      "Advocacia empresarial, quer escalar.",         "Tentando Contato",  None,   None,  None,   None,                                         dt(3)),
        ("Dra. Larissa Vaz",    "11991110008", "larissa@dermaclinic.com", "Clínica Médica", "Google Ads",      "Clínica de dermatologia.",                    "Novo Lead",         None,   None,  None,   None,                                         dt(1)),
        ("Dr. Fábio Santana",   "11991110009", None,                      "Odontologia",    "Google Ads",      "Clínica odonto com 2 sócios.",                 "Perdido",           None,   None,  None,   "Já tem agência contratada.",                 dt(25)),
        ("Dra. Mônica Teles",   "11991110010", "monica@teles.com",        "Advocacia",      "Google Ads",      "Advocacia previdenciária.",                    "Perdido",           None,   None,  None,   "Não tinha orçamento no momento.",            dt(18)),
        # Instagram (6 leads)
        ("Dra. Patrícia Souza", "11992220001", "pati@odontocare.com",     "Odontologia",    "Instagram",       "Foco em implantes e harmonização.",            "Fechado",           3500.0, d(12), "10:00", None,                                         dt(40)),
        ("Dr. Bruno Alves",     "11992220002", "bruno@psiquiatria.com",   "Clínica Médica", "Instagram",       "Psiquiatra, atende planos e particular.",      "Consulta Agendada", None,   d(2),  "11:00", None,                                         dt(15)),
        ("Dra. Renata Campos",  "11992220003", None,                      "Psicologia",     "Instagram",       "Psicóloga clínica, online e presencial.",      "Contato Feito",     None,   None,  None,   None,                                         dt(10)),
        ("Dr. Gustavo Nery",    "11992220004", "gustavo@nery.vet",        "Veterinária",    "Instagram",       "Clínica vet especializada em felinos.",        "Tentando Contato",  None,   None,  None,   None,                                         dt(6)),
        ("Dra. Isabela Moura",  "11992220005", None,                      "Odontologia",    "Instagram",       "Odontopediatra.",                              "Novo Lead",         None,   None,  None,   None,                                         dt(2)),
        ("Dr. Leandro Couto",   "11992220006", None,                      "Advocacia",      "Instagram",       "Advogado criminal, quer autoridade digital.",  "Perdido",           None,   None,  None,   "Não acredita em tráfego pago.",              dt(30)),
        # Indicação (5 leads)
        ("Dra. Fernanda Costa", "11993330001", "fernanda@vetpet.com",     "Veterinária",    "Indicação",       "Indicação da Dra. Patrícia. 2 unidades.",      "Fechado",           6000.0, d(22), "14:00", None,                                         dt(50)),
        ("Dr. Marcelo Dutra",   "11993330002", "marcelo@dutraadv.com",    "Advocacia",      "Indicação",       "Indicado por colega. Escritório tributário.",  "Fechado",           5500.0, d(10), "09:00", None,                                         dt(30)),
        ("Dra. Cristina Luz",   "11993330003", "cris@ortopedia.com",      "Clínica Médica", "Indicação",       "Ortopedista, indicado por paciente.",          "Consulta Agendada", None,   d(5),  "16:00", None,                                         dt(12)),
        ("Dr. Paulo Henrique",  "11993330004", None,                      "Psicologia",     "Indicação",       "Psicólogo organizacional.",                    "Contato Feito",     None,   None,  None,   None,                                         dt(7)),
        ("Dra. Vanessa Lopes",  "11993330005", "vanessa@odonlo.com",      "Odontologia",    "Indicação",       "Clínica de reabilitação oral.",                "Tentando Contato",  None,   None,  None,   None,                                         dt(4)),
        # Site (3 leads)
        ("Marcos Oliveira",     "11994440001", None,                      "Psicologia",     "Site",            "Psicólogo autônomo, atende particular.",       "Tentando Contato",  None,   None,  None,   None,                                         dt(4)),
        ("Dr. Roberto Nunes",   "11994440002", "roberto@advocacia.com",   "Advocacia",      "Site",            "Escritório trabalhista.",                      "Perdido",           None,   None,  None,   "Achou o investimento alto.",                 dt(20)),
        ("Dra. Aline Freitas",  "11994440003", "aline@alinevet.com",      "Veterinária",    "Site",            "Vet de pequenos animais.",                     "Novo Lead",         None,   None,  None,   None,                                         dt(2)),
        # WhatsApp direto (1 lead)
        ("Dr. Sérgio Batista",  "11995550001", "sergio@clinicabat.com",   "Clínica Médica", "WhatsApp direto", "Mandou mensagem direto. Clínica de urologia.", "Novo Lead",         None,   None,  None,   None,                                         dt(1)),
    ]

    for l in leads:
        conn.execute("""
            INSERT INTO leads (nome, whatsapp, email, segmento, origem, observacoes,
                               etapa, valor_servico, data_consulta, hora_consulta,
                               motivo_perda, criado_em)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        """, l)
    conn.commit()

    # Pega os IDs pelo nome (funciona em SQLite e PostgreSQL)
    rows = conn.execute("SELECT id, nome FROM leads ORDER BY id").fetchall()
    idx  = {row["nome"]: row["id"] for row in rows}

    interacoes = [
        (idx["Dr. Rafael Borges"],   "WhatsApp", "Primeiro contato, precisa de mais clientes.",    dt(44,9)),
        (idx["Dr. Rafael Borges"],   "Ligação",  "Apresentei o serviço, ele gostou.",              dt(42,14)),
        (idx["Dr. Rafael Borges"],   "Reunião",  "Mostrei cases de advocacia. Aprovado!",          dt(40,10)),
        (idx["Dr. Rafael Borges"],   "WhatsApp", "Enviou contrato assinado.",                      dt(45,16)),
        (idx["Dra. Camila Rocha"],   "WhatsApp", "Veio pelo Google, quer pacientes de estética.",  dt(59,10)),
        (idx["Dra. Camila Rocha"],   "Ligação",  "Detalhou o perfil dos pacientes ideais.",        dt(57,11)),
        (idx["Dra. Camila Rocha"],   "Reunião",  "Apresentei estratégia, fechou na hora.",         dt(55,14)),
        (idx["Dr. Thiago Ferreira"], "WhatsApp", "Interessado em captar para aparelhos.",          dt(34,10)),
        (idx["Dr. Thiago Ferreira"], "Ligação",  "Alinhamos objetivos e orçamento.",               dt(32,15)),
        (idx["Dr. Thiago Ferreira"], "WhatsApp", "Confirmou fechamento por e-mail.",               dt(20,9)),
        (idx["Dra. Ana Lima"],       "WhatsApp", "Perguntou sobre resultados em advocacia.",       dt(7,10)),
        (idx["Dra. Ana Lima"],       "Ligação",  "Conversa boa, agendamos apresentação.",          dt(6,14)),
        (idx["Dr. Carlos Mendes"],   "WhatsApp", "Primeiro contato, pediu para ligar depois.",     dt(9,10)),
        (idx["Dra. Juliana Pires"],  "WhatsApp", "Mandei mensagem, sem resposta ainda.",           dt(5,9)),
        (idx["Dra. Patrícia Souza"], "WhatsApp", "Enviou dúvidas sobre resultados esperados.",     dt(39,10)),
        (idx["Dra. Patrícia Souza"], "Reunião",  "Apresentei o plano de mídia, gostou muito.",     dt(35,14)),
        (idx["Dra. Patrícia Souza"], "WhatsApp", "Fechou! Início na próxima semana.",              dt(12,9)),
        (idx["Dr. Bruno Alves"],     "WhatsApp", "Perguntou sobre anúncios para psiquiatria.",     dt(14,10)),
        (idx["Dr. Bruno Alves"],     "Ligação",  "Boa conversa, agendamos consultoria.",           dt(12,11)),
        (idx["Dra. Renata Campos"],  "WhatsApp", "Respondeu! Quer entender mais o processo.",      dt(9,10)),
        (idx["Dra. Fernanda Costa"], "WhatsApp", "Indicada pela Dra. Patrícia, já veio confiante.",dt(49,10)),
        (idx["Dra. Fernanda Costa"], "Reunião",  "Apresentamos estratégia para as 2 unidades.",    dt(47,14)),
        (idx["Dra. Fernanda Costa"], "WhatsApp", "Fechou contrato para as 2 clínicas!",            dt(22,9)),
        (idx["Dr. Marcelo Dutra"],   "WhatsApp", "Indicado por colega, já sabia o que queria.",    dt(29,10)),
        (idx["Dr. Marcelo Dutra"],   "Ligação",  "Alinhamos estratégia para tributário.",          dt(27,15)),
        (idx["Dr. Marcelo Dutra"],   "WhatsApp", "Assinou contrato.",                              dt(10,9)),
        (idx["Dra. Cristina Luz"],   "WhatsApp", "Indicada por paciente que viu o resultado.",     dt(11,10)),
        (idx["Dra. Cristina Luz"],   "Ligação",  "Agendamos reunião de apresentação.",             dt(9,14)),
        (idx["Dr. Paulo Henrique"],  "WhatsApp", "Primeiro contato, quer entender o processo.",    dt(6,10)),
        (idx["Marcos Oliveira"],     "WhatsApp", "Mandei mensagem pelo número do site.",           dt(4,9)),
    ]

    for it in interacoes:
        conn.execute(
            "INSERT INTO interacoes (lead_id, tipo, anotacao, data_hora) VALUES (%s,%s,%s,%s)", it
        )

    # Atualiza atualizado_em conforme última interação
    for nome, lid in idx.items():
        row = conn.execute(
            "SELECT data_hora FROM interacoes WHERE lead_id=%s ORDER BY data_hora DESC LIMIT 1", (lid,)
        ).fetchone()
        if row:
            conn.execute("UPDATE leads SET atualizado_em=%s WHERE id=%s", (row["data_hora"], lid))

    # Carlos Mendes: garante alerta de 9 dias
    conn.execute("UPDATE leads SET atualizado_em=%s WHERE id=%s", (dt(9,10), idx["Dr. Carlos Mendes"]))

    # Lembretes de exemplo
    hoje   = now.strftime("%Y-%m-%d")
    amanha = (now + timedelta(days=1)).strftime("%Y-%m-%d")
    conn.execute("UPDATE leads SET lembrete_em=%s, lembrete_nota=%s WHERE id=%s",
                 (hoje,   "Ligar para fechar proposta",  idx["Dra. Ana Lima"]))
    conn.execute("UPDATE leads SET lembrete_em=%s, lembrete_nota=%s WHERE id=%s",
                 (amanha, "Enviar material por e-mail",  idx["Dra. Juliana Pires"]))
    conn.execute("UPDATE leads SET lembrete_em=%s, lembrete_nota=%s WHERE id=%s",
                 (amanha, "Fazer follow-up da reunião",  idx["Dr. Bruno Alves"]))

    # Custos de aquisição
    custos = {
        "Dr. Rafael Borges": 120, "Dra. Camila Rocha": 95,  "Dr. Thiago Ferreira": 110,
        "Dra. Ana Lima":      85, "Dr. Carlos Mendes":  90,  "Dra. Juliana Pires":   75,
        "Dr. Eduardo Matos":  80, "Dra. Larissa Vaz":   70,  "Dr. Fábio Santana":   100,
        "Dra. Mônica Teles":  88, "Dra. Patrícia Souza":45,  "Dr. Bruno Alves":      50,
        "Dra. Renata Campos": 40, "Dr. Gustavo Nery":   35,  "Dra. Isabela Moura":   38,
        "Dr. Leandro Couto":  42,
    }
    for nome, custo in custos.items():
        if nome in idx:
            conn.execute("UPDATE leads SET custo_aquisicao=%s WHERE id=%s", (custo, idx[nome]))

    conn.commit()


# ─── Helpers ─────────────────────────────────────────────────────────────────

def whatsapp_link(numero):
    if not numero:
        return None
    digitos = re.sub(r"\D", "", numero)
    if not digitos:
        return None
    return f"https://wa.me/55{digitos}"


def ultima_interacao(lead_id, conn):
    row = conn.execute(
        "SELECT data_hora FROM interacoes WHERE lead_id=%s ORDER BY data_hora DESC LIMIT 1",
        (lead_id,)
    ).fetchone()
    return row["data_hora"] if row else None


def dias_sem_contato(lead_id, criado_em, conn):
    ultima = ultima_interacao(lead_id, conn)
    ref = ultima if ultima else criado_em
    try:
        return (datetime.now() - datetime.strptime(str(ref)[:19], "%Y-%m-%d %H:%M:%S")).days
    except Exception:
        return 0


# ─── Rotas ───────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    return redirect(url_for("dashboard"))


@app.route("/dashboard")
def dashboard():
    conn = get_db()
    total_por_etapa = {}
    for e in ETAPAS:
        total_por_etapa[e] = conn.execute(
            "SELECT COUNT(*) FROM leads WHERE etapa=%s", (e,)
        ).fetchone()[0]

    por_origem = {}
    for r in conn.execute("SELECT origem, COUNT(*) as n FROM leads GROUP BY origem").fetchall():
        por_origem[r["origem"]] = r["n"]

    ultimos_30 = conn.execute(
        "SELECT COUNT(*) FROM leads WHERE criado_em::timestamp >= NOW() - INTERVAL '30 days'"
    ).fetchone()[0]

    atrasados = []
    for l in conn.execute("SELECT * FROM leads WHERE etapa NOT IN ('Fechado','Perdido')").fetchall():
        d = dias_sem_contato(l["id"], l["criado_em"], conn)
        if d > 7:
            atrasados.append({"nome": l["nome"], "etapa": l["etapa"], "dias": d, "id": l["id"]})

    hoje = datetime.now().strftime("%Y-%m-%d")
    lembretes = [dict(r) for r in conn.execute("""
        SELECT id, nome, etapa, lembrete_em, lembrete_nota
        FROM leads
        WHERE lembrete_em IS NOT NULL AND lembrete_em <= %s
          AND etapa NOT IN ('Fechado','Perdido')
        ORDER BY lembrete_em ASC
    """, (hoje,)).fetchall()]

    conn.close()
    return render_template("dashboard.html",
                           total_por_etapa=total_por_etapa, por_origem=por_origem,
                           atrasados=atrasados, ultimos_30=ultimos_30,
                           etapas=ETAPAS, lembretes=lembretes, hoje=hoje)


@app.route("/pipeline")
def pipeline():
    conn = get_db()
    colunas = {}
    for e in ETAPAS:
        cards = []
        for l in conn.execute(
            "SELECT * FROM leads WHERE etapa=%s ORDER BY atualizado_em DESC", (e,)
        ).fetchall():
            d = dias_sem_contato(l["id"], l["criado_em"], conn)
            cards.append({
                "id": l["id"], "nome": l["nome"], "segmento": l["segmento"],
                "origem": l["origem"], "dias_sem_contato": d, "alerta": d > 7,
                "etapa": l["etapa"], "whatsapp_link": whatsapp_link(l["whatsapp"])
            })
        colunas[e] = cards
    conn.close()
    return render_template("pipeline.html", colunas=colunas, etapas=ETAPAS)


@app.route("/leads")
def leads():
    conn = get_db()
    q        = request.args.get("q", "")
    etapa    = request.args.get("etapa", "")
    origem   = request.args.get("origem", "")
    segmento = request.args.get("segmento", "")

    sql    = "SELECT * FROM leads WHERE 1=1"
    params = []
    if q:
        sql += " AND (nome LIKE %s OR whatsapp LIKE %s)"
        params += [f"%{q}%", f"%{q}%"]
    if etapa:
        sql += " AND etapa = %s";    params.append(etapa)
    if origem:
        sql += " AND origem = %s";   params.append(origem)
    if segmento:
        sql += " AND segmento = %s"; params.append(segmento)
    sql += " ORDER BY atualizado_em DESC"

    leads_list = []
    for l in conn.execute(sql, params).fetchall():
        d = dias_sem_contato(l["id"], l["criado_em"], conn)
        leads_list.append({**dict(l), "dias_sem_contato": d, "alerta": d > 7})
    conn.close()
    return render_template("leads.html", leads=leads_list, etapas=ETAPAS,
                           origens=ORIGENS, segmentos=SEGMENTOS,
                           filtros={"q": q, "etapa": etapa, "origem": origem, "segmento": segmento})


@app.route("/lead/novo", methods=["GET", "POST"])
def novo_lead():
    if request.method == "POST":
        d = request.form
        conn = get_db()
        conn.execute("""
            INSERT INTO leads (nome, whatsapp, email, segmento, origem, observacoes,
                               custo_aquisicao, lembrete_em, lembrete_nota)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
        """, (d["nome"], d["whatsapp"], d.get("email"), d.get("segmento"),
              d.get("origem"), d.get("observacoes"),
              d.get("custo_aquisicao") or None,
              d.get("lembrete_em")     or None,
              d.get("lembrete_nota")   or None))
        conn.commit()
        conn.close()
        return redirect(url_for("pipeline"))
    return render_template("form_lead.html", lead=None, etapas=ETAPAS,
                           segmentos=SEGMENTOS, origens=ORIGENS)


@app.route("/lead/<int:lead_id>")
def ver_lead(lead_id):
    conn = get_db()
    lead = conn.execute("SELECT * FROM leads WHERE id=%s", (lead_id,)).fetchone()
    if not lead:
        conn.close()
        return "Lead não encontrado", 404
    interacoes = conn.execute(
        "SELECT * FROM interacoes WHERE lead_id=%s ORDER BY data_hora DESC", (lead_id,)
    ).fetchall()
    d = dias_sem_contato(lead_id, lead["criado_em"], conn)
    conn.close()
    return render_template("lead_detalhe.html", lead=dict(lead),
                           interacoes=[dict(i) for i in interacoes],
                           dias_sem_contato=d, tipos_interacao=TIPOS_INTERACAO,
                           etapas=ETAPAS, segmentos=SEGMENTOS, origens=ORIGENS,
                           now_str=datetime.now().strftime("%Y-%m-%dT%H:%M"),
                           hoje=datetime.now().strftime("%Y-%m-%d"),
                           whatsapp_link=whatsapp_link(lead["whatsapp"]))


@app.route("/lead/<int:lead_id>/editar", methods=["POST"])
def editar_lead(lead_id):
    d = request.form
    conn = get_db()
    conn.execute("""
        UPDATE leads SET nome=%s, whatsapp=%s, email=%s, segmento=%s, origem=%s,
        observacoes=%s, valor_servico=%s, data_consulta=%s, hora_consulta=%s,
        motivo_perda=%s, custo_aquisicao=%s, lembrete_em=%s, lembrete_nota=%s,
        atualizado_em=NOW()::text
        WHERE id=%s
    """, (d["nome"], d["whatsapp"], d.get("email"), d.get("segmento"), d.get("origem"),
          d.get("observacoes"),
          d.get("valor_servico")    or None,
          d.get("data_consulta")    or None,
          d.get("hora_consulta")    or None,
          d.get("motivo_perda")     or None,
          d.get("custo_aquisicao")  or None,
          d.get("lembrete_em")      or None,
          d.get("lembrete_nota")    or None,
          lead_id))
    conn.commit()
    conn.close()
    return redirect(url_for("ver_lead", lead_id=lead_id))


@app.route("/lead/<int:lead_id>/interacao", methods=["POST"])
def nova_interacao(lead_id):
    d = request.form
    data_hora = d.get("data_hora") or datetime.now().strftime("%Y-%m-%d %H:%M")
    conn = get_db()
    conn.execute(
        "INSERT INTO interacoes (lead_id, tipo, anotacao, data_hora) VALUES (%s,%s,%s,%s)",
        (lead_id, d["tipo"], d.get("anotacao"), data_hora)
    )
    conn.execute("UPDATE leads SET atualizado_em=%s WHERE id=%s", (data_hora, lead_id))
    conn.commit()
    conn.close()
    return redirect(url_for("ver_lead", lead_id=lead_id))


@app.route("/lead/<int:lead_id>/excluir", methods=["POST"])
def excluir_lead(lead_id):
    conn = get_db()
    conn.execute("DELETE FROM leads WHERE id=%s", (lead_id,))
    conn.commit()
    conn.close()
    return redirect(url_for("leads"))


@app.route("/lead/<int:lead_id>/lembrete/concluir", methods=["POST"])
def concluir_lembrete(lead_id):
    conn = get_db()
    conn.execute("UPDATE leads SET lembrete_em=NULL, lembrete_nota=NULL WHERE id=%s", (lead_id,))
    conn.commit()
    conn.close()
    volta = request.form.get("volta", "dashboard")
    return redirect(url_for(volta) if volta in ("dashboard", "ver_lead") else url_for("dashboard"))


# ─── API Kanban ───────────────────────────────────────────────────────────────

@app.route("/api/mover", methods=["POST"])
def api_mover():
    data      = request.get_json()
    lead_id   = data.get("lead_id")
    nova_etapa = data.get("nova_etapa")

    if nova_etapa not in ETAPAS:
        return jsonify({"ok": False, "erro": "Etapa inválida"}), 400

    conn = get_db()
    lead = conn.execute("SELECT * FROM leads WHERE id=%s", (lead_id,)).fetchone()
    if not lead:
        conn.close()
        return jsonify({"ok": False, "erro": "Lead não encontrado"}), 404

    etapa_atual = lead["etapa"]
    erro = None
    if nova_etapa == "Tentando Contato" and etapa_atual == "Novo Lead":
        if not lead["whatsapp"]:
            erro = "Preencha o WhatsApp do lead antes de avançar."
    elif nova_etapa == "Contato Feito" and etapa_atual == "Tentando Contato":
        n = conn.execute("SELECT COUNT(*) FROM interacoes WHERE lead_id=%s", (lead_id,)).fetchone()[0]
        if n == 0:
            erro = "Registre pelo menos 1 interação antes de avançar."
    elif nova_etapa == "Consulta Agendada" and etapa_atual == "Contato Feito":
        if not lead["data_consulta"] or not lead["hora_consulta"]:
            erro = "Preencha a data e hora da consulta antes de avançar."
    elif nova_etapa == "Fechado" and etapa_atual == "Consulta Agendada":
        if not lead["valor_servico"]:
            erro = "Preencha o valor do serviço antes de fechar."
    elif nova_etapa == "Perdido":
        if not lead["motivo_perda"]:
            erro = "Informe o motivo da perda antes de mover para Perdido."

    if erro:
        conn.close()
        return jsonify({"ok": False, "erro": erro})

    conn.execute(
        "UPDATE leads SET etapa=%s, atualizado_em=NOW()::text WHERE id=%s", (nova_etapa, lead_id)
    )
    conn.commit()
    conn.close()
    return jsonify({"ok": True})


@app.route("/api/lead/<int:lead_id>")
def api_lead(lead_id):
    conn = get_db()
    lead = conn.execute("SELECT * FROM leads WHERE id=%s", (lead_id,)).fetchone()
    conn.close()
    if not lead:
        return jsonify({}), 404
    return jsonify(dict(lead))


# ─── Relatórios ───────────────────────────────────────────────────────────────

@app.route("/relatorios")
def relatorios():
    conn = get_db()

    por_origem = {}
    for r in conn.execute("SELECT origem, COUNT(*) n FROM leads GROUP BY origem ORDER BY n DESC"):
        por_origem[r["origem"] or "Não informado"] = r["n"]

    por_segmento = {}
    for r in conn.execute("SELECT segmento, COUNT(*) n FROM leads GROUP BY segmento ORDER BY n DESC"):
        por_segmento[r["segmento"] or "Não informado"] = r["n"]

    funil = {}
    for e in ETAPAS:
        funil[e] = conn.execute("SELECT COUNT(*) FROM leads WHERE etapa=%s", (e,)).fetchone()[0]

    conv_origem = {}
    for origem in por_origem:
        total   = conn.execute("SELECT COUNT(*) FROM leads WHERE origem=%s", (origem,)).fetchone()[0]
        fechados = conn.execute(
            "SELECT COUNT(*) FROM leads WHERE origem=%s AND etapa='Fechado'", (origem,)
        ).fetchone()[0]
        conv_origem[origem] = {
            "total": total, "fechados": fechados,
            "taxa": round(fechados / total * 100, 1) if total else 0
        }

    receita_origem = {}
    for r in conn.execute("""
        SELECT origem, SUM(valor_servico) total
        FROM leads WHERE etapa='Fechado' AND valor_servico IS NOT NULL GROUP BY origem
    """):
        receita_origem[r["origem"] or "Não informado"] = r["total"] or 0

    receita_total  = sum(receita_origem.values())
    ticket_medio   = conn.execute(
        "SELECT AVG(valor_servico) FROM leads WHERE etapa='Fechado' AND valor_servico IS NOT NULL"
    ).fetchone()[0] or 0

    evolucao = {}
    for r in conn.execute("""
        SELECT TO_CHAR(criado_em::timestamp, 'YYYY-MM') mes, COUNT(*) n
        FROM leads WHERE criado_em::timestamp >= NOW() - INTERVAL '12 months'
        GROUP BY mes ORDER BY mes
    """).fetchall():
        evolucao[r["mes"]] = r["n"]

    tempos = []
    for r in conn.execute("SELECT criado_em, atualizado_em FROM leads WHERE etapa='Fechado'").fetchall():
        try:
            c = datetime.strptime(str(r["criado_em"])[:19],    "%Y-%m-%d %H:%M:%S")
            f = datetime.strptime(str(r["atualizado_em"])[:19], "%Y-%m-%d %H:%M:%S")
            tempos.append((f - c).days)
        except Exception:
            pass
    tempo_medio_fechamento = round(sum(tempos) / len(tempos), 1) if tempos else 0

    total_leads   = conn.execute("SELECT COUNT(*) FROM leads").fetchone()[0]
    total_fechados = funil.get("Fechado", 0)
    taxa_conv_geral = round(total_fechados / total_leads * 100, 1) if total_leads else 0

    custo_origem = {}
    for r in conn.execute("""
        SELECT origem, SUM(custo_aquisicao) total_custo, COUNT(*) total_leads
        FROM leads WHERE custo_aquisicao IS NOT NULL GROUP BY origem
    """):
        custo_origem[r["origem"] or "Não informado"] = {
            "total": r["total_custo"] or 0,
            "leads": r["total_leads"],
            "cpl": round((r["total_custo"] or 0) / r["total_leads"], 2) if r["total_leads"] else 0,
        }

    roi_origem = {}
    for orig in set(list(custo_origem) + list(receita_origem)):
        receita = receita_origem.get(orig, 0)
        custo   = custo_origem.get(orig, {}).get("total", 0)
        if custo > 0:
            roi_origem[orig] = round((receita - custo) / custo * 100, 1)

    investimento_total = sum(v["total"] for v in custo_origem.values())
    conn.close()

    return render_template("relatorios.html",
        por_origem=por_origem, por_segmento=por_segmento, funil=funil,
        conv_origem=conv_origem, receita_origem=receita_origem,
        receita_total=receita_total, ticket_medio=ticket_medio,
        evolucao=evolucao, etapas=ETAPAS, total_leads=total_leads,
        total_fechados=total_fechados, taxa_conv_geral=taxa_conv_geral,
        tempo_medio_fechamento=tempo_medio_fechamento,
        custo_origem=custo_origem, roi_origem=roi_origem,
        investimento_total=investimento_total,
    )


@app.route("/relatorios/exportar-pdf")
def exportar_pdf():
    conn = get_db()
    total_leads    = conn.execute("SELECT COUNT(*) FROM leads").fetchone()[0]
    total_fechados = conn.execute("SELECT COUNT(*) FROM leads WHERE etapa='Fechado'").fetchone()[0]
    taxa_conv      = round(total_fechados / total_leads * 100, 1) if total_leads else 0
    receita_total  = conn.execute(
        "SELECT COALESCE(SUM(valor_servico),0) FROM leads WHERE etapa='Fechado'"
    ).fetchone()[0] or 0
    ticket_medio   = conn.execute(
        "SELECT COALESCE(AVG(valor_servico),0) FROM leads WHERE etapa='Fechado' AND valor_servico IS NOT NULL"
    ).fetchone()[0] or 0
    invest_total   = conn.execute(
        "SELECT COALESCE(SUM(custo_aquisicao),0) FROM leads WHERE custo_aquisicao IS NOT NULL"
    ).fetchone()[0] or 0

    funil = {}
    for e in ETAPAS:
        funil[e] = conn.execute("SELECT COUNT(*) FROM leads WHERE etapa=%s", (e,)).fetchone()[0]

    canais = conn.execute("""
        SELECT l.origem,
               COUNT(*) total,
               SUM(CASE WHEN l.etapa='Fechado' THEN 1 ELSE 0 END) fechados,
               COALESCE(SUM(CASE WHEN l.etapa='Fechado' THEN l.valor_servico ELSE 0 END),0) receita,
               COALESCE(SUM(l.custo_aquisicao),0) custo
        FROM leads l GROUP BY l.origem ORDER BY total DESC
    """).fetchall()
    conn.close()

    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()
    pdf.set_margins(15, 15, 15)

    pdf.set_fill_color(17, 23, 34)
    pdf.rect(0, 0, 210, 30, 'F')
    pdf.set_text_color(253, 148, 81)
    pdf.set_font("Helvetica", "B", 18)
    pdf.set_y(8)
    pdf.cell(0, 10, "Sistema 4X CRM - Relatorio de Desempenho", align="C")
    pdf.set_text_color(180, 175, 155)
    pdf.set_font("Helvetica", "", 9)
    pdf.set_y(20)
    pdf.cell(0, 6, f"Gerado em {datetime.now().strftime('%d/%m/%Y as %H:%M')}", align="C")
    pdf.ln(20)

    pdf.set_text_color(40, 40, 40)
    pdf.set_font("Helvetica", "B", 12)
    pdf.cell(0, 8, "Resumo Geral", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.set_draw_color(253, 148, 81)
    pdf.set_line_width(0.5)
    pdf.line(15, pdf.get_y(), 195, pdf.get_y())
    pdf.ln(3)

    kpis = [
        ("Total de Leads",    str(total_leads)),
        ("Negocios Fechados", str(total_fechados)),
        ("Taxa de Conversao", f"{taxa_conv}%"),
        ("Receita Total",     f"R$ {receita_total:,.2f}"),
        ("Ticket Medio",      f"R$ {ticket_medio:,.2f}"),
        ("Investimento",      f"R$ {invest_total:,.2f}"),
        ("ROI Geral",         f"{round((receita_total-invest_total)/invest_total*100,1) if invest_total else 0}%"),
    ]
    col_w = 87
    for i, (label, valor) in enumerate(kpis):
        x = 15 if i % 2 == 0 else 15 + col_w + 6
        if i % 2 == 0 and i > 0:
            pdf.ln(1)
        pdf.set_xy(x, pdf.get_y())
        pdf.set_fill_color(245, 245, 245)
        pdf.set_font("Helvetica", "", 9)
        pdf.cell(col_w, 5, label, fill=True)
        pdf.set_xy(x, pdf.get_y() + 5)
        pdf.set_font("Helvetica", "B", 13)
        pdf.set_text_color(253, 148, 81)
        pdf.cell(col_w, 8, valor)
        pdf.set_text_color(40, 40, 40)
        if i % 2 == 1:
            pdf.ln(10)
    pdf.ln(8)

    pdf.set_font("Helvetica", "B", 12)
    pdf.cell(0, 8, "Funil de Conversao", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.line(15, pdf.get_y(), 195, pdf.get_y())
    pdf.ln(3)
    cores = [(74,144,217),(232,168,56),(167,139,250),(244,114,182),(52,211,153),(248,113,113)]
    max_f = max(funil.values()) or 1
    pdf.set_font("Helvetica", "", 9)
    for i, (etapa, n) in enumerate(funil.items()):
        pct = int(n / max_f * 100)
        pdf.cell(50, 6, etapa, fill=False)
        pdf.set_fill_color(*cores[i % len(cores)])
        pdf.cell(max(pct, 2), 6, "", fill=True)
        pdf.set_fill_color(230, 230, 230)
        pdf.cell(100 - pct, 6, "", fill=True)
        pdf.cell(10, 6, f" {n}", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        pdf.ln(1)
    pdf.ln(4)

    pdf.set_font("Helvetica", "B", 12)
    pdf.cell(0, 8, "Desempenho por Canal de Origem", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.line(15, pdf.get_y(), 195, pdf.get_y())
    pdf.ln(3)
    headers = ["Origem","Leads","Fechados","Conversao","Receita (R$)","Custo (R$)","ROI"]
    widths  = [40,18,22,24,35,30,20]
    pdf.set_fill_color(40,40,40)
    pdf.set_text_color(255,255,255)
    pdf.set_font("Helvetica","B",9)
    for h, w in zip(headers, widths):
        pdf.cell(w, 7, h, border=1, fill=True, align="C")
    pdf.ln()
    pdf.set_text_color(40,40,40)
    pdf.set_font("Helvetica","",9)
    fill = False
    for row in canais:
        total   = row["total"]
        fechados = row["fechados"]
        receita = row["receita"] or 0
        custo   = row["custo"]   or 0
        roi_val = round((receita-custo)/custo*100,1) if custo > 0 else "-"
        pdf.set_fill_color(248,248,248) if fill else pdf.set_fill_color(255,255,255)
        for v, w, a in zip(
            [row["origem"] or "N/A", str(total), str(fechados),
             f"{round(fechados/total*100,1)}%" if total else "0%",
             f"{receita:,.2f}", f"{custo:,.2f}",
             f"{roi_val}%" if roi_val != "-" else "-"],
            widths, ["L","C","C","C","R","R","C"]
        ):
            pdf.cell(w, 6, v, border=1, fill=True, align=a)
        pdf.ln()
        fill = not fill
    pdf.ln(4)
    pdf.set_font("Helvetica","I",8)
    pdf.set_text_color(150,150,150)
    pdf.cell(0, 6, "Gerado pelo Sistema 4X CRM - sistema de gestao de leads", align="C")

    pdf_bytes = pdf.output()
    resp = make_response(bytes(pdf_bytes))
    resp.headers["Content-Type"] = "application/pdf"
    resp.headers["Content-Disposition"] = f"attachment; filename=relatorio_4xcrm_{datetime.now().strftime('%Y%m%d_%H%M')}.pdf"
    return resp


init_db()

if __name__ == "__main__":
    print("\nSistema 4X CRM iniciado!")
    print("Acesse: http://localhost:5000\n")
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=not USE_PG)
