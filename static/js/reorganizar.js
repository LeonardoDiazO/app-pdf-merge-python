const dropZone = document.getElementById('dropZone');
const fileInput = document.getElementById('fileInput');
const pagesGrid = document.getElementById('pagesGrid');
const reorderButton = document.getElementById('reorderButton');
const previewSection = document.getElementById('previewSection');
const resetBtn = document.getElementById('resetBtn');

const ORIGINAL_DROP_ZONE_HTML = dropZone.innerHTML;
const WORKER_SRC = 'https://cdnjs.cloudflare.com/ajax/libs/pdf.js/3.4.120/pdf.worker.min.js';

let currentFile = null;
let totalPages = 0;

PdfTools.initDropZone(dropZone, fileInput, handleFiles);

async function handleFiles(files) {
  const file = files[0];
  const v = PdfTools.validatePdfFile(file, 20);
  if (!v.valid) { PdfTools.showToast(v.error, 'error'); return; }

  currentFile = file;
  document.querySelectorAll('.success-banner').forEach(b => b.remove());
  PdfTools.updateDropZoneWithFileInfo(dropZone, file);
  previewSection.style.display = 'block';
  reorderButton.disabled = true;

  pagesGrid.innerHTML = `
    <div style="grid-column:1/-1;text-align:center;padding:2rem;color:var(--text-secondary)">
      <span class="btn-spinner" style="border-color:rgba(0,0,0,.15);border-top-color:#9ca3af;width:28px;height:28px;margin-bottom:.75rem;display:inline-block"></span>
      <div>Cargando páginas...</div>
    </div>
  `;

  pdfjsLib.GlobalWorkerOptions.workerSrc = WORKER_SRC;

  let pdf;
  try {
    const arrayBuffer = await file.arrayBuffer();
    pdf = await pdfjsLib.getDocument(arrayBuffer).promise;
  } catch (e) {
    pagesGrid.innerHTML = '';
    previewSection.style.display = 'none';
    PdfTools.showToast('No se pudo leer el PDF. ¿Está protegido con contraseña?', 'error');
    return;
  }

  totalPages = pdf.numPages;
  pagesGrid.innerHTML = '';

  for (let i = 1; i <= totalPages; i++) {
    const page = await pdf.getPage(i);
    const viewport = page.getViewport({ scale: 0.7 });
    const canvas = document.createElement('canvas');
    canvas.width = viewport.width;
    canvas.height = viewport.height;
    await page.render({ canvasContext: canvas.getContext('2d'), viewport }).promise;
    pagesGrid.appendChild(createPageCard(canvas, i - 1, i));
  }

  if (totalPages < 2) {
    PdfTools.showToast('Este PDF tiene una sola página, no hay nada que reorganizar.', 'warning');
  }
  reorderButton.disabled = totalPages < 2;
}

function createPageCard(canvas, originalIndex, pageNumber) {
  const card = document.createElement('div');
  card.className = 'page-card';
  card.draggable = true;
  card.dataset.originalIndex = originalIndex;

  const posLabel = document.createElement('div');
  posLabel.className = 'page-position-label';
  posLabel.textContent = `Posición ${pageNumber}`;

  const originLabel = document.createElement('div');
  originLabel.className = 'page-origin-label';
  originLabel.textContent = `Pág. original: ${pageNumber}`;

  card.appendChild(posLabel);
  card.appendChild(canvas);
  card.appendChild(originLabel);

  card.addEventListener('dragstart', (e) => {
    e.dataTransfer.effectAllowed = 'move';
    e.dataTransfer.setData('text/plain', '');
    card.classList.add('dragging');
  });

  card.addEventListener('dragend', () => {
    card.classList.remove('dragging');
    pagesGrid.querySelectorAll('.page-card').forEach(c => c.classList.remove('drag-over'));
    updatePositionLabels();
  });

  card.addEventListener('dragover', (e) => {
    e.preventDefault();
    const dragging = pagesGrid.querySelector('.dragging');
    if (!dragging || dragging === card) return;
    card.classList.add('drag-over');
    const rect = card.getBoundingClientRect();
    if (e.clientY < rect.top + rect.height / 2) pagesGrid.insertBefore(dragging, card);
    else pagesGrid.insertBefore(dragging, card.nextSibling);
  });

  card.addEventListener('dragleave', () => card.classList.remove('drag-over'));
  card.addEventListener('drop', (e) => { e.preventDefault(); card.classList.remove('drag-over'); });

  return card;
}

function updatePositionLabels() {
  pagesGrid.querySelectorAll('.page-card').forEach((card, i) => {
    card.querySelector('.page-position-label').textContent = `Posición ${i + 1}`;
  });
}

function getCurrentOrder() {
  return Array.from(pagesGrid.querySelectorAll('.page-card')).map(
    card => parseInt(card.dataset.originalIndex)
  );
}

resetBtn.addEventListener('click', () => {
  if (!currentFile) return;
  const cards = Array.from(pagesGrid.querySelectorAll('.page-card'));
  cards.sort((a, b) => parseInt(a.dataset.originalIndex) - parseInt(b.dataset.originalIndex));
  cards.forEach(card => pagesGrid.appendChild(card));
  updatePositionLabels();
  PdfTools.showToast('Orden original restaurado', 'info');
});

reorderButton.addEventListener('click', async () => {
  if (!currentFile || totalPages < 2) return;

  const newOrder = getCurrentOrder();

  document.querySelectorAll('.success-banner').forEach(b => b.remove());
  PdfTools.setButtonLoading(reorderButton, 'Reorganizando páginas...');

  const formData = new FormData();
  formData.append('pdf', currentFile);
  formData.append('page_order', newOrder.join(','));

  try {
    const response = await fetch('/reorganizar', { method: 'POST', body: formData });

    if (response.ok) {
      const blob = await response.blob();
      const outputName = `reorder-${currentFile.name}`;
      PdfTools.downloadBlob(blob, outputName);
      PdfTools.showToast('¡Páginas reorganizadas exitosamente!', 'success');
      PdfTools.showDownloadSuccess(outputName, document.querySelector('.merge-button-container'), () => {
        currentFile = null;
        totalPages = 0;
        pagesGrid.innerHTML = '';
        fileInput.value = '';
        previewSection.style.display = 'none';
        dropZone.innerHTML = ORIGINAL_DROP_ZONE_HTML;
      });
    } else {
      const msg = await PdfTools.getErrorMessage(response);
      PdfTools.showToast(msg, 'error');
    }
  } catch (e) {
    PdfTools.showToast('Error de conexión: ' + e.message, 'error');
  } finally {
    PdfTools.resetButton(reorderButton);
    reorderButton.disabled = totalPages < 2;
  }
});
