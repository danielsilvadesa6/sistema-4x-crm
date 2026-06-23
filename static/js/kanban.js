let draggedId = null;
let draggedEtapa = null;
let pendingLeadId = null;
let pendingNovaEtapa = null;

// ── Drag events ──────────────────────────────────────────────────────────────

function onDragStart(e) {
  draggedId    = e.currentTarget.dataset.id;
  draggedEtapa = e.currentTarget.dataset.etapa;
  e.currentTarget.classList.add('dragging');
  e.dataTransfer.effectAllowed = 'move';
}

document.addEventListener('dragend', function() {
  document.querySelectorAll('.kanban-card.dragging').forEach(el => el.classList.remove('dragging'));
  document.querySelectorAll('.col-cards.drag-over').forEach(el => el.classList.remove('drag-over'));
});

document.querySelectorAll('.col-cards').forEach(col => {
  col.addEventListener('dragover', e => { e.preventDefault(); col.classList.add('drag-over'); });
  col.addEventListener('dragleave', () => col.classList.remove('drag-over'));
});

function onDrop(e, novaEtapa) {
  e.preventDefault();
  document.querySelectorAll('.col-cards.drag-over').forEach(el => el.classList.remove('drag-over'));

  if (!draggedId || novaEtapa === draggedEtapa) return;

  tentarMover(draggedId, novaEtapa);
}

// ── Lógica de mover ──────────────────────────────────────────────────────────

function tentarMover(leadId, novaEtapa) {
  fetch('/api/mover', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ lead_id: parseInt(leadId), nova_etapa: novaEtapa })
  })
  .then(r => r.json())
  .then(data => {
    if (data.ok) {
      location.reload();
    } else {
      // Verifica se é um erro que pode ser resolvido preenchendo um campo
      const campo = campoNecessario(draggedEtapa, novaEtapa);
      if (campo) {
        abrirModalCampo(leadId, novaEtapa, data.erro, campo);
      } else {
        mostrarAviso(data.erro);
      }
    }
  })
  .catch(() => mostrarAviso('Erro de conexão. Tente novamente.'));
}

// Retorna qual campo precisa ser preenchido para cada transição
function campoNecessario(de, para) {
  const mapa = {
    'Novo Lead→Tentando Contato':       { tipo: 'text',     nome: 'whatsapp',      label: 'WhatsApp' },
    'Contato Feito→Consulta Agendada':  { tipo: 'date+time', nome: 'data_hora_consulta', label: 'Data e Hora da Consulta' },
    'Consulta Agendada→Fechado':        { tipo: 'number',   nome: 'valor_servico', label: 'Valor do Serviço (R$)' },
    'qualquer→Perdido':                 { tipo: 'text',     nome: 'motivo_perda',  label: 'Motivo da Perda' },
  };
  const chave = `${de}→${para}`;
  if (mapa[chave]) return mapa[chave];
  if (para === 'Perdido') return mapa['qualquer→Perdido'];
  return null;
}

// ── Modal de campo obrigatório ───────────────────────────────────────────────

function abrirModalCampo(leadId, novaEtapa, mensagem, campo) {
  pendingLeadId   = leadId;
  pendingNovaEtapa = novaEtapa;

  document.getElementById('modal-campo-msg').textContent = mensagem;

  const formDiv = document.getElementById('modal-campo-form');
  formDiv.innerHTML = '';

  if (campo.tipo === 'date+time') {
    formDiv.innerHTML = `
      <div style="display:flex;gap:10px;margin-bottom:8px">
        <div style="flex:1">
          <label style="font-size:11px;color:var(--text2);text-transform:uppercase;letter-spacing:.4px;display:block;margin-bottom:4px">Data *</label>
          <input id="campo-data" type="date" class="input" style="width:100%">
        </div>
        <div style="flex:1">
          <label style="font-size:11px;color:var(--text2);text-transform:uppercase;letter-spacing:.4px;display:block;margin-bottom:4px">Hora *</label>
          <input id="campo-hora" type="time" class="input" style="width:100%">
        </div>
      </div>`;
  } else {
    formDiv.innerHTML = `
      <div style="margin-bottom:8px">
        <label style="font-size:11px;color:var(--text2);text-transform:uppercase;letter-spacing:.4px;display:block;margin-bottom:4px">${campo.label} *</label>
        <input id="campo-valor" type="${campo.tipo}" class="input" style="width:100%" step="0.01">
      </div>`;
  }

  document.getElementById('modal-campo-ok').onclick = () => salvarCampoEMover(campo);
  document.getElementById('modal-campo').style.display = 'flex';
}

function salvarCampoEMover(campo) {
  const leadId   = pendingLeadId;
  const novaEtapa = pendingNovaEtapa;

  // Monta FormData para enviar ao backend via fetch
  const fd = new FormData();

  if (campo.tipo === 'date+time') {
    const data = document.getElementById('campo-data').value;
    const hora = document.getElementById('campo-hora').value;
    if (!data || !hora) { mostrarAvisoModal('Preencha data e hora.'); return; }
    fd.append('data_consulta', data);
    fd.append('hora_consulta', hora);
  } else {
    const val = document.getElementById('campo-valor').value.trim();
    if (!val) { mostrarAvisoModal('Campo obrigatório.'); return; }
    fd.append(campo.nome, val);
  }

  // Busca dados atuais do lead para não sobrescrever os outros campos
  fetch(`/api/lead/${leadId}`)
    .then(r => r.json())
    .then(lead => {
      // Mescla campos existentes + campo novo
      const campos = ['nome','whatsapp','email','segmento','origem','observacoes',
                      'valor_servico','data_consulta','hora_consulta','motivo_perda'];
      campos.forEach(c => {
        if (!fd.has(c) && lead[c] != null) fd.append(c, lead[c]);
      });

      return fetch(`/lead/${leadId}/editar`, { method: 'POST', body: fd });
    })
    .then(() => {
      document.getElementById('modal-campo').style.display = 'none';
      return fetch('/api/mover', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ lead_id: parseInt(leadId), nova_etapa: novaEtapa })
      });
    })
    .then(r => r.json())
    .then(data => {
      if (data.ok) {
        location.reload();
      } else {
        mostrarAviso(data.erro);
      }
    })
    .catch(() => mostrarAviso('Erro ao salvar. Tente novamente.'));
}

function mostrarAvisoModal(msg) {
  alert(msg);
}

function cancelarMover() {
  document.getElementById('modal-campo').style.display = 'none';
  pendingLeadId = null;
  pendingNovaEtapa = null;
}

// Fecha ao clicar fora
document.getElementById('modal-campo').addEventListener('click', function(e) {
  if (e.target === this) cancelarMover();
});
