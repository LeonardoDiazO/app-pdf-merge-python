const dropZone = document.getElementById('dropZone');
const fileInput = document.getElementById('fileInput');
const compressSection = document.getElementById('compressSection');
const compressButton = document.getElementById('compressButton');
const fileName = document.getElementById('fileName');
const fileSize = document.getElementById('fileSize');

const ORIGINAL_DROP_ZONE_HTML = dropZone.innerHTML;

let currentFile = null;
let selectedLevel = 'media';
let selectedMaxMb = 20; // default matches 'media' level

document.querySelectorAll('.level-card').forEach(card => {
  card.addEventListener('click', () => {
    document.querySelectorAll('.level-card').forEach(c => c.classList.remove('selected'));
    card.classList.add('selected');
    selectedLevel = card.dataset.level;
    selectedMaxMb = parseInt(card.dataset.maxMb || '40', 10);
  });
});

PdfTools.initDropZone(dropZone, fileInput, handleFiles);

function handleFiles(files) {
  const file = files[0];
  const v = PdfTools.validatePdfFile(file, selectedMaxMb);
  if (!v.valid) { PdfTools.showToast(v.error, 'error'); return; }

  currentFile = file;
  fileName.textContent = file.name;
  fileSize.textContent = `Tamaño actual: ${PdfTools.formatFileSize(file.size)}`;
  compressSection.style.display = 'block';
  document.querySelectorAll('.success-banner').forEach(b => b.remove());
  PdfTools.updateDropZoneWithFileInfo(dropZone, file);
}

compressButton.addEventListener('click', async () => {
  if (!currentFile) return;

  const v = PdfTools.validatePdfFile(currentFile, selectedMaxMb);
  if (!v.valid) { PdfTools.showToast(v.error, 'error'); return; }

  document.querySelectorAll('.success-banner').forEach(b => b.remove());
  PdfTools.setButtonLoading(compressButton, 'Comprimiendo...');

  const formData = new FormData();
  formData.append('pdf', currentFile);
  formData.append('level', selectedLevel);

  try {
    const response = await fetch('/comprimir', { method: 'POST', body: formData });

    if (response.ok) {
      const originalSize  = parseInt(response.headers.get('X-Original-Size')  || '0');
      const compressedSize = parseInt(response.headers.get('X-Compressed-Size') || '0');
      const reduction     = parseFloat(response.headers.get('X-Reduction-Percent') || '0');

      const blob = await response.blob();
      const outputName = `compress-${currentFile.name}`;
      PdfTools.downloadBlob(blob, outputName);

      const reductionMsg = reduction > 0
        ? `Reducción: ${reduction}% (${PdfTools.formatFileSize(originalSize)} → ${PdfTools.formatFileSize(compressedSize)})`
        : `Sin cambio significativo (${PdfTools.formatFileSize(compressedSize)})`;

      PdfTools.showToast(reductionMsg, 'success', 6000);
      PdfTools.showDownloadSuccess(outputName, document.querySelector('.merge-button-container'), () => {
        currentFile = null;
        fileInput.value = '';
        compressSection.style.display = 'none';
        dropZone.innerHTML = ORIGINAL_DROP_ZONE_HTML;
        PdfTools.initDropZone(dropZone, fileInput, handleFiles);
      });
    } else {
      const msg = await PdfTools.getErrorMessage(response);
      PdfTools.showToast(msg, 'error');
    }
  } catch (e) {
    PdfTools.showToast('Error de conexión: ' + e.message, 'error');
  } finally {
    PdfTools.resetButton(compressButton);
  }
});

