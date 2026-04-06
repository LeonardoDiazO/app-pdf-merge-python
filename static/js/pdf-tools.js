/**
 * pdf-tools.js — Módulo compartido para PDF Tools
 * Contiene: toasts, validación, drop zone, previsualización, descarga.
 */
const PdfTools = (() => {

  // ── Toasts ───────────────────────────────────────────────────────────────

  let _toastContainer = null;

  function _getToastContainer() {
    if (!_toastContainer) {
      _toastContainer = document.createElement('div');
      _toastContainer.className = 'toast-container';
      document.body.appendChild(_toastContainer);
    }
    return _toastContainer;
  }

  function showToast(message, type = 'success', duration = 4500) {
    const icons = { success: '✓', error: '✕', warning: '⚠', info: 'ℹ' };
    const container = _getToastContainer();
    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    toast.innerHTML = `<span class="toast-icon">${icons[type] || icons.info}</span><span>${message}</span>`;
    container.appendChild(toast);

    const remove = () => {
      if (toast.classList.contains('removing')) return;
      toast.classList.add('removing');
      toast.addEventListener('animationend', () => toast.remove(), { once: true });
    };
    toast.addEventListener('click', remove);
    setTimeout(remove, duration);
  }

  // ── Utilidades de archivo ─────────────────────────────────────────────────

  function formatFileSize(bytes) {
    const kb = bytes / 1024;
    return kb > 1024 ? `${(kb / 1024).toFixed(1)} MB` : `${kb.toFixed(1)} KB`;
  }

  function validatePdfFile(file, maxSizeMB = 20) {
    if (!file) return { valid: false, error: 'No se seleccionó ningún archivo' };
    if (file.type !== 'application/pdf' && !file.name.toLowerCase().endsWith('.pdf')) {
      return { valid: false, error: 'El archivo debe ser un PDF' };
    }
    if (file.size === 0) {
      return { valid: false, error: 'El archivo está vacío' };
    }
    if (file.size > maxSizeMB * 1024 * 1024) {
      return { valid: false, error: `El archivo supera el límite de ${maxSizeMB} MB (${formatFileSize(file.size)})` };
    }
    return { valid: true };
  }

  // ── Drop Zone ─────────────────────────────────────────────────────────────

  function initDropZone(dropZoneEl, fileInputEl, onFilesSelected) {
    dropZoneEl.addEventListener('click', () => fileInputEl.click());

    fileInputEl.addEventListener('change', (e) => {
      if (e.target.files.length) onFilesSelected(e.target.files);
    });

    dropZoneEl.addEventListener('dragover', (e) => {
      e.preventDefault();
      dropZoneEl.classList.add('drag-over');
    });

    dropZoneEl.addEventListener('dragleave', (e) => {
      if (!dropZoneEl.contains(e.relatedTarget)) {
        dropZoneEl.classList.remove('drag-over');
      }
    });

    dropZoneEl.addEventListener('drop', (e) => {
      e.preventDefault();
      dropZoneEl.classList.remove('drag-over');
      if (e.dataTransfer.files.length) onFilesSelected(e.dataTransfer.files);
    });
  }

  function updateDropZoneWithFileInfo(dropZoneEl, file) {
    dropZoneEl.innerHTML = `
      <div class="drop-zone-icon">📄</div>
      <div class="drop-zone-text" style="font-weight:600;color:var(--text-primary)">${file.name}</div>
      <div class="drop-zone-subtext">${formatFileSize(file.size)} &nbsp;·&nbsp; Haz clic para cambiar</div>
    `;
  }

  // ── Previsualización PDF ──────────────────────────────────────────────────

  const WORKER_SRC = 'https://cdnjs.cloudflare.com/ajax/libs/pdf.js/3.4.120/pdf.worker.min.js';

  async function renderPagePreviews(file, containerEl, { actionButton = null, onToggle = null } = {}) {
    if (typeof pdfjsLib === 'undefined') {
      showToast('No se pudo cargar la librería de previsualización', 'error');
      return null;
    }

    pdfjsLib.GlobalWorkerOptions.workerSrc = WORKER_SRC;

    const selectedPages = new Set();
    const checkboxes = [];

    containerEl.innerHTML = `
      <div style="grid-column:1/-1;text-align:center;padding:2rem;color:var(--text-secondary)">
        <span class="btn-spinner" style="border-color:rgba(0,0,0,.15);border-top-color:#9ca3af;width:28px;height:28px;margin-bottom:.75rem;display:inline-block"></span>
        <div>Cargando páginas...</div>
      </div>
    `;

    let pdf;
    try {
      const arrayBuffer = await file.arrayBuffer();
      pdf = await pdfjsLib.getDocument(arrayBuffer).promise;
    } catch (e) {
      containerEl.innerHTML = '';
      showToast('No se pudo leer el PDF. ¿Está protegido con contraseña?', 'error');
      return null;
    }

    containerEl.innerHTML = '';
    const numPages = pdf.numPages;

    for (let i = 1; i <= numPages; i++) {
      const page = await pdf.getPage(i);
      const viewport = page.getViewport({ scale: 0.8 });

      const canvas = document.createElement('canvas');
      canvas.width = viewport.width;
      canvas.height = viewport.height;
      await page.render({ canvasContext: canvas.getContext('2d'), viewport }).promise;

      const container = document.createElement('div');
      container.className = 'page-preview';
      container.dataset.pageIndex = i - 1;
      container.setAttribute('tabindex', '0');
      container.setAttribute('role', 'checkbox');
      container.setAttribute('aria-checked', 'false');
      container.setAttribute('aria-label', `Página ${i}`);

      const checkbox = document.createElement('input');
      checkbox.type = 'checkbox';
      checkbox.className = 'page-checkbox';
      checkbox.dataset.pageIndex = i - 1;
      checkboxes.push(checkbox);

      const pageNum = document.createElement('div');
      pageNum.className = 'page-number';
      pageNum.textContent = `Página ${i}`;

      container.appendChild(checkbox);
      container.appendChild(canvas);
      container.appendChild(pageNum);

      const pageIdx = i - 1;
      const toggle = (selected) => {
        checkbox.checked = selected;
        container.setAttribute('aria-checked', String(selected));
        container.classList.toggle('selected', selected);
        if (selected) selectedPages.add(pageIdx);
        else selectedPages.delete(pageIdx);
        if (actionButton) actionButton.disabled = selectedPages.size === 0;
        if (onToggle) onToggle(selectedPages, checkboxes);
      };

      container.addEventListener('click', (e) => {
        if (e.target !== checkbox) toggle(!checkbox.checked);
      });
      checkbox.addEventListener('change', (e) => {
        e.stopPropagation();
        toggle(checkbox.checked);
      });
      container.addEventListener('keydown', (e) => {
        if (e.key === ' ' || e.key === 'Enter') { e.preventDefault(); toggle(!checkbox.checked); }
      });

      containerEl.appendChild(container);
    }

    return { selectedPages, checkboxes, numPages };
  }

  // ── Descarga ──────────────────────────────────────────────────────────────

  function downloadBlob(blob, filename) {
    const url = URL.createObjectURL(blob);
    const a = Object.assign(document.createElement('a'), { href: url, download: filename });
    document.body.appendChild(a);
    a.click();
    URL.revokeObjectURL(url);
    a.remove();
  }

  function showDownloadSuccess(filename, anchorEl, onReset) {
    document.querySelectorAll('.success-banner').forEach(b => b.remove());
    const banner = document.createElement('div');
    banner.className = 'success-banner';
    banner.innerHTML = `
      <div class="success-banner-icon">✅</div>
      <div class="success-banner-text">
        <div class="success-banner-title">¡Archivo generado exitosamente!</div>
        <div class="success-banner-filename">${filename}</div>
      </div>
      <button class="success-banner-action" type="button">Procesar otro</button>
    `;
    banner.querySelector('button').addEventListener('click', () => {
      banner.remove();
      if (onReset) onReset();
    });
    anchorEl.after(banner);
  }

  // ── Estado de botón ───────────────────────────────────────────────────────

  function setButtonLoading(btn, text) {
    btn._originalHTML = btn.innerHTML;
    btn.disabled = true;
    btn.innerHTML = `<span class="btn-spinner"></span>${text}`;
  }

  function resetButton(btn) {
    if (btn._originalHTML !== undefined) btn.innerHTML = btn._originalHTML;
    btn.disabled = false;
    delete btn._originalHTML;
  }

  // ── Manejo de errores del servidor ────────────────────────────────────────

  async function getErrorMessage(response) {
    try {
      const data = await response.json();
      return data.error || 'Error desconocido';
    } catch {
      return (await response.text().catch(() => '')) || `Error del servidor (${response.status})`;
    }
  }

  // ── Seleccionar todas ─────────────────────────────────────────────────────

  function handleSelectAll(btn, getState, actionButton) {
    const { selectedPages, checkboxes } = getState();
    const allSelected = selectedPages.size === checkboxes.length && checkboxes.length > 0;
    checkboxes.forEach((cb, idx) => {
      cb.checked = !allSelected;
      const preview = cb.closest('.page-preview');
      preview.classList.toggle('selected', !allSelected);
      preview.setAttribute('aria-checked', String(!allSelected));
      if (!allSelected) selectedPages.add(idx);
      else selectedPages.delete(idx);
    });
    if (actionButton) actionButton.disabled = selectedPages.size === 0;
    btn.textContent = allSelected ? 'Seleccionar todas' : 'Deseleccionar todas';
  }

  return {
    showToast,
    formatFileSize,
    validatePdfFile,
    initDropZone,
    updateDropZoneWithFileInfo,
    renderPagePreviews,
    downloadBlob,
    showDownloadSuccess,
    setButtonLoading,
    resetButton,
    getErrorMessage,
    handleSelectAll,
  };
})();
