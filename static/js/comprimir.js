const dropZone = document.getElementById('dropZone');
const fileInput = document.getElementById('fileInput');
const compressSection = document.getElementById('compressSection');
const compressButton = document.getElementById('compressButton');
const fileName = document.getElementById('fileName');
const fileSize = document.getElementById('fileSize');

const ORIGINAL_DROP_ZONE_HTML = dropZone.innerHTML;

let currentFile = null;
let selectedLevel = 'media';

document.querySelectorAll('.level-card').forEach(card => {
  card.addEventListener('click', () => {
    document.querySelectorAll('.level-card').forEach(c => c.classList.remove('selected'));
    card.classList.add('selected');
    selectedLevel = card.dataset.level;
  });
});

PdfTools.initDropZone(dropZone, fileInput, handleFiles);

function handleFiles(files) {
  const file = files[0];
  const v = PdfTools.validatePdfFile(file, 20);
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
      PdfTools.downloadBlob(blob, 'compressed_output.pdf');

      const reductionText = reduction > 0
        ? `Se redujo un <strong>${reduction}%</strong> (${PdfTools.formatFileSize(originalSize)} → ${PdfTools.formatFileSize(compressedSize)})`
        : `Tamaño final: ${PdfTools.formatFileSize(compressedSize)} (sin cambio significativo)`;

      PdfTools.showToast('¡PDF comprimido exitosamente!', 'success');
      _showCompressionSuccess(reductionText);
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

function _showCompressionSuccess(reductionText) {
  document.querySelectorAll('.success-banner').forEach(b => b.remove());

  const banner = document.createElement('div');
  banner.className = 'success-banner';
  banner.innerHTML = `
    <div class="success-banner-icon">✅</div>
    <div class="success-banner-text">
      <div class="success-banner-title">¡Archivo generado exitosamente!</div>
      <div class="success-banner-filename">${reductionText}</div>
    </div>
    <button class="success-banner-action" type="button">Comprimir otro</button>
  `;
  banner.querySelector('button').addEventListener('click', () => {
    banner.remove();
    currentFile = null;
    fileInput.value = '';
    compressSection.style.display = 'none';
    dropZone.innerHTML = ORIGINAL_DROP_ZONE_HTML;
    PdfTools.initDropZone(dropZone, fileInput, handleFiles);
  });

  document.querySelector('.merge-button-container').after(banner);
}
