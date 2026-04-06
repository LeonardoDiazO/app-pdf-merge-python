const dropZone = document.getElementById('dropZone');
const fileInput = document.getElementById('fileInput');
const previewGrid = document.getElementById('previewGrid');
const extractButton = document.getElementById('extractButton');
const previewSection = document.getElementById('previewSection');
const selectAllBtn = document.getElementById('selectAllBtn');

const ORIGINAL_DROP_ZONE_HTML = dropZone.innerHTML;

let currentFile = null;
let pageState = null;

PdfTools.initDropZone(dropZone, fileInput, handleFiles);

async function handleFiles(files) {
  const file = files[0];
  const v = PdfTools.validatePdfFile(file, 20);
  if (!v.valid) { PdfTools.showToast(v.error, 'error'); return; }

  currentFile = file;
  previewSection.style.display = 'block';
  extractButton.disabled = true;
  selectAllBtn.textContent = 'Seleccionar todas';
  document.querySelectorAll('.success-banner').forEach(b => b.remove());
  PdfTools.updateDropZoneWithFileInfo(dropZone, file);

  pageState = await PdfTools.renderPagePreviews(file, previewGrid, {
    actionButton: extractButton,
  });
}

selectAllBtn.addEventListener('click', () => {
  if (!pageState) return;
  PdfTools.handleSelectAll(selectAllBtn, () => pageState, extractButton);
});

document.addEventListener('keydown', (e) => {
  if (e.target.tagName === 'INPUT') return;
  if ((e.key === 'a' || e.key === 'A') && !e.ctrlKey && !e.metaKey) {
    selectAllBtn.click();
  }
  if (e.key === 'Escape' && pageState) {
    const { selectedPages } = pageState;
    previewGrid.querySelectorAll('.page-preview.selected').forEach(el => {
      el.classList.remove('selected');
      el.querySelector('.page-checkbox').checked = false;
      el.setAttribute('aria-checked', 'false');
    });
    selectedPages.clear();
    extractButton.disabled = true;
    selectAllBtn.textContent = 'Seleccionar todas';
  }
});

extractButton.addEventListener('click', async () => {
  if (!currentFile || !pageState || pageState.selectedPages.size === 0) return;

  document.querySelectorAll('.success-banner').forEach(b => b.remove());
  PdfTools.setButtonLoading(extractButton, `Extrayendo ${pageState.selectedPages.size} página(s)...`);

  const formData = new FormData();
  formData.append('pdf', currentFile);
  formData.append('extract_pages', Array.from(pageState.selectedPages).join(','));

  try {
    const response = await fetch('/extraer', { method: 'POST', body: formData });

    if (response.ok) {
      const blob = await response.blob();
      PdfTools.downloadBlob(blob, 'extracted_output.pdf');
      PdfTools.showToast('¡Páginas extraídas exitosamente!', 'success');
      PdfTools.showDownloadSuccess('extracted_output.pdf', document.querySelector('.merge-button-container'), () => {
        currentFile = null;
        pageState = null;
        previewGrid.innerHTML = '';
        fileInput.value = '';
        previewSection.style.display = 'none';
        selectAllBtn.textContent = 'Seleccionar todas';
        dropZone.innerHTML = ORIGINAL_DROP_ZONE_HTML;
      });
    } else {
      const msg = await PdfTools.getErrorMessage(response);
      PdfTools.showToast(msg, 'error');
    }
  } catch (e) {
    PdfTools.showToast('Error de conexión: ' + e.message, 'error');
  } finally {
    PdfTools.resetButton(extractButton);
    if (pageState) extractButton.disabled = pageState.selectedPages.size === 0;
  }
});
