const dropZone = document.getElementById('dropZone');
const fileInput = document.getElementById('fileInput');
const previewGrid = document.getElementById('previewGrid');
const rotateButton = document.getElementById('rotateButton');
const rotationSection = document.getElementById('rotationSection');
const selectAllBtn = document.getElementById('selectAllBtn');

const ORIGINAL_DROP_ZONE_HTML = dropZone.innerHTML;

let currentFile = null;
let pageState = null;
let selectedRotation = 180;

document.querySelectorAll('.rotate-option').forEach(option => {
  option.addEventListener('click', () => {
    document.querySelectorAll('.rotate-option').forEach(o => o.classList.remove('selected'));
    option.classList.add('selected');
    selectedRotation = parseInt(option.dataset.rotation);
    updatePreviewRotations();
  });
});

PdfTools.initDropZone(dropZone, fileInput, handleFiles);

async function handleFiles(files) {
  const file = files[0];
  const v = PdfTools.validatePdfFile(file, 20);
  if (!v.valid) { PdfTools.showToast(v.error, 'error'); return; }

  currentFile = file;
  rotationSection.style.display = 'block';
  rotateButton.disabled = true;
  selectAllBtn.textContent = 'Seleccionar todas';
  document.querySelectorAll('.success-banner').forEach(b => b.remove());
  PdfTools.updateDropZoneWithFileInfo(dropZone, file);

  pageState = await PdfTools.renderPagePreviews(file, previewGrid, {
    actionButton: rotateButton,
    onToggle: () => updatePreviewRotations(),
  });
}

selectAllBtn.addEventListener('click', () => {
  if (!pageState) return;
  PdfTools.handleSelectAll(selectAllBtn, () => pageState, rotateButton);
  updatePreviewRotations();
});

function updatePreviewRotations() {
  previewGrid.querySelectorAll('.page-preview').forEach(preview => {
    preview.classList.remove('rotate-90', 'rotate-180', 'rotate-270');
    if (preview.classList.contains('selected')) {
      preview.classList.add(`rotate-${selectedRotation}`);
    }
  });
}

document.addEventListener('keydown', (e) => {
  if (e.target.tagName === 'INPUT') return;
  if ((e.key === 'a' || e.key === 'A') && !e.ctrlKey && !e.metaKey) {
    selectAllBtn.click();
  }
  if (e.key === 'Escape' && pageState) {
    const { selectedPages, checkboxes } = pageState;
    previewGrid.querySelectorAll('.page-preview.selected').forEach(el => {
      el.classList.remove('selected', 'rotate-90', 'rotate-180', 'rotate-270');
      el.querySelector('.page-checkbox').checked = false;
      el.setAttribute('aria-checked', 'false');
    });
    selectedPages.clear();
    rotateButton.disabled = true;
    selectAllBtn.textContent = 'Seleccionar todas';
  }
});

rotateButton.addEventListener('click', async () => {
  if (!currentFile || !pageState || pageState.selectedPages.size === 0) return;

  document.querySelectorAll('.success-banner').forEach(b => b.remove());
  PdfTools.setButtonLoading(rotateButton, `Rotando ${pageState.selectedPages.size} página(s)...`);

  const formData = new FormData();
  formData.append('pdf', currentFile);
  formData.append('pages', Array.from(pageState.selectedPages).join(','));
  formData.append('rotation', selectedRotation);

  try {
    const response = await fetch('/rotar', { method: 'POST', body: formData });

    if (response.ok) {
      const blob = await response.blob();
      PdfTools.downloadBlob(blob, 'rotated_output.pdf');
      PdfTools.showToast('¡Páginas rotadas exitosamente!', 'success');
      PdfTools.showDownloadSuccess('rotated_output.pdf', document.querySelector('.merge-button-container'), () => {
        currentFile = null;
        pageState = null;
        previewGrid.innerHTML = '';
        fileInput.value = '';
        rotationSection.style.display = 'none';
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
    PdfTools.resetButton(rotateButton);
    if (pageState) rotateButton.disabled = pageState.selectedPages.size === 0;
  }
});
