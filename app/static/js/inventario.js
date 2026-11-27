document.addEventListener("DOMContentLoaded", () => {
  const { apiFetch, showToast } = window.StockBarrio;
  const esAdmin = Boolean(window.INVENTARIO_CONFIG && window.INVENTARIO_CONFIG.esAdmin);

  const elKpiActivos = document.getElementById("kpi-activos");
  const elKpiBajo = document.getElementById("kpi-bajo");
  const elKpiPorVencer = document.getElementById("kpi-por-vencer");
  const elKpiVencidos = document.getElementById("kpi-vencidos");
  const kpiCards = Array.from(document.querySelectorAll("[data-kpi-filter]"));

  const tabBtnProductos = document.getElementById("tab-btn-productos");
  const tabBtnMovimientos = document.getElementById("tab-btn-movimientos");
  const panelProductos = document.getElementById("panel-productos");
  const panelMovimientos = document.getElementById("panel-movimientos");

  const inputSearch = document.getElementById("inv-search");
  const selectCat = document.getElementById("inv-filter-cat");
  const selectVenc = document.getElementById("inv-filter-venc");
  const checkBajo = document.getElementById("inv-filter-bajo");
  const checkInactivos = document.getElementById("inv-filter-inactivos");
  const tbodyProductos = document.getElementById("inv-productos-tbody");
  const tbodyMovimientos = document.getElementById("inv-movimientos-tbody");

  const modalProducto = document.getElementById("modal-producto");
  const formProducto = document.getElementById("form-producto");
  const prodModalTitulo = document.getElementById("modal-producto-titulo");
  const fProdId = document.getElementById("prod-id");
  const fProdNombre = document.getElementById("prod-nombre");
  const fProdCodigo = document.getElementById("prod-codigo");
  const fProdUnidad = document.getElementById("prod-unidad");
  const fProdCategoria = document.getElementById("prod-categoria");
  const fProdProveedor = document.getElementById("prod-proveedor");
  const fProdCosto = document.getElementById("prod-costo");
  const fProdVenta = document.getElementById("prod-venta");
  const grupoStockInicial = document.getElementById("grupo-stock-inicial");
  const fProdStockInicial = document.getElementById("prod-stock-inicial");
  const fProdStockMinimo = document.getElementById("prod-stock-minimo");
  const fProdVencimiento = document.getElementById("prod-vencimiento");
  const prodVencimientoHint = document.getElementById("prod-vencimiento-hint");

  const catInlineBox = document.getElementById("cat-inline-box");
  const catNuevaNombre = document.getElementById("cat-nueva-nombre");

  const modalMov = document.getElementById("modal-movimiento");
  const formMov = document.getElementById("form-movimiento");
  const movTitulo = document.getElementById("modal-mov-titulo");
  const movSubtitulo = document.getElementById("modal-mov-subtitulo");
  const fMovProdId = document.getElementById("mov-prod-id");
  const fMovTipo = document.getElementById("mov-tipo");
  const fMovCantidad = document.getElementById("mov-cantidad");
  const movCantidadLabel = document.getElementById("mov-cantidad-label");
  const movVencGroup = document.getElementById("mov-venc-group");
  const fMovVencimiento = document.getElementById("mov-vencimiento");
  const movLoteGroup = document.getElementById("mov-lote-group");
  const fMovLoteId = document.getElementById("mov-lote-id");
  const fMovMotivo = document.getElementById("mov-motivo");

  const modalDetalle = document.getElementById("modal-detalle");
  const detTitulo = document.getElementById("modal-det-titulo");
  const detSubtitulo = document.getElementById("modal-det-subtitulo");
  const detLotesBox = document.getElementById("modal-det-lotes-box");
  const detLotes = document.getElementById("modal-det-lotes");
  const detMovs = document.getElementById("modal-det-movs");

  let productosCache = [];
  let categoriasCache = [];
  let proveedoresCache = [];
  let productoMovActual = null;
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

  function formatStock(valor) {
    const num = Number(valor || 0);
    return Number.isInteger(num)
      ? num.toLocaleString("es-CL")
      : num.toLocaleString("es-CL", { maximumFractionDigits: 3 });
  }

  function formatFecha(isoDate) {
    if (!isoDate) return "Sin fecha";
    const partes = String(isoDate).split("-");
    if (partes.length !== 3) return escapeHtml(isoDate);
    return `${partes[2]}/${partes[1]}/${partes[0]}`;
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

  function badgeSemaforo(estado, fecha) {
    if (estado === "VENCIDO") {
      return `<span class="badge badge-danger">Vencido (${formatFecha(fecha)})</span>`;
    }
    if (estado === "POR_VENCER") {
      return `<span class="badge badge-warn">Por vencer (${formatFecha(fecha)})</span>`;
    }
    if (estado === "OPTIMO") {
      return `<span class="badge badge-ok">Optimo (${formatFecha(fecha)})</span>`;
    }
    return `<span class="badge badge-neutral">Sin fecha</span>`;
  }

  function badgeTipoMovimiento(tipo) {
    if (tipo === "ENTRADA" || tipo === "ANULACION") {
      return `<span class="badge badge-ok">${escapeHtml(tipo)}</span>`;
    }
    if (tipo === "MERMA") {
      return `<span class="badge badge-danger">${escapeHtml(tipo)}</span>`;
    }
    if (tipo === "AJUSTE") {
      return `<span class="badge badge-warn">${escapeHtml(tipo)}</span>`;
    }
    return `<span class="badge badge-neutral">${escapeHtml(tipo)}</span>`;
  }

  function sincronizarKpiActivo() {
    const filtroVenc = selectVenc.value;
    const soloBajo = checkBajo.checked;
    kpiCards.forEach((card) => {
      const target = card.dataset.kpiFilter;
      let active = false;
      if (target === "TODOS") active = !filtroVenc && !soloBajo;
      if (target === "STOCK_BAJO") active = soloBajo && !filtroVenc;
      if (target === "POR_VENCER") active = filtroVenc === "POR_VENCER";
      if (target === "CON_VENCIDO") active = filtroVenc === "CON_VENCIDO";
      card.classList.toggle("active-filter", active);
    });
  }

  function poblarSelectsCatalogo() {
    const filtroCatVal = selectCat.value;
    const prodCatVal = fProdCategoria.value;
    selectCat.innerHTML = `<option value="">Todas las categorias</option>`;
    fProdCategoria.innerHTML = `<option value="">Sin categoria</option>`;
    for (const c of categoriasCache) {
      const opt1 = `<option value="${c.id}">${escapeHtml(c.nombre)}</option>`;
      selectCat.insertAdjacentHTML("beforeend", opt1);
      fProdCategoria.insertAdjacentHTML("beforeend", opt1);
    }
    selectCat.value = filtroCatVal;
    fProdCategoria.value = prodCatVal;

    const prodProvVal = fProdProveedor.value;
    fProdProveedor.innerHTML = `<option value="">Sin proveedor (compra presencial)</option>`;
    for (const prov of proveedoresCache) {
      fProdProveedor.insertAdjacentHTML(
        "beforeend",
        `<option value="${prov.id}">${escapeHtml(prov.nombre)}</option>`
      );
    }
    fProdProveedor.value = prodProvVal;
  }

  async function cargarResumen() {
    const res = await apiFetch("/api/v1/inventario/resumen");
    elKpiActivos.textContent = res.total_activos;
    elKpiBajo.textContent = res.stock_bajo;
    elKpiPorVencer.textContent = res.por_vencer;
    elKpiVencidos.textContent = res.vencidos;
  }

  async function cargarCatalogos() {
    const [cats, provs] = await Promise.all([
      apiFetch("/api/v1/inventario/categorias"),
      apiFetch("/api/v1/inventario/proveedores"),
    ]);
    categoriasCache = cats;
    proveedoresCache = provs;
    poblarSelectsCatalogo();
  }

  async function cargarProductos() {
    sincronizarKpiActivo();
    const params = new URLSearchParams();
    const q = inputSearch.value.trim();
    const catId = selectCat.value;
    const venc = selectVenc.value;

    if (q) params.set("q", q);
    if (catId) params.set("categoria_id", catId);
    if (venc && venc !== "CON_VENCIDO") params.set("estado_vencimiento", venc);
    if (checkBajo.checked) params.set("solo_stock_bajo", "true");
    if (checkInactivos.checked) params.set("incluir_inactivos", "true");

    const url = `/api/v1/inventario/productos${params.toString() ? "?" + params.toString() : ""}`;
    let lista = await apiFetch(url);
    if (venc === "CON_VENCIDO") {
      lista = lista.filter((p) => p.estado_vencimiento === "VENCIDO" || p.stock_vencido > 0);
    }
    productosCache = lista;
    renderTablaProductos();
  }

  function renderTablaProductos() {
    if (!productosCache.length) {
      tbodyProductos.innerHTML = `
        <tr>
          <td colspan="5" style="text-align:center; color:var(--text-muted); padding:24px;">
            No se encontraron productos con los filtros actuales.
          </td>
        </tr>`;
      return;
    }

    tbodyProductos.innerHTML = productosCache
      .map((p) => {
        const metaParts = [];
        if (p.codigo_barras) metaParts.push(`<span class="tabular">${escapeHtml(p.codigo_barras)}</span>`);
        metaParts.push(escapeHtml(p.categoria_nombre || "Sin categoria"));
        if (p.proveedor_nombre) metaParts.push(escapeHtml(p.proveedor_nombre));
        if (!p.activo) metaParts.push("Inactivo");

        const stockBajoBadge = p.stock_bajo
          ? `<span class="badge badge-warn">Bajo min (${formatStock(p.stock_minimo)})</span>`
          : "";
        const stockVencidoBadge =
          p.stock_vencido > 0
            ? `<span class="badge badge-danger">${formatStock(p.stock_vencido)} vencido(s)</span>`
            : "";
        const tandasNote =
          p.lotes.length > 1
            ? `<div class="inv-lote-note">${p.lotes.length} tandas activas (FEFO)</div>`
            : "";

        const btnEditar = esAdmin
          ? `<button type="button" class="btn-icon" data-action="editar" data-id="${p.id}" title="Editar producto"><i data-lucide="pencil"></i></button>`
          : "";
        const btnToggle = esAdmin
          ? `<button type="button" class="btn-icon" data-action="estado" data-id="${p.id}" title="${
              p.activo ? "Desactivar producto" : "Reactivar producto"
            }"><i data-lucide="${p.activo ? "power-off" : "rotate-ccw"}"></i></button>`
          : "";

        return `
          <tr class="${p.activo ? "" : "inv-row-inactive"}">
            <td>
              <div class="inv-prod-name">${escapeHtml(p.nombre)}</div>
              <div class="inv-prod-meta">${metaParts.join(" · ")}</div>
            </td>
            <td>
              <div class="tabular"><strong>${formatMoney(p.precio_venta)}</strong></div>
              <div class="inv-prod-meta tabular">Costo ${formatMoney(p.precio_costo)}</div>
            </td>
            <td>
              <div class="tabular"><strong>${formatStock(p.stock_actual)}</strong> ${escapeHtml(p.unidad)}</div>
              <div class="inv-badges-stack" style="margin-top:4px;">
                ${stockBajoBadge}
                ${stockVencidoBadge}
              </div>
            </td>
            <td>
              <div class="inv-badges-stack">
                ${badgeSemaforo(p.estado_vencimiento, p.fecha_vencimiento)}
              </div>
              ${tandasNote}
            </td>
            <td>
              <div class="table-actions">
                <button type="button" class="btn btn-secondary" data-action="mov" data-id="${p.id}" style="padding:5px 10px; font-size:12.5px;">
                  ${esAdmin ? "Stock / Merma" : "Merma"}
                </button>
                <button type="button" class="btn-icon" data-action="detalle" data-id="${p.id}" title="Ver tandas y movimientos">
                  <i data-lucide="layers"></i>
                </button>
                ${btnEditar}
                ${btnToggle}
              </div>
            </td>
          </tr>`;
      })
      .join("");

    if (window.lucide) window.lucide.createIcons();
  }

  async function cargarMovimientos() {
    const movs = await apiFetch("/api/v1/inventario/movimientos?limit=50");
    if (!movs.length) {
      tbodyMovimientos.innerHTML = `
        <tr>
          <td colspan="7" style="text-align:center; color:var(--text-muted); padding:24px;">
            Sin movimientos registrados todavia.
          </td>
        </tr>`;
      return;
    }

    tbodyMovimientos.innerHTML = movs
      .map((m) => {
        const signo = m.cantidad > 0 && m.tipo !== "VENTA" ? "+" : "";
        const cambioTxt = m.tipo === "VENTA" ? `-${formatStock(Math.abs(m.cantidad))}` : `${signo}${formatStock(m.cantidad)}`;
        return `
          <tr>
            <td class="tabular">${formatFechaHora(m.creado_en)}</td>
            <td><strong>${escapeHtml(m.producto_nombre)}</strong></td>
            <td>${badgeTipoMovimiento(m.tipo)}</td>
            <td class="tabular">${cambioTxt}</td>
            <td class="tabular">${formatStock(m.stock_anterior)} &rarr; <strong>${formatStock(m.stock_nuevo)}</strong></td>
            <td>${escapeHtml(m.motivo || "-")}</td>
            <td>${escapeHtml(m.usuario_nombre)}</td>
          </tr>`;
      })
      .join("");
  }

  async function recargarTodo() {
    await Promise.all([cargarResumen(), cargarProductos()]);
    if (panelMovimientos.style.display !== "none") {
      await cargarMovimientos();
    }
  }

  function abrirModalNuevoProducto() {
    fProdId.value = "";
    formProducto.reset();
    fProdUnidad.value = "UN";
    fProdCosto.value = "0";
    fProdStockInicial.value = "0";
    fProdStockMinimo.value = "5";
    fProdVencimiento.disabled = false;
    prodVencimientoHint.textContent =
      'Dejar vacio para productos no perecibles. Si manejas varias tandas, usa "Stock / Merma > Entrada".';
    grupoStockInicial.style.display = "block";
    fProdStockInicial.required = true;
    catInlineBox.classList.remove("open");
    prodModalTitulo.textContent = "Nuevo producto";
    modalProducto.classList.add("open");
    fProdNombre.focus();
  }

  function abrirModalEditarProducto(p) {
    fProdId.value = p.id;
    fProdNombre.value = p.nombre;
    fProdCodigo.value = p.codigo_barras || "";
    fProdUnidad.value = p.unidad;
    fProdCategoria.value = p.categoria_id ? String(p.categoria_id) : "";
    fProdProveedor.value = p.proveedor_id ? String(p.proveedor_id) : "";
    fProdCosto.value = p.precio_costo;
    fProdVenta.value = p.precio_venta;
    fProdStockMinimo.value = p.stock_minimo;
    fProdVencimiento.value = p.fecha_vencimiento || "";
    grupoStockInicial.style.display = "none";
    fProdStockInicial.required = false;
    catInlineBox.classList.remove("open");

    if (p.lotes.length > 1) {
      fProdVencimiento.disabled = true;
      prodVencimientoHint.textContent =
        "Este producto tiene varias tandas activas. Gestiona nuevas fechas desde Stock / Merma > Entrada.";
    } else {
      fProdVencimiento.disabled = false;
      prodVencimientoHint.textContent =
        "Dejar vacio para productos no perecibles.";
    }

    prodModalTitulo.textContent = `Editar: ${p.nombre}`;
    modalProducto.classList.add("open");
    fProdNombre.focus();
  }

  function actualizarCamposMovimiento() {
    const tipo = fMovTipo.value;
    if (tipo === "ENTRADA") {
      movCantidadLabel.textContent = `Cantidad a ingresar (${productoMovActual?.unidad || "UN"})`;
      movVencGroup.style.display = "block";
      movLoteGroup.style.display = "none";
      fMovMotivo.placeholder = "Ej: Compra presencial / reposicion";
    } else if (tipo === "MERMA") {
      movCantidadLabel.textContent = `Cantidad a mermar (${productoMovActual?.unidad || "UN"})`;
      movVencGroup.style.display = "none";
      const lotes = productoMovActual?.lotes || [];
      if (lotes.length > 0) {
        movLoteGroup.style.display = "block";
        fMovLoteId.innerHTML = `<option value="">Automatico (tanda mas proxima)</option>`;
        for (const l of lotes) {
          const estadoTxt = l.vencido ? "VENCIDO" : l.estado_vencimiento;
          fMovLoteId.insertAdjacentHTML(
            "beforeend",
            `<option value="${l.id}">${formatFecha(l.fecha_vencimiento)} · ${formatStock(l.cantidad_disponible)} disp. (${estadoTxt})</option>`
          );
        }
      } else {
        movLoteGroup.style.display = "none";
      }
      fMovMotivo.placeholder = "Ej: Producto vencido o envase danado";
    } else {
      movCantidadLabel.textContent = `Stock fisico final (${productoMovActual?.unidad || "UN"})`;
      movVencGroup.style.display = "none";
      movLoteGroup.style.display = "none";
      fMovMotivo.placeholder = "Ej: Conteo fisico de estanteria";
    }
  }

  function abrirModalMovimiento(p, opts = {}) {
    productoMovActual = p;
    fMovProdId.value = p.id;
    formMov.reset();
    fMovTipo.value = opts.tipo || (esAdmin ? "ENTRADA" : "MERMA");
    movTitulo.textContent = `Movimiento: ${p.nombre}`;
    movSubtitulo.textContent = `Stock actual: ${formatStock(p.stock_actual)} ${p.unidad} (${formatStock(
      p.stock_vendible
    )} vigentes · ${formatStock(p.stock_vencido)} vencidos)`;
    actualizarCamposMovimiento();
    if (opts.loteId) fMovLoteId.value = String(opts.loteId);
    if (opts.cantidad !== undefined) fMovCantidad.value = String(opts.cantidad);
    if (opts.motivo) fMovMotivo.value = opts.motivo;
    modalMov.classList.add("open");
    fMovCantidad.focus();
  }

  async function abrirModalDetalle(p) {
    detTitulo.textContent = p.nombre;
    detSubtitulo.textContent = `Stock total: ${formatStock(p.stock_actual)} ${p.unidad} · Vigentes: ${formatStock(
      p.stock_vendible
    )} · Vencidos: ${formatStock(p.stock_vencido)}`;

    if (p.lotes.length > 0) {
      detLotesBox.style.display = "block";
      detLotes.innerHTML = p.lotes
        .map((l) => {
          return `
            <div class="inv-lote-row">
              <div>
                ${badgeSemaforo(l.estado_vencimiento, l.fecha_vencimiento)}
                <span class="tabular" style="margin-left:8px;"><strong>${formatStock(l.cantidad_disponible)}</strong> ${escapeHtml(p.unidad)}</span>
              </div>
              <button type="button" class="btn btn-secondary" data-merma-lote="${l.id}" data-merma-cant="${l.cantidad_disponible}" data-prod-id="${p.id}" style="padding:4px 10px; font-size:12px;">
                Registrar merma
              </button>
            </div>`;
        })
        .join("");
    } else {
      detLotesBox.style.display = "none";
      detLotes.innerHTML = "";
    }

    detMovs.innerHTML = `<tr><td colspan="5" style="text-align:center; color:var(--text-muted); padding:16px;">Cargando...</td></tr>`;
    modalDetalle.classList.add("open");

    try {
      const movs = await apiFetch(`/api/v1/inventario/movimientos?producto_id=${p.id}&limit=15`);
      if (!movs.length) {
        detMovs.innerHTML = `<tr><td colspan="5" style="text-align:center; color:var(--text-muted); padding:16px;">Sin movimientos registrados.</td></tr>`;
        return;
      }
      detMovs.innerHTML = movs
        .map((m) => {
          const signo = m.cantidad > 0 && m.tipo !== "VENTA" ? "+" : "";
          const cambioTxt = m.tipo === "VENTA" ? `-${formatStock(Math.abs(m.cantidad))}` : `${signo}${formatStock(m.cantidad)}`;
          return `
            <tr>
              <td class="tabular">${formatFechaHora(m.creado_en)}</td>
              <td>${badgeTipoMovimiento(m.tipo)}</td>
              <td class="tabular">${cambioTxt}</td>
              <td class="tabular">${formatStock(m.stock_anterior)} &rarr; ${formatStock(m.stock_nuevo)}</td>
              <td>${escapeHtml(m.motivo || "-")}</td>
            </tr>`;
        })
        .join("");
    } catch (err) {
      detMovs.innerHTML = `<tr><td colspan="5" style="color:var(--danger); padding:16px;">${escapeHtml(err.message)}</td></tr>`;
    }
  }

  kpiCards.forEach((card) => {
    card.addEventListener("click", () => {
      const target = card.dataset.kpiFilter;
      if (target === "TODOS") {
        selectVenc.value = "";
        checkBajo.checked = false;
      } else if (target === "STOCK_BAJO") {
        selectVenc.value = "";
        checkBajo.checked = true;
      } else if (target === "POR_VENCER") {
        selectVenc.value = "POR_VENCER";
        checkBajo.checked = false;
      } else if (target === "CON_VENCIDO") {
        selectVenc.value = "CON_VENCIDO";
        checkBajo.checked = false;
      }
      tabBtnProductos.click();
      cargarProductos();
    });
  });

  tabBtnProductos.addEventListener("click", () => {
    tabBtnProductos.classList.add("active");
    tabBtnMovimientos.classList.remove("active");
    panelProductos.style.display = "block";
    panelMovimientos.style.display = "none";
  });

  tabBtnMovimientos.addEventListener("click", () => {
    tabBtnMovimientos.classList.add("active");
    tabBtnProductos.classList.remove("active");
    panelProductos.style.display = "none";
    panelMovimientos.style.display = "block";
    cargarMovimientos().catch((err) => showToast(err.message, "error"));
  });

  inputSearch.addEventListener("input", () => {
    clearTimeout(searchTimer);
    searchTimer = setTimeout(() => {
      cargarProductos().catch((err) => showToast(err.message, "error"));
    }, 220);
  });

  [selectCat, selectVenc, checkBajo, checkInactivos].forEach((el) => {
    el.addEventListener("change", () => {
      cargarProductos().catch((err) => showToast(err.message, "error"));
    });
  });

  const btnNuevo = document.getElementById("btn-nuevo-producto");
  if (btnNuevo) btnNuevo.addEventListener("click", abrirModalNuevoProducto);

  document.getElementById("modal-producto-cerrar").addEventListener("click", () => modalProducto.classList.remove("open"));
  document.getElementById("modal-producto-cancelar").addEventListener("click", () => modalProducto.classList.remove("open"));
  document.getElementById("modal-mov-cerrar").addEventListener("click", () => modalMov.classList.remove("open"));
  document.getElementById("modal-mov-cancelar").addEventListener("click", () => modalMov.classList.remove("open"));
  document.getElementById("modal-det-cerrar").addEventListener("click", () => modalDetalle.classList.remove("open"));
  document.getElementById("modal-det-aceptar").addEventListener("click", () => modalDetalle.classList.remove("open"));

  [modalProducto, modalMov, modalDetalle].forEach((m) => {
    m.addEventListener("click", (e) => {
      if (e.target === m) m.classList.remove("open");
    });
  });

  document.getElementById("btn-toggle-cat").addEventListener("click", () => {
    catInlineBox.classList.toggle("open");
    if (catInlineBox.classList.contains("open")) catNuevaNombre.focus();
  });

  document.getElementById("btn-guardar-cat").addEventListener("click", async () => {
    const nombre = catNuevaNombre.value.trim();
    if (nombre.length < 2) {
      showToast("Escribe al menos 2 caracteres para la categoria", "warn");
      return;
    }
    try {
      const nueva = await apiFetch("/api/v1/inventario/categorias", {
        method: "POST",
        body: JSON.stringify({ nombre }),
      });
      await cargarCatalogos();
      fProdCategoria.value = String(nueva.id);
      catNuevaNombre.value = "";
      catInlineBox.classList.remove("open");
      showToast("Categoria creada");
    } catch (err) {
      showToast(err.message, "error");
    }
  });

  formProducto.addEventListener("submit", async (e) => {
    e.preventDefault();
    const id = fProdId.value;
    const basePayload = {
      nombre: fProdNombre.value.trim(),
      codigo_barras: fProdCodigo.value.trim() || null,
      categoria_id: fProdCategoria.value ? Number(fProdCategoria.value) : null,
      proveedor_id: fProdProveedor.value ? Number(fProdProveedor.value) : null,
      unidad: fProdUnidad.value,
      precio_costo: Number(fProdCosto.value || 0),
      precio_venta: Number(fProdVenta.value),
      stock_minimo: Number(fProdStockMinimo.value || 0),
      fecha_vencimiento: fProdVencimiento.value || null,
    };

    try {
      if (!id) {
        basePayload.stock_actual = Number(fProdStockInicial.value || 0);
        await apiFetch("/api/v1/inventario/productos", {
          method: "POST",
          body: JSON.stringify(basePayload),
        });
        showToast("Producto creado");
      } else {
        await apiFetch(`/api/v1/inventario/productos/${id}`, {
          method: "PUT",
          body: JSON.stringify(basePayload),
        });
        showToast("Producto actualizado");
      }
      modalProducto.classList.remove("open");
      await recargarTodo();
    } catch (err) {
      showToast(err.message, "error");
    }
  });

  fMovTipo.addEventListener("change", actualizarCamposMovimiento);

  formMov.addEventListener("submit", async (e) => {
    e.preventDefault();
    const prodId = fMovProdId.value;
    const payload = {
      tipo: fMovTipo.value,
      cantidad: Number(fMovCantidad.value),
      motivo: fMovMotivo.value.trim(),
    };
    if (fMovTipo.value === "ENTRADA" && fMovVencimiento.value) {
      payload.fecha_vencimiento = fMovVencimiento.value;
    }
    if (fMovTipo.value === "MERMA" && fMovLoteId.value) {
      payload.lote_id = Number(fMovLoteId.value);
    }

    try {
      await apiFetch(`/api/v1/inventario/productos/${prodId}/movimientos`, {
        method: "POST",
        body: JSON.stringify(payload),
      });
      modalMov.classList.remove("open");
      showToast("Movimiento registrado");
      await recargarTodo();
    } catch (err) {
      showToast(err.message, "error");
    }
  });

  tbodyProductos.addEventListener("click", async (e) => {
    const btn = e.target.closest("[data-action]");
    if (!btn) return;
    const id = Number(btn.dataset.id);
    const prod = productosCache.find((p) => p.id === id);
    if (!prod) return;

    const action = btn.dataset.action;
    if (action === "editar") {
      abrirModalEditarProducto(prod);
    } else if (action === "mov") {
      abrirModalMovimiento(prod);
    } else if (action === "detalle") {
      abrirModalDetalle(prod);
    } else if (action === "estado") {
      try {
        await apiFetch(`/api/v1/inventario/productos/${id}/estado`, {
          method: "PATCH",
          body: JSON.stringify({ activo: !prod.activo }),
        });
        showToast(prod.activo ? "Producto desactivado" : "Producto reactivado");
        await recargarTodo();
      } catch (err) {
        showToast(err.message, "error");
      }
    }
  });

  detLotes.addEventListener("click", (e) => {
    const btn = e.target.closest("[data-merma-lote]");
    if (!btn) return;
    const prodId = Number(btn.dataset.prodId);
    const loteId = Number(btn.dataset.mermaLote);
    const cant = Number(btn.dataset.mermaCant);
    const prod = productosCache.find((p) => p.id === prodId);
    if (!prod) return;

    modalDetalle.classList.remove("open");
    abrirModalMovimiento(prod, {
      tipo: "MERMA",
      loteId,
      cantidad: cant,
      motivo: "Retiro de tanda vencida",
    });
  });

  Promise.all([cargarCatalogos(), cargarResumen(), cargarProductos()]).catch((err) => {
    showToast(err.message, "error");
  });
});
