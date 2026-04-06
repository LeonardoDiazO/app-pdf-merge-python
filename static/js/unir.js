const dropZone = document.getElementById('dropZone');
const fileInput = document.getElementById('fileInput');
const pdfFilesContainer = document.getElementById('pdfFilesContainer');
const mergeButton = document.getElementById('mergeButton');
const mainContainer = document.querySelector('.main-container');

const MAX_SIZE_MB = 20;
let filesArray = [];

PdfTools.initDropZone(dropZone, fileInput, handleFiles);

function handleFiles(files) {
  const newFiles = Array.from(files).filter(f => {
    const v = PdfTools.validatePdfFile(f, MAX_SIZE_MB);
    if (!v.valid) { PdfTools.showToast(`${f.name}: ${v.error}`, 'error'); return false; }
    return true;
  });
  if (newFiles.length === 0) return;
  filesArray = [...filesArray, ...newFiles];
  renderFiles();
}

function renderFiles() {
  pdfFilesContainer.innerHTML = '';
  mergeButton.disabled = filesArray.length < 2;
  filesArray.forEach((file, index) => {
    pdfFilesContainer.appendChild(createPdfCard(file, index));
  });
}

function createPdfCard(file, index) {
  const card = document.createElement('div');
  card.className = 'pdf-card';
  card.draggable = true;
  card.dataset.index = index;

  card.innerHTML = `
    <div class="pdf-icon"></div>
    <div class="pdf-info">
      <div class="pdf-filename" title="${file.name}">${file.name}</div>
      <div class="pdf-size">${PdfTools.formatFileSize(file.size)}</div>
    </div>
    <div class="reorder-controls">
      <button class="reorder-btn" onclick="moveFile(${index}, -1)" ${index === 0 ? 'disabled' : ''} title="Subir">↑</button>
      <button class="reorder-btn" onclick="moveFile(${index}, 1)" ${index === filesArray.length - 1 ? 'disabled' : ''} title="Bajar">↓</button>
      <button class="reorder-btn" onclick="removeFile(${index})" title="Eliminar" style="color:var(--pdf-red)">✕</button>
    </div>
  `;

  card.addEventListener('dragstart', (e) => {
    e.dataTransfer.effectAllowed = 'move';
    e.dataTransfer.setData('text/plain', index);
    card.classList.add('dragging');
  });
  card.addEventListener('dragend', () => card.classList.remove('dragging'));
  card.addEventListener('dragover', (e) => {
    e.preventDefault();
    const dragging = document.querySelector('.dragging');
    if (!dragging || dragging === card) return;
    const rect = card.getBoundingClientRect();
    if (e.clientY < rect.top + rect.height / 2) card.parentNode.insertBefore(dragging, card);
    else card.parentNode.insertBefore(dragging, card.nextSibling);
  });
  card.addEventListener('drop', (e) => { e.preventDefault(); updateFilesOrder(); });

  return card;
}

function moveFile(index, direction) {
  const newIndex = index + direction;
  if (newIndex < 0 || newIndex >= filesArray.length) return;
  [filesArray[index], filesArray[newIndex]] = [filesArray[newIndex], filesArray[index]];
  renderFiles();
}

function removeFile(index) {
  filesArray.splice(index, 1);
  renderFiles();
}

function updateFilesOrder() {
  const cards = Array.from(pdfFilesContainer.children);
  const newOrder = cards.map(card => parseInt(card.dataset.index));
  filesArray = newOrder.map(i => filesArray[i]);
  renderFiles();
}

mergeButton.addEventListener('click', async () => {
  if (filesArray.length < 2) return;

  document.querySelectorAll('.success-banner').forEach(b => b.remove());
  PdfTools.setButtonLoading(mergeButton, `Uniendo ${filesArray.length} archivos...`);

  const formData = new FormData();
  filesArray.forEach(file => formData.append('pdfs', file));
  formData.append('order', filesArray.map((_, i) => i).join(','));

  try {
    const response = await fetch('/unir', { method: 'POST', body: formData });

    if (response.ok) {
      const blob = await response.blob();
      const outputName = `merge-${filesArray[0].name}`;
      PdfTools.downloadBlob(blob, outputName);
      PdfTools.showToast('¡PDFs unidos exitosamente!', 'success');
      PdfTools.showDownloadSuccess(outputName, document.querySelector('.merge-button-container'), () => {
        filesArray = [];
        fileInput.value = '';
        renderFiles();
      });
    } else {
      const msg = await PdfTools.getErrorMessage(response);
      PdfTools.showToast(msg, 'error');
    }
  } catch (e) {
    PdfTools.showToast('Error de conexión: ' + e.message, 'error');
  } finally {
    PdfTools.resetButton(mergeButton);
    mergeButton.disabled = filesArray.length < 2;
  }
});
