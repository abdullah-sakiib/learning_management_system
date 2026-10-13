const viewerTitle = document.getElementById('viewer-title');
  const viewerLabel = document.getElementById('viewer-label');
  const viewerMedia = document.getElementById('viewer-media');
  const viewerDescription = document.getElementById('viewer-description');

  function buildViewerContent(resource) {
    const title = resource.dataset.title || 'Untitled resource';
    const type = resource.dataset.type || '';
    const label = resource.dataset.label || 'Resource';
    const description = resource.dataset.description || 'No description provided for this resource.';
    const videoUrl = resource.dataset.videoUrl;
    const fileUrl = resource.dataset.fileUrl;
    const externalUrl = resource.dataset.externalUrl;

    viewerTitle.textContent = title;
    viewerLabel.textContent = label;
    viewerDescription.textContent = description;

    if (type === 'video' && videoUrl) {
      viewerMedia.innerHTML = `<video controls class="w-full max-h-[520px] bg-black object-contain"><source src="${videoUrl}"></video>`;
      return;
    }

    if (type === 'file' && fileUrl) {
      viewerMedia.innerHTML = `<div class="text-center p-6"><i class="ri-file-download-line text-4xl text-slate-400"></i><p class="mt-3 text-sm text-slate-600">This resource is a downloadable file.</p><a href="${fileUrl}" class="inline-flex mt-3 px-4 py-2 rounded-lg bg-indigo-600 text-white text-sm font-semibold hover:bg-indigo-700 transition">Download file</a></div>`;
      return;
    }

    if (type === 'link' && externalUrl) {
      viewerMedia.innerHTML = `<div class="text-center p-6"><i class="ri-link text-4xl text-slate-400"></i><p class="mt-3 text-sm text-slate-600">This resource is an external link.</p><a href="${externalUrl}" target="_blank" rel="noopener" class="inline-flex mt-3 px-4 py-2 rounded-lg bg-indigo-600 text-white text-sm font-semibold hover:bg-indigo-700 transition">Open link</a></div>`;
      return;
    }

    viewerMedia.innerHTML = '<p class="text-sm text-slate-500">No preview available for this resource.</p>';
  }

  document.querySelectorAll('.resource-item').forEach((item) => {
    item.addEventListener('click', () => buildViewerContent(item));
  });
