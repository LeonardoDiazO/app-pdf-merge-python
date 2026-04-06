const dropZone = document.getElementById('dropZone');
const fileInput = document.getElementById('fileInput');
const imagesContainer = document.getElementById('imagesContainer');
const convertButton = document.getElementById('convertButton');

const MAX_SIZE_MB = 20;
const MAX_IMAGES = 20;
const ALLOWED_EXTS = ['.jpg', '.jpeg', '.png', '.webp', '.gif', '.bmp'];
const ALLOWED_MIME = ['image/jpeg', 'image/png', 'image/webp', 'image/gif', 'image/bmp'];

let imagesArray = [];

PdfTools.initDropZone(dropZone, fileInput, handleFiles);

function validateImageFile(file) {
  if (!file) return { valid: false, error: 'No se seleccionó ningún archivo' };
  const ext = '.' + file.name.split('.').pop().toLowerCase();
  if (!ALLOWED_MIME.includes(file.type) && !ALLOWED_EXTS.includes(ext)) {
    return { valid: false, error: `"${file.name}": formato no soportado. Use JPG, PNG, WEBP, GIF o BMP` };
  }
  if (file.size === 0) return { valid: false, error: `"${file.name}": el archivo está vacío` };
  if (file.size > MAX_SIZE_MB * 1024 * 1024) {
    return { valid: false, error: `"${file.name}": supera el límite de ${MAX_SIZE_MB} MB (${PdfTools.formatFileSize(file.size)})` };
  }
  return { valid: true };
}

function handleFiles(files) {
  const remaining = MAX_IMAGES - imagesArray.length;
  if (remaining <= 0) {
    PdfTools.showToast(`Máximo ${MAX_IMAGES} imágenes permitidas`, 'warning');
    return;
  }

  const candidates = Array.from(files).slice(0, remaining);
  if (Array.from(files).length > remaining) {
    PdfTools.showToast(`Solo se añadirán las primeras ${remaining} imágenes (límite: ${MAX_IMAGES})`, 'warning');
  }

  const newFiles = candidates.filter(f => {
    const v = validateImageFile(f);
    if (!v.valid) { PdfTools.showToast(v.error, 'error'); return false; }
    return true;
  });

  if (newFiles.length === 0) return;
  imagesArray = [...imagesArray, ...newFiles];
  renderImages();
}

function renderImages() {
  imagesContainer.innerHTML = '';
  convertButton.disabled = imagesArray.length === 0;
  imagesArray.forEach((file, index) => {
    const card = createImageCard(file, index);
    imagesContainer.appendChild(card);
  });
}

function createImageCard(file, index) {
  const card = document.createElement('div');
  card.className = 'image-card';
  card.draggable = true;
  card.dataset.index = index;

  const thumbWrap = document.createElement('div');
  thumbWrap.className = 'image-thumb-wrap';

  const img = document.createElement('img');
  img.className = 'image-thumb';
  img.alt = file.name;

  const reader = new FileReader();
  reader.onload = (e) => { img.src = e.target.result; };
  reader.readAsDataURL(file);

  thumbWrap.appendChild(img);

  const info = document.createElement('div');
  info.className = 'pdf-info';
  info.innerHTML = `
    <div class="pdf-filename" title="${file.name}">${file.name}</div>
    <div class="pdf-size">${PdfTools.formatFileSize(file.size)}</div>
  `;

  const controls = document.createElement('div');
  controls.className = 'reorder-controls';

  const upBtn = document.createElement('button');
  upBtn.className = 'reorder-btn';
  upBtn.title = 'Subir';
  upBtn.textContent = '↑';
  upBtn.disabled = index === 0;
  upBtn.addEventListener('click', () => moveImage(index, -1));

  const downBtn = document.createElement('button');
  downBtn.className = 'reorder-btn';
  downBtn.title = 'Bajar';
  downBtn.textContent = '↓';
  downBtn.disabled = index === imagesArray.length - 1;
  downBtn.addEventListener('click', () => moveImage(index, 1));

  const removeBtn = document.createElement('button');
  removeBtn.className = 'reorder-btn';
  removeBtn.title = 'Eliminar';
  removeBtn.textContent = '✕';
  removeBtn.style.color = 'var(--pdf-red)';
  removeBtn.addEventListener('click', () => removeImage(index));

  controls.appendChild(upBtn);
  controls.appendChild(downBtn);
  controls.appendChild(removeBtn);

  card.appendChild(thumbWrap);
  card.appendChild(info);
  card.appendChild(controls);

  card.addEventListener('dragstart', (e) => {
    e.dataTransfer.effectAllowed = 'move';
    e.dataTransfer.setData('text/plain', index);
    card.classList.add('dragging');
  });
  card.addEventListener('dragend', () => card.classList.remove('dragging'));
  card.addEventListener('dragover', (e) => {
    e.preventDefault();
    const dragging = imagesContainer.querySelector('.image-card.dragging');
    if (!dragging || dragging === card) return;
    const rect = card.getBoundingClientRect();
    if (e.clientY < rect.top + rect.height / 2) imagesContainer.insertBefore(dragging, card);
    else imagesContainer.insertBefore(dragging, card.nextSibling);
  });
  card.addEventListener('drop', (e) => { e.preventDefault(); syncOrderFromDOM(); });

  return card;
}

function moveImage(index, direction) {
  const newIndex = index + direction;
  if (newIndex < 0 || newIndex >= imagesArray.length) return;
  [imagesArray[index], imagesArray[newIndex]] = [imagesArray[newIndex], imagesArray[index]];
  renderImages();
}

function removeImage(index) {
  imagesArray.splice(index, 1);
  renderImages();
}

function syncOrderFromDOM() {
  const cards = Array.from(imagesContainer.children);
  const newOrder = cards.map(card => parseInt(card.dataset.index));
  imagesArray = newOrder.map(i => imagesArray[i]);
  renderImages();
}

convertButton.addEventListener('click', async () => {
  if (imagesArray.length === 0) return;

  document.querySelectorAll('.success-banner').forEach(b => b.remove());
  PdfTools.setButtonLoading(convertButton, `Convirtiendo ${imagesArray.length} imagen(es)...`);

  const formData = new FormData();
  imagesArray.forEach(file => formData.append('images', file));
  formData.append('order', imagesArray.map((_, i) => i).join(','));

  try {
    const response = await fetch('/imagenes', { method: 'POST', body: formData });

    if (response.ok) {
      const blob = await response.blob();
      PdfTools.downloadBlob(blob, 'images_output.pdf');
      PdfTools.showToast('¡Imágenes convertidas exitosamente!', 'success');
      PdfTools.showDownloadSuccess('images_output.pdf', document.querySelector('.merge-button-container'), () => {
        imagesArray = [];
        fileInput.value = '';
        renderImages();
      });
    } else {
      const msg = await PdfTools.getErrorMessage(response);
      PdfTools.showToast(msg, 'error');
    }
  } catch (e) {
    PdfTools.showToast('Error de conexión: ' + e.message, 'error');
  } finally {
    PdfTools.resetButton(convertButton);
    convertButton.disabled = imagesArray.length === 0;
  }
});
