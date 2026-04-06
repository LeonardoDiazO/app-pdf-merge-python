const dropZone      = document.getElementById('dropZone');
const fileInput     = document.getElementById('fileInput');
const configSection = document.getElementById('configSection');
const paginateBtn   = document.getElementById('paginateButton');
const fromPageInput = document.getElementById('fromPage');
const startNumInput = document.getElementById('startNumber');
const totalPagesEl  = document.getElementById('totalPagesHint');

const ORIGINAL_DROP_ZONE_HTML = dropZone.innerHTML;

let currentFile  = null;
let selectedPos  = 'bottom-center';
let selectedFmt  = 'number';
let selectedSize = 12;
let coverExisting = false;

// ── Drop zone ──────────────────────────────────────────────────────────────

PdfTools.initDropZone(dropZone, fileInput, handleFiles);

async function handleFiles(files) {
  const file = files[0];
  const v = PdfTools.validatePdfFile(file, 20);
  if (!v.valid) { PdfTools.showToast(v.error, 'error'); return; }

  currentFile = file;
  document.querySelectorAll('.success-banner').forEach(b => b.remove());
  PdfTools.updateDropZoneWithFileInfo(dropZone, file);

  // Get page count client-side via PDF.js to show hint
  if (typeof pdfjsLib !== 'undefined') {
    try {
      pdfjsLib.GlobalWorkerOptions.workerSrc =
        'https://cdnjs.cloudflare.com/ajax/libs/pdf.js/3.4.120/pdf.worker.min.js';
      const ab  = await file.arrayBuffer();
      const pdf = await pdfjsLib.getDocument(ab).promise;
      const n   = pdf.numPages;
      fromPageInput.max = n;
      totalPagesEl.textContent = `Este PDF tiene ${n} página${n !== 1 ? 's' : ''}.`;
      totalPagesEl.style.display = 'block';
    } catch {
      totalPagesEl.style.display = 'none';
    }
  }

  configSection.style.display = 'block';
  paginateBtn.disabled = false;
}

// ── Position picker ────────────────────────────────────────────────────────

document.querySelectorAll('.pos-btn').forEach(btn => {
  btn.addEventListener('click', () => {
    document.querySelectorAll('.pos-btn').forEach(b => b.classList.remove('selected'));
    btn.classList.add('selected');
    selectedPos = btn.dataset.pos;
  });
});

// ── Format selector ────────────────────────────────────────────────────────

document.querySelectorAll('.fmt-btn').forEach(btn => {
  btn.addEventListener('click', () => {
    document.querySelectorAll('.fmt-btn').forEach(b => b.classList.remove('selected'));
    btn.classList.add('selected');
    selectedFmt = btn.dataset.fmt;
    updateFormatPreview();
  });
});

function updateFormatPreview() {
  const n     = parseInt(startNumInput.value) || 1;
  const total = n + 9; // mock total
  const texts = {
    number:      String(n),
    page_number: `Página ${n}`,
    of_total:    `${n} / ${total}`,
    classic:     `- ${n} -`,
  };
  const previewEl = document.getElementById('formatPreview');
  if (previewEl) previewEl.textContent = texts[selectedFmt] || String(n);
}

startNumInput.addEventListener('input', updateFormatPreview);

// ── Font size selector ─────────────────────────────────────────────────────

document.querySelectorAll('.size-btn').forEach(btn => {
  btn.addEventListener('click', () => {
    document.querySelectorAll('.size-btn').forEach(b => b.classList.remove('selected'));
    btn.classList.add('selected');
    selectedSize = parseInt(btn.dataset.size);
  });
});

// ── Cover existing toggle ──────────────────────────────────────────────────

document.getElementById('coverExisting').addEventListener('change', (e) => {
  coverExisting = e.target.checked;
});

// ── Paginate ───────────────────────────────────────────────────────────────

paginateBtn.addEventListener('click', async () => {
  if (!currentFile) return;

  const fromPage   = parseInt(fromPageInput.value) || 1;
  const startNumber = parseInt(startNumInput.value) || 1;

  if (fromPage < 1) {
    PdfTools.showToast('La página de inicio debe ser mayor que 0', 'error');
    return;
  }
  if (startNumber < 1) {
    PdfTools.showToast('El número inicial debe ser mayor que 0', 'error');
    return;
  }

  document.querySelectorAll('.success-banner').forEach(b => b.remove());
  PdfTools.setButtonLoading(paginateBtn, 'Agregando paginación...');

  const formData = new FormData();
  formData.append('pdf',            currentFile);
  formData.append('position',       selectedPos);
  formData.append('start_number',   startNumber);
  formData.append('from_page',      fromPage);
  formData.append('format',         selectedFmt);
  formData.append('font_size',      selectedSize);
  formData.append('cover_existing', coverExisting ? 'true' : 'false');

  try {
    const response = await fetch('/paginar', { method: 'POST', body: formData });

    if (response.ok) {
      const blob = await response.blob();
      PdfTools.downloadBlob(blob, 'paginated_output.pdf');
      PdfTools.showToast('¡Paginación agregada exitosamente!', 'success');
      PdfTools.showDownloadSuccess('paginated_output.pdf', document.querySelector('.merge-button-container'), () => {
        currentFile = null;
        fileInput.value = '';
        configSection.style.display = 'none';
        totalPagesEl.style.display = 'none';
        paginateBtn.disabled = true;
        fromPageInput.value = '1';
        startNumInput.value = '1';
        dropZone.innerHTML = ORIGINAL_DROP_ZONE_HTML;
      });
    } else {
      const msg = await PdfTools.getErrorMessage(response);
      PdfTools.showToast(msg, 'error');
    }
  } catch (e) {
    PdfTools.showToast('Error de conexión: ' + e.message, 'error');
  } finally {
    PdfTools.resetButton(paginateBtn);
  }
});

// Init preview on load
updateFormatPreview();
