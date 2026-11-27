document.addEventListener("DOMContentLoaded", () => {
  const { apiFetch, showToast } = window.StockBarrio;
  const cfg = window.COMPRAS_CONFIG || {};
  const esAdmin = Boolean(cfg.esAdmin);
  const almacenNombre = cfg.almacenNombre || "StockBarrio";

  const elKpiReponer = document.getElementById("kpi-reponer");
  const elKpiGrupos = document.getElementById("kpi-grupos");
  const elKpiCosto = document.getElementById("kpi-costo");

  const tabBtnSugeridas = document.getElementById("tab-btn-sugeridas");
  const tabBtnProveedores = document.getElementById("tab-btn-proveedores");
  const controlsSugeridas = document.getElementById("controls-sugeridas");
  const controlsProveedores = document.getElementById("controls-proveedores");
  const panelSugeridas = document.getElementById("panel-sugeridas");
  const panelProveedores = document.getElementById("panel-proveedores");

  const inputSearch = document.getElementById("compras-search");
  const btnToggleTodos = document.getElementById("btn-toggle-todos");
  const checkIncluirTodos = document.getElementById("compras-incluir-todos");
  const checkProvInactivos = document.getElementById("prov-ver-inactivos");
  const gruposContainer = document.getElementById("grupos-container");
  const tbodyProveedores = document.getElementById("proveedores-tbody");

  const modalProv = document.getElementById("modal-proveedor");
  const formProv = document.getElementById("form-proveedor");
  const provTitulo = document.getElementById("modal-prov-titulo");
  const fProvId = document.getElementById("prov-id");
  const fProvNombre = document.getElementById("prov-nombre");
  const fProvWhatsapp = document.getElementById("prov-whatsapp");
  const fProvContacto = document.getElementById("prov-contacto");

  let gruposData = [];
  let proveedoresCache = [];

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

  function formatCant(valor) {
    const num = Number(valor || 0);
    return Number.isInteger(num) ? String(num) : String(Math.round(num * 10) / 10);
  }

  function construirMensajeGrupo(grupo, seleccionados) {
    const encabezado =
      grupo.proveedor_id !== null
        ? `Hola ${grupo.proveedor_nombre}, pedido para ${almacenNombre}:`
        : `Lista de compra presencial - ${almacenNombre}:`;
    if (!seleccionados.length) {
      return `${encabezado}\n(Sin productos seleccionados)`;
    }
    const lineas = seleccionados.map(
      (i) => `- ${formatCant(i.cantidad_editada)} ${i.unidad} x ${i.nombre}`
    );
    return `${encabezado}\n${lineas.join("\n")}`;
  }

  function construirWhatsappUrl(telefono, mensaje) {
    const digitos = String(telefono || "").replace(/\D/g, "");
    const texto = encodeURIComponent(mensaje);
    return digitos ? `https://wa.me/${digitos}?text=${texto}` : `https://wa.me/?text=${texto}`;
  }

  async function copiarTexto(texto) {
    if (navigator.clipboard && navigator.clipboard.writeText) {
      await navigator.clipboard.writeText(texto);
      return;
    }
    const area = document.createElement("textarea");
    area.value = texto;
    area.style.position = "fixed";
    area.style.opacity = "0";
    document.body.appendChild(area);
    area.select();
    document.execCommand("copy");
    area.remove();
  }

  function obtenerGruposVisibles() {
    const q = (inputSearch ? inputSearch.value : "").trim().toLowerCase();
    const resultado = [];

    gruposData.forEach((g, gIdx) => {
      const provMatch = q && g.proveedor_nombre.toLowerCase().includes(q);
      const itemsVisibles = [];

      g.items.forEach((it, iIdx) => {
        const itemMatch =
          !q ||
          provMatch ||
          it.nombre.toLowerCase().includes(q) ||
          (it.codigo_barras && it.codigo_barras.toLowerCase().includes(q));
        if (itemMatch) {
          itemsVisibles.push({ item: it, iIdx });
        }
      });

      if (!q || provMatch || itemsVisibles.length > 0) {
        resultado.push({
          grupo: g,
          gIdx,
          itemsVisibles,
          abierto: q ? true : Boolean(g.abierto),
        });
      }
    });

    return resultado;
  }

  function actualizarBotonExpandir(visibles) {
    if (!btnToggleTodos) return;
    const todosAbiertos = visibles.length > 0 && visibles.every((v) => v.abierto);
    btnToggleTodos.textContent = todosAbiertos ? "Contraer todo" : "Expandir todo";
  }

  function actualizarResumenGlobal() {
    let totalItems = 0;
    let costoTotal = 0;
    gruposData.forEach((g) => {
      g.items.forEach((it) => {
        if (it.incluido && it.cantidad_editada > 0) {
          totalItems += 1;
          costoTotal += Math.round(it.cantidad_editada * it.precio_costo);
        }
      });
    });
    elKpiReponer.textContent = String(totalItems);
    elKpiGrupos.textContent = String(gruposData.length);
    elKpiCosto.textContent = formatMoney(costoTotal);
  }

  function actualizarTarjetaGrupo(gIdx) {
    const grupo = gruposData[gIdx];
    const card = gruposContainer.querySelector(`[data-group-idx="${gIdx}"]`);
    if (!grupo || !card) return;

    const seleccionados = grupo.items.filter((i) => i.incluido && i.cantidad_editada > 0);
    const costoGrupo = seleccionados.reduce(
      (acc, i) => acc + Math.round(i.cantidad_editada * i.precio_costo),
      0
    );
    const mensaje = construirMensajeGrupo(grupo, seleccionados);
    const url = construirWhatsappUrl(grupo.telefono_whatsapp, mensaje);

    card.querySelector("[data-group-subtotal]").textContent = `${seleccionados.length} de ${grupo.items.length} producto(s) · Estimado ${formatMoney(costoGrupo)}`;
    card.querySelector("[data-group-msg]").textContent = mensaje;

    const waBtn = card.querySelector("[data-group-wa]");
    if (waBtn) {
      waBtn.href = url;
      waBtn.style.pointerEvents = seleccionados.length ? "auto" : "none";
      waBtn.style.opacity = seleccionados.length ? "1" : "0.5";
    }
    actualizarResumenGlobal();
  }

  function renderGrupos() {
    const visibles = obtenerGruposVisibles();
    actualizarBotonExpandir(visibles);

    if (!gruposData.length) {
      gruposContainer.innerHTML = `
        <div class="card compras-empty">
          Todos los productos activos tienen stock por encima del minimo.
        </div>`;
      actualizarResumenGlobal();
      return;
    }

    if (!visibles.length) {
      gruposContainer.innerHTML = `
        <div class="card compras-empty">
          No se encontraron productos o distribuidoras con esa busqueda.
        </div>`;
      actualizarResumenGlobal();
      return;
    }

    gruposContainer.innerHTML = visibles
      .map(({ grupo: g, gIdx, itemsVisibles, abierto }) => {
        const metaPartes = [];
        if (g.telefono_whatsapp) metaPartes.push(escapeHtml(g.telefono_whatsapp));
        if (g.contacto) metaPartes.push(escapeHtml(g.contacto));
        if (!metaPartes.length) {
          metaPartes.push(
            g.proveedor_id === null ? "Compra en feria o distribuidora" : "Sin telefono registrado"
          );
        }

        const filas = itemsVisibles
          .map(({ item: it, iIdx }) => {
            const sub = Math.round(it.cantidad_editada * it.precio_costo);
            const badgeVenc =
              it.estado_vencimiento === "VENCIDO"
                ? '<span class="badge badge-danger">Sin stock vigente</span>'
                : it.estado_vencimiento === "POR_VENCER"
                  ? '<span class="badge badge-warn">Por vencer</span>'
                  : "";
            const step = it.unidad === "KG" ? "0.1" : "1";

            return `
              <tr>
                <td style="width:36px;">
                  <input type="checkbox" class="item-check" data-group-idx="${gIdx}" data-item-idx="${iIdx}" ${
                    it.incluido ? "checked" : ""
                  }>
                </td>
                <td>
                  <div style="font-weight:600;">${escapeHtml(it.nombre)}</div>
                  <div class="compras-group-meta">
                    ${it.codigo_barras ? `<span class="tabular">${escapeHtml(it.codigo_barras)}</span> · ` : ""}
                    ${badgeVenc}
                  </div>
                </td>
                <td class="tabular">
                  <strong>${formatCant(it.stock_vendible)}</strong> / min ${formatCant(it.stock_minimo)} ${escapeHtml(it.unidad)}
                </td>
                <td>
                  <input
                    type="number"
                    min="0"
                    step="${step}"
                    class="form-input tabular compras-qty-input"
                    data-group-idx="${gIdx}"
                    data-item-idx="${iIdx}"
                    value="${formatCant(it.cantidad_editada)}"
                  >
                </td>
                <td class="tabular" data-item-sub="${gIdx}-${iIdx}">
                  <strong>${formatMoney(sub)}</strong>
                </td>
              </tr>`;
          })
          .join("");

        return `
          <article class="card compras-group-card ${abierto ? "open" : ""}" data-group-idx="${gIdx}">
            <div class="compras-group-head">
              <button type="button" class="compras-group-toggle" data-toggle-group="${gIdx}" aria-expanded="${abierto ? "true" : "false"}">
                <i data-lucide="chevron-down" class="compras-chevron"></i>
                <div>
                  <h2 class="compras-group-title">${escapeHtml(g.proveedor_nombre)}</h2>
                  <div class="compras-group-meta">
                    ${metaPartes.join(" · ")} · <span data-group-subtotal></span>
                  </div>
                </div>
              </button>
              <div class="compras-group-actions">
                <button type="button" class="btn btn-secondary" data-copy-group="${gIdx}">
                  <i data-lucide="copy"></i>
                  Copiar pedido
                </button>
                <a class="btn btn-primary" data-group-wa target="_blank" rel="noopener noreferrer" href="#">
                  <i data-lucide="message-circle"></i>
                  Enviar por WhatsApp
                </a>
              </div>
            </div>

            <div class="compras-group-body">
              <div class="table-wrap">
                <table class="data-table">
                  <thead>
                    <tr>
                      <th></th>
                      <th>Producto</th>
                      <th>Stock vigente / min</th>
                      <th>Pedir</th>
                      <th>Costo est.</th>
                    </tr>
                  </thead>
                  <tbody>${filas}</tbody>
                </table>
              </div>

              <div class="compras-msg-box">
                <div class="compras-msg-label">Vista previa del mensaje</div>
                <pre class="compras-msg-pre" data-group-msg></pre>
              </div>
            </div>
          </article>`;
      })
      .join("");

    visibles.forEach(({ gIdx }) => actualizarTarjetaGrupo(gIdx));
    if (window.lucide) window.lucide.createIcons();
  }

  async function cargarSugeridas() {
    const incluir = checkIncluirTodos.checked ? "true" : "false";
    const data = await apiFetch(`/api/v1/compras/sugeridas?incluir_todos=${incluir}`);
    gruposData = (data.grupos || []).map((g) => ({
      ...g,
      abierto: false,
      items: g.items.map((it) => ({
        ...it,
        incluido: true,
        cantidad_editada: it.cantidad_sugerida,
      })),
    }));
    renderGrupos();
  }

  async function cargarProveedores() {
    const incluir = checkProvInactivos.checked ? "true" : "false";
    proveedoresCache = await apiFetch(`/api/v1/compras/proveedores?incluir_inactivos=${incluir}`);
    renderTablaProveedores();
  }

  function renderTablaProveedores() {
    const colSpan = esAdmin ? 6 : 5;
    if (!proveedoresCache.length) {
      tbodyProveedores.innerHTML = `
        <tr>
          <td colspan="${colSpan}" style="text-align:center; color:var(--text-muted); padding:24px;">
            Sin proveedores registrados.
          </td>
        </tr>`;
      return;
    }

    tbodyProveedores.innerHTML = proveedoresCache
      .map((p) => {
        const estadoBadge = p.activo
          ? '<span class="badge badge-ok">Activo</span>'
          : '<span class="badge badge-neutral">Inactivo</span>';
        const acciones = esAdmin
          ? `
            <td>
              <div class="table-actions">
                <button type="button" class="btn-icon" data-prov-action="editar" data-id="${p.id}" title="Editar proveedor">
                  <i data-lucide="pencil"></i>
                </button>
                <button type="button" class="btn-icon" data-prov-action="estado" data-id="${p.id}" title="${
                  p.activo ? "Desactivar proveedor" : "Reactivar proveedor"
                }">
                  <i data-lucide="${p.activo ? "power-off" : "rotate-ccw"}"></i>
                </button>
              </div>
            </td>`
          : "";

        return `
          <tr class="${p.activo ? "" : "compras-row-inactive"}">
            <td><strong>${escapeHtml(p.nombre)}</strong></td>
            <td class="tabular">${escapeHtml(p.telefono_whatsapp || "-")}</td>
            <td>${escapeHtml(p.contacto || "-")}</td>
            <td class="tabular">${p.productos_asociados}</td>
            <td>${estadoBadge}</td>
            ${acciones}
          </tr>`;
      })
      .join("");

    if (window.lucide) window.lucide.createIcons();
  }

  function abrirModalNuevoProveedor() {
    fProvId.value = "";
    formProv.reset();
    provTitulo.textContent = "Nuevo proveedor";
    modalProv.classList.add("open");
    fProvNombre.focus();
  }

  function abrirModalEditarProveedor(p) {
    fProvId.value = p.id;
    fProvNombre.value = p.nombre;
    fProvWhatsapp.value = p.telefono_whatsapp || "";
    fProvContacto.value = p.contacto || "";
    provTitulo.textContent = `Editar: ${p.nombre}`;
    modalProv.classList.add("open");
    fProvNombre.focus();
  }

  tabBtnSugeridas.addEventListener("click", () => {
    tabBtnSugeridas.classList.add("active");
    tabBtnProveedores.classList.remove("active");
    panelSugeridas.style.display = "block";
    panelProveedores.style.display = "none";
    controlsSugeridas.style.display = "flex";
    controlsProveedores.style.display = "none";
    cargarSugeridas().catch((err) => showToast(err.message, "error"));
  });

  tabBtnProveedores.addEventListener("click", () => {
    tabBtnProveedores.classList.add("active");
    tabBtnSugeridas.classList.remove("active");
    panelSugeridas.style.display = "none";
    panelProveedores.style.display = "block";
    controlsSugeridas.style.display = "none";
    controlsProveedores.style.display = "flex";
    cargarProveedores().catch((err) => showToast(err.message, "error"));
  });

  if (inputSearch) {
    inputSearch.addEventListener("input", renderGrupos);
  }

  if (btnToggleTodos) {
    btnToggleTodos.addEventListener("click", () => {
      const visibles = obtenerGruposVisibles();
      const abrir = !(visibles.length > 0 && visibles.every((v) => v.abierto));
      visibles.forEach(({ grupo }) => {
        grupo.abierto = abrir;
      });
      renderGrupos();
    });
  }

  checkIncluirTodos.addEventListener("change", () => {
    cargarSugeridas().catch((err) => showToast(err.message, "error"));
  });
  document.getElementById("btn-refrescar-compras").addEventListener("click", () => {
    cargarSugeridas().catch((err) => showToast(err.message, "error"));
  });
  checkProvInactivos.addEventListener("change", () => {
    cargarProveedores().catch((err) => showToast(err.message, "error"));
  });

  gruposContainer.addEventListener("change", (e) => {
    const check = e.target.closest(".item-check");
    if (!check) return;
    const gIdx = Number(check.dataset.groupIdx);
    const iIdx = Number(check.dataset.itemIdx);
    if (!gruposData[gIdx] || !gruposData[gIdx].items[iIdx]) return;
    gruposData[gIdx].items[iIdx].incluido = check.checked;
    actualizarTarjetaGrupo(gIdx);
  });

  gruposContainer.addEventListener("input", (e) => {
    const qtyInput = e.target.closest(".compras-qty-input");
    if (!qtyInput) return;
    const gIdx = Number(qtyInput.dataset.groupIdx);
    const iIdx = Number(qtyInput.dataset.itemIdx);
    const item = gruposData[gIdx] && gruposData[gIdx].items[iIdx];
    if (!item) return;

    const val = Math.max(0, Number(qtyInput.value || 0));
    item.cantidad_editada = val;
    const subCell = gruposContainer.querySelector(`[data-item-sub="${gIdx}-${iIdx}"]`);
    if (subCell) {
      subCell.innerHTML = `<strong>${formatMoney(Math.round(val * item.precio_costo))}</strong>`;
    }
    actualizarTarjetaGrupo(gIdx);
  });

  gruposContainer.addEventListener("click", async (e) => {
    const toggleBtn = e.target.closest("[data-toggle-group]");
    if (toggleBtn) {
      const gIdx = Number(toggleBtn.dataset.toggleGroup);
      const grupo = gruposData[gIdx];
      const card = gruposContainer.querySelector(`[data-group-idx="${gIdx}"]`);
      if (grupo && card) {
        grupo.abierto = !card.classList.contains("open");
        card.classList.toggle("open", grupo.abierto);
        toggleBtn.setAttribute("aria-expanded", grupo.abierto ? "true" : "false");
        actualizarBotonExpandir(obtenerGruposVisibles());
      }
      return;
    }

    const copyBtn = e.target.closest("[data-copy-group]");
    if (!copyBtn) return;
    const gIdx = Number(copyBtn.dataset.copyGroup);
    const grupo = gruposData[gIdx];
    if (!grupo) return;
    const seleccionados = grupo.items.filter((i) => i.incluido && i.cantidad_editada > 0);
    if (!seleccionados.length) {
      showToast("Selecciona al menos un producto para copiar", "warn");
      return;
    }
    try {
      await copiarTexto(construirMensajeGrupo(grupo, seleccionados));
      showToast("Pedido copiado para WhatsApp");
    } catch (_err) {
      showToast("No se pudo copiar al portapapeles", "error");
    }
  });

  const btnNuevoProv = document.getElementById("btn-nuevo-proveedor");
  if (btnNuevoProv) btnNuevoProv.addEventListener("click", abrirModalNuevoProveedor);

  document.getElementById("modal-prov-cerrar").addEventListener("click", () => modalProv.classList.remove("open"));
  document.getElementById("modal-prov-cancelar").addEventListener("click", () => modalProv.classList.remove("open"));
  modalProv.addEventListener("click", (e) => {
    if (e.target === modalProv) modalProv.classList.remove("open");
  });

  formProv.addEventListener("submit", async (e) => {
    e.preventDefault();
    const id = fProvId.value;
    const payload = {
      nombre: fProvNombre.value.trim(),
      telefono_whatsapp: fProvWhatsapp.value.trim() || null,
      contacto: fProvContacto.value.trim() || null,
    };

    try {
      if (!id) {
        await apiFetch("/api/v1/compras/proveedores", {
          method: "POST",
          body: JSON.stringify(payload),
        });
        showToast("Proveedor creado");
      } else {
        await apiFetch(`/api/v1/compras/proveedores/${id}`, {
          method: "PUT",
          body: JSON.stringify(payload),
        });
        showToast("Proveedor actualizado");
      }
      modalProv.classList.remove("open");
      await Promise.all([cargarProveedores(), cargarSugeridas()]);
    } catch (err) {
      showToast(err.message, "error");
    }
  });

  tbodyProveedores.addEventListener("click", async (e) => {
    const btn = e.target.closest("[data-prov-action]");
    if (!btn) return;
    const id = Number(btn.dataset.id);
    const prov = proveedoresCache.find((p) => p.id === id);
    if (!prov) return;

    const action = btn.dataset.provAction;
    if (action === "editar") {
      abrirModalEditarProveedor(prov);
    } else if (action === "estado") {
      try {
        await apiFetch(`/api/v1/compras/proveedores/${id}/estado`, {
          method: "PATCH",
          body: JSON.stringify({ activo: !prov.activo }),
        });
        showToast(prov.activo ? "Proveedor desactivado" : "Proveedor reactivado");
        await Promise.all([cargarProveedores(), cargarSugeridas()]);
      } catch (err) {
        showToast(err.message, "error");
      }
    }
  });

  cargarSugeridas().catch((err) => showToast(err.message, "error"));
});
