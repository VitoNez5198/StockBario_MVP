document.addEventListener("DOMContentLoaded", () => {
  const { apiFetch, showToast } = window.StockBarrio;
  const esAdmin = Boolean(window.FIADOS_CONFIG && window.FIADOS_CONFIG.esAdmin);

  const elDeudaTotal = document.getElementById("kpi-deuda-total");
  const elClientesDeuda = document.getElementById("kpi-clientes-deuda");
  const elCupoTotal = document.getElementById("kpi-cupo-total");

  const inputSearch = document.getElementById("fiado-search");
  const checkSoloDeuda = document.getElementById("fiado-solo-deuda");
  const checkInactivos = document.getElementById("fiado-ver-inactivos");
  const tbody = document.getElementById("fiados-tbody");

  const modalCliente = document.getElementById("modal-cliente");
  const formCliente = document.getElementById("form-cliente");
  const cliTitulo = document.getElementById("modal-cliente-titulo");
  const fCliId = document.getElementById("cli-id");
  const fCliNombre = document.getElementById("cli-nombre");
  const fCliApodo = document.getElementById("cli-apodo");
  const fCliTelefono = document.getElementById("cli-telefono");
  const fCliDireccion = document.getElementById("cli-direccion");
  const fCliLimite = document.getElementById("cli-limite");

  const modalAbono = document.getElementById("modal-abono");
  const formAbono = document.getElementById("form-abono");
  const abonoTitulo = document.getElementById("modal-abono-titulo");
  const abonoSubtitulo = document.getElementById("modal-abono-subtitulo");
  const fAbonoCliId = document.getElementById("abono-cli-id");
  const fAbonoMonto = document.getElementById("abono-monto");
  const fAbonoMetodo = document.getElementById("abono-metodo");
  const fAbonoObs = document.getElementById("abono-obs");
  const btnPagarTodo = document.getElementById("btn-pagar-todo");

  const modalHist = document.getElementById("modal-historial");
  const histTitulo = document.getElementById("modal-hist-titulo");
  const histSubtitulo = document.getElementById("modal-hist-subtitulo");
  const histTbody = document.getElementById("modal-hist-tbody");

  let clientesCache = [];
  let clienteAbonoActual = null;
  let searchTimer = null;

  function escapeHtml(text) {
    return String(text ?? "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#39;");
  }

  function formatMoney(valor) {
    return "$" + Math.round(Number(valor || 0)).toLocaleString("es-CL");
  }

  function formatFechaHora(isoTs) {
    if (!isoTs) return "-";
    try {
      return new Intl.DateTimeFormat("es-CL", {
        timeZone: "America/Santiago",
        day: "2-digit",
        month: "2-digit",
        hour: "2-digit",
        minute: "2-digit",
        hour12: false,
      }).format(new Date(isoTs));
    } catch (_err) {
      return escapeHtml(isoTs);
    }
  }

  function badgeTipoMov(tipo) {
    if (tipo === "ABONO") return '<span class="badge badge-ok">ABONO</span>';
    if (tipo === "FIADO") return '<span class="badge badge-warn">FIADO</span>';
    return '<span class="badge badge-neutral">ANULACION</span>';
  }

  async function cargarResumen() {
    const res = await apiFetch("/api/v1/fiados/resumen");
    elDeudaTotal.textContent = formatMoney(res.deuda_total);
    elClientesDeuda.textContent = `${res.clientes_con_deuda} / ${res.total_clientes_activos}`;
    elCupoTotal.textContent = formatMoney(res.cupo_total);
  }

  async function cargarClientes() {
    const params = new URLSearchParams();
    const q = inputSearch.value.trim();
    if (q) params.set("q", q);
    if (checkSoloDeuda.checked) params.set("solo_con_deuda", "true");
    if (checkInactivos.checked) params.set("incluir_inactivos", "true");

    const url = `/api/v1/fiados/clientes${params.toString() ? "?" + params.toString() : ""}`;
    clientesCache = await apiFetch(url);
    renderTabla();
  }

  function renderTabla() {
    if (!clientesCache.length) {
      tbody.innerHTML = `
        <tr>
          <td colspan="4" style="text-align:center; color:var(--text-muted); padding:24px;">
            No se encontraron clientes con los filtros actuales.
          </td>
        </tr>`;
      return;
    }

    tbody.innerHTML = clientesCache
      .map((c) => {
        const meta = [];
        if (c.rut_o_apodo) meta.push(escapeHtml(c.rut_o_apodo));
        if (c.telefono) meta.push(`<span class="tabular">${escapeHtml(c.telefono)}</span>`);
        if (c.direccion) meta.push(escapeHtml(c.direccion));
        if (!c.activo) meta.push("Inactivo");

        const pct = Math.min(100, Number(c.porcentaje_uso || 0));
        const barCls = pct >= 90 ? "danger" : pct >= 65 ? "warn" : "";

        const btnAbonar =
          c.activo && c.deuda_actual > 0
            ? `<button type="button" class="btn btn-primary" data-action="abonar" data-id="${c.id}" style="padding:5px 11px; font-size:12.5px;">Abonar</button>`
            : `<button type="button" class="btn btn-secondary" disabled style="padding:5px 11px; font-size:12.5px; opacity:0.5; cursor:not-allowed;">Al dia</button>`;

        const btnEditar = esAdmin
          ? `<button type="button" class="btn-icon" data-action="editar" data-id="${c.id}" title="Editar cliente"><i data-lucide="pencil"></i></button>`
          : "";
        const btnEstado = esAdmin
          ? `<button type="button" class="btn-icon" data-action="estado" data-id="${c.id}" title="${
              c.activo ? "Desactivar cliente" : "Reactivar cliente"
            }"><i data-lucide="${c.activo ? "user-x" : "rotate-ccw"}"></i></button>`
          : "";

        return `
          <tr class="${c.activo ? "" : "fiado-row-inactive"}">
            <td>
              <div class="fiado-name">${escapeHtml(c.nombre)}</div>
              <div class="fiado-meta">${meta.join(" · ") || "Sin datos adicionales"}</div>
            </td>
            <td>
              <div class="tabular">
                <strong>${formatMoney(c.deuda_actual)}</strong>
                <span style="color:var(--text-muted);">/ ${formatMoney(c.limite_credito)}</span>
              </div>
              <div class="fiado-bar" title="${pct}% del limite usado">
                <div class="fiado-bar-fill ${barCls}" style="width:${pct}%"></div>
              </div>
            </td>
            <td>
              <span class="badge ${c.cupo_disponible > 0 ? "badge-ok" : "badge-danger"} tabular">
                ${formatMoney(c.cupo_disponible)}
              </span>
            </td>
            <td>
              <div class="table-actions">
                ${btnAbonar}
                <button type="button" class="btn-icon" data-action="historial" data-id="${c.id}" title="Ver historial">
                  <i data-lucide="file-text"></i>
                </button>
                ${btnEditar}
                ${btnEstado}
              </div>
            </td>
          </tr>`;
      })
      .join("");

    if (window.lucide) window.lucide.createIcons();
  }

  async function recargarTodo() {
    await Promise.all([cargarResumen(), cargarClientes()]);
  }

  function abrirModalNuevoCliente() {
    fCliId.value = "";
    formCliente.reset();
    fCliLimite.value = "20000";
    cliTitulo.textContent = "Nuevo cliente";
    modalCliente.classList.add("open");
    fCliNombre.focus();
  }

  function abrirModalEditarCliente(c) {
    fCliId.value = c.id;
    fCliNombre.value = c.nombre;
    fCliApodo.value = c.rut_o_apodo || "";
    fCliTelefono.value = c.telefono || "";
    fCliDireccion.value = c.direccion || "";
    fCliLimite.value = c.limite_credito;
    cliTitulo.textContent = `Editar: ${c.nombre}`;
    modalCliente.classList.add("open");
    fCliNombre.focus();
  }

  function abrirModalAbono(c) {
    clienteAbonoActual = c;
    fAbonoCliId.value = c.id;
    formAbono.reset();
    fAbonoMetodo.value = "EFECTIVO";
    fAbonoMonto.max = String(c.deuda_actual);
    fAbonoMonto.value = String(c.deuda_actual);
    abonoTitulo.textContent = `Abono: ${c.nombre}`;
    abonoSubtitulo.textContent = `Deuda pendiente: ${formatMoney(c.deuda_actual)} · Cupo limite: ${formatMoney(c.limite_credito)}`;
    modalAbono.classList.add("open");
    fAbonoMonto.focus();
    fAbonoMonto.select();
  }

  async function abrirModalHistorial(c) {
    histTitulo.textContent = `Cuenta de ${c.nombre}`;
    histSubtitulo.textContent = `Deuda actual: ${formatMoney(c.deuda_actual)} · Disponible: ${formatMoney(c.cupo_disponible)}`;
    histTbody.innerHTML = `<tr><td colspan="5" style="text-align:center; color:var(--text-muted); padding:16px;">Cargando...</td></tr>`;
    modalHist.classList.add("open");

    try {
      const movs = await apiFetch(`/api/v1/fiados/clientes/${c.id}/movimientos?limit=50`);
      if (!movs.length) {
        histTbody.innerHTML = `<tr><td colspan="5" style="text-align:center; color:var(--text-muted); padding:16px;">Sin movimientos en esta cuenta.</td></tr>`;
        return;
      }
      histTbody.innerHTML = movs
        .map((m) => {
          const signo = m.tipo === "ABONO" ? "-" : "+";
          return `
            <tr>
              <td class="tabular">${formatFechaHora(m.fecha)}</td>
              <td>${badgeTipoMov(m.tipo)}</td>
              <td class="tabular"><strong>${signo}${formatMoney(m.monto)}</strong></td>
              <td>
                <div>${escapeHtml(m.detalle)}</div>
                <div class="fiado-meta tabular">${escapeHtml(m.referencia)}</div>
              </td>
              <td>${escapeHtml(m.usuario_nombre)}</td>
            </tr>`;
        })
        .join("");
    } catch (err) {
      histTbody.innerHTML = `<tr><td colspan="5" style="color:var(--danger); padding:16px;">${escapeHtml(err.message)}</td></tr>`;
    }
  }

  const btnNuevo = document.getElementById("btn-nuevo-cliente");
  if (btnNuevo) btnNuevo.addEventListener("click", abrirModalNuevoCliente);

  document.getElementById("modal-cliente-cerrar").addEventListener("click", () => modalCliente.classList.remove("open"));
  document.getElementById("modal-cliente-cancelar").addEventListener("click", () => modalCliente.classList.remove("open"));
  document.getElementById("modal-abono-cerrar").addEventListener("click", () => modalAbono.classList.remove("open"));
  document.getElementById("modal-abono-cancelar").addEventListener("click", () => modalAbono.classList.remove("open"));
  document.getElementById("modal-hist-cerrar").addEventListener("click", () => modalHist.classList.remove("open"));
  document.getElementById("modal-hist-aceptar").addEventListener("click", () => modalHist.classList.remove("open"));

  [modalCliente, modalAbono, modalHist].forEach((m) => {
    m.addEventListener("click", (e) => {
      if (e.target === m) m.classList.remove("open");
    });
  });

  btnPagarTodo.addEventListener("click", () => {
    if (clienteAbonoActual) {
      fAbonoMonto.value = String(clienteAbonoActual.deuda_actual);
      fAbonoMonto.focus();
    }
  });

  inputSearch.addEventListener("input", () => {
    clearTimeout(searchTimer);
    searchTimer = setTimeout(() => {
      cargarClientes().catch((err) => showToast(err.message, "error"));
    }, 220);
  });

  [checkSoloDeuda, checkInactivos].forEach((el) => {
    el.addEventListener("change", () => {
      cargarClientes().catch((err) => showToast(err.message, "error"));
    });
  });

  formCliente.addEventListener("submit", async (e) => {
    e.preventDefault();
    const id = fCliId.value;
    const payload = {
      nombre: fCliNombre.value.trim(),
      rut_o_apodo: fCliApodo.value.trim() || null,
      telefono: fCliTelefono.value.trim() || null,
      direccion: fCliDireccion.value.trim() || null,
      limite_credito: Number(fCliLimite.value || 0),
    };

    try {
      if (!id) {
        await apiFetch("/api/v1/fiados/clientes", {
          method: "POST",
          body: JSON.stringify(payload),
        });
        showToast("Cliente registrado");
      } else {
        await apiFetch(`/api/v1/fiados/clientes/${id}`, {
          method: "PUT",
          body: JSON.stringify(payload),
        });
        showToast("Cliente actualizado");
      }
      modalCliente.classList.remove("open");
      await recargarTodo();
    } catch (err) {
      showToast(err.message, "error");
    }
  });

  formAbono.addEventListener("submit", async (e) => {
    e.preventDefault();
    const cliId = fAbonoCliId.value;
    try {
      const res = await apiFetch(`/api/v1/fiados/clientes/${cliId}/abonos`, {
        method: "POST",
        body: JSON.stringify({
          monto: Number(fAbonoMonto.value),
          metodo_pago: fAbonoMetodo.value,
          observacion: fAbonoObs.value.trim() || null,
        }),
      });
      modalAbono.classList.remove("open");
      showToast(`Abono registrado. Deuda restante: ${formatMoney(res.deuda_restante)}`);
      await recargarTodo();
    } catch (err) {
      showToast(err.message, "error");
    }
  });

  tbody.addEventListener("click", async (e) => {
    const btn = e.target.closest("[data-action]");
    if (!btn) return;
    const id = Number(btn.dataset.id);
    const cliente = clientesCache.find((c) => c.id === id);
    if (!cliente) return;

    const action = btn.dataset.action;
    if (action === "abonar") {
      abrirModalAbono(cliente);
    } else if (action === "historial") {
      abrirModalHistorial(cliente);
    } else if (action === "editar") {
      abrirModalEditarCliente(cliente);
    } else if (action === "estado") {
      try {
        await apiFetch(`/api/v1/fiados/clientes/${id}/estado`, {
          method: "PATCH",
          body: JSON.stringify({ activo: !cliente.activo }),
        });
        showToast(cliente.activo ? "Cliente desactivado" : "Cliente reactivado");
        await recargarTodo();
      } catch (err) {
        showToast(err.message, "error");
      }
    }
  });

  recargarTodo().catch((err) => showToast(err.message, "error"));
});
