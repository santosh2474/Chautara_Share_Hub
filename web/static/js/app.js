/**
 * Antigravity Network Share & Vault - Client-side Reactive Application
 * Fully self-contained, 100% offline-ready.
 */

(function () {
  'use strict';

  // Application State
  const state = {
    serverInfo: null,
    roots: [],
    currentRoot: 'public',
    currentPath: '',
    currentFilter: 'all',
    searchQuery: '',
    items: [],
    viewMode: localStorage.getItem('agy_view_mode') || 'grid',
    isDark: localStorage.getItem('agy_theme') !== 'light',
    vaultToken: '', // Ephemeral: resets whenever user navigates away or refreshes
    isReadOnly: false,
  };

  // DOM Elements Cache
  const el = {
    body: document.body,
    serverNameTitle: document.getElementById('serverNameTitle'),
    serverIpBadge: document.getElementById('serverIpBadge'),
    themeToggleBtn: document.getElementById('themeToggleBtn'),
    themeIconSun: document.getElementById('themeIconSun'),
    themeIconMoon: document.getElementById('themeIconMoon'),
    showQrBtn: document.getElementById('showQrBtn'),
    storageTabsList: document.getElementById('storageTabsList'),
    breadcrumbsNav: document.getElementById('breadcrumbsNav'),
    lockVaultBtn: document.getElementById('lockVaultBtn'),
    uploadFilesBtn: document.getElementById('uploadFilesBtn'),
    uploadFolderBtn: document.getElementById('uploadFolderBtn'),
    filePickerInput: document.getElementById('filePickerInput'),
    photoPickerInput: document.getElementById('photoPickerInput'),
    folderPickerInput: document.getElementById('folderPickerInput'),
    quickPickAnyBtn: document.getElementById('quickPickAnyBtn'),
    quickPickFolderBtn: document.getElementById('quickPickFolderBtn'),
    quickPickMediaBtn: document.getElementById('quickPickMediaBtn'),
    floatingUploadBtn: document.getElementById('floatingUploadBtn'),
    newFolderBtn: document.getElementById('newFolderBtn'),
    downloadZipBtn: document.getElementById('downloadZipBtn'),
    refreshBtn: document.getElementById('refreshBtn'),
    viewGridBtn: document.getElementById('viewGridBtn'),
    viewListBtn: document.getElementById('viewListBtn'),
    searchInput: document.getElementById('searchInput'),
    clearSearchBtn: document.getElementById('clearSearchBtn'),
    filterChips: document.getElementById('filterChips'),
    dropzone: document.getElementById('dropzone'),
    uploadProgressContainer: document.getElementById('uploadProgressContainer'),
    uploadStatusText: document.getElementById('uploadStatusText'),
    uploadProgressBarFill: document.getElementById('uploadProgressBarFill'),
    uploadList: document.getElementById('uploadList'),
    dismissUploadsBtn: document.getElementById('dismissUploadsBtn'),
    filesContainer: document.getElementById('filesContainer'),
    emptyState: document.getElementById('emptyState'),
    vaultLockedState: document.getElementById('vaultLockedState'),
    vaultUnlockForm: document.getElementById('vaultUnlockForm'),
    vaultPasswordInput: document.getElementById('vaultPasswordInput'),
    togglePasswordVisibility: document.getElementById('togglePasswordVisibility'),
    vaultErrorMsg: document.getElementById('vaultErrorMsg'),
    previewModal: document.getElementById('previewModal'),
    previewFilename: document.getElementById('previewFilename'),
    previewFilesize: document.getElementById('previewFilesize'),
    previewDownloadDirectBtn: document.getElementById('previewDownloadDirectBtn'),
    closePreviewBtn: document.getElementById('closePreviewBtn'),
    previewBody: document.getElementById('previewBody'),
    qrModal: document.getElementById('qrModal'),
    qrCodeModalImg: document.getElementById('qrCodeModalImg'),
    serverUrlInput: document.getElementById('serverUrlInput'),
    copyUrlBtn: document.getElementById('copyUrlBtn'),
    closeQrBtn: document.getElementById('closeQrBtn'),
    newFolderModal: document.getElementById('newFolderModal'),
    newFolderForm: document.getElementById('newFolderForm'),
    folderNameInput: document.getElementById('folderNameInput'),
    cancelFolderBtn: document.getElementById('cancelFolderBtn'),
    closeFolderModalBtn: document.getElementById('closeFolderModalBtn'),
    shareDriveModal: document.getElementById('shareDriveModal'),
    shareDriveFilename: document.getElementById('shareDriveFilename'),
    shareDriveSelect: document.getElementById('shareDriveSelect'),
    cancelShareDriveBtn: document.getElementById('cancelShareDriveBtn'),
    confirmShareDriveBtn: document.getElementById('confirmShareDriveBtn'),
    closeShareDriveModalBtn: document.getElementById('closeShareDriveModalBtn'),
    toastContainer: document.getElementById('toastContainer'),
  };

  // Detect whether the browser supports native whole-folder selection
  // (Chrome, Edge, Firefox; older Safari/Android may not).
  const folderPickSupported =
    'webkitdirectory' in document.createElement('input') ||
    'directory' in document.createElement('input');

  // Open the folder picker. The input must be in pure directory mode:
  // some engines treat a `webkitdirectory` + `multiple` combo as a plain
  // multi-file dialog. Always re-assert attribute AND property before
  // clicking so engines that only respect one of them still get folder mode.
  function openFolderPicker() {
    const input = el.folderPickerInput;
    input.multiple = false;
    input.webkitdirectory = true;
    input.directory = true;
    input.setAttribute('dir', '');
    input.setAttribute('webkitdirectory', '');
    input.setAttribute('directory', '');
    if (folderPickSupported) {
      input.click();
    } else {
      el.filePickerInput.click();
      showToast('This browser cannot select folders. Choose multiple files instead.');
    }
  }

  // SVG Icon Templates
  const ICONS = {
    folder: '<svg viewBox="0 0 24 24" width="24" height="24" fill="none" stroke="currentColor" stroke-width="2"><path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"></path></svg>',
    image: '<svg viewBox="0 0 24 24" width="24" height="24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="3" width="18" height="18" rx="2" ry="2"></rect><circle cx="8.5" cy="8.5" r="1.5"></circle><polyline points="21 15 16 10 5 21"></polyline></svg>',
    video: '<svg viewBox="0 0 24 24" width="24" height="24" fill="none" stroke="currentColor" stroke-width="2"><polygon points="23 7 16 12 23 17 23 7"></polygon><rect x="1" y="5" width="15" height="14" rx="2" ry="2"></rect></svg>',
    audio: '<svg viewBox="0 0 24 24" width="24" height="24" fill="none" stroke="currentColor" stroke-width="2"><path d="M9 18V5l12-2v13"></path><circle cx="6" cy="18" r="3"></circle><circle cx="18" cy="16" r="3"></circle></svg>',
    document: '<svg viewBox="0 0 24 24" width="24" height="24" fill="none" stroke="currentColor" stroke-width="2"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path><polyline points="14 2 14 8 20 8"></polyline><line x1="16" y1="13" x2="8" y2="13"></line><line x1="16" y1="17" x2="8" y2="17"></line><polyline points="10 9 9 9 8 9"></polyline></svg>',
    archive: '<svg viewBox="0 0 24 24" width="24" height="24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="21 8 21 21 3 21 3 8"></polyline><rect x="1" y="3" width="22" height="5"></rect><line x1="10" y1="12" x2="14" y2="12"></line></svg>',
    code: '<svg viewBox="0 0 24 24" width="24" height="24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="16 18 22 12 16 6"></polyline><polyline points="8 6 2 12 8 18"></polyline></svg>',
    other: '<svg viewBox="0 0 24 24" width="24" height="24" fill="none" stroke="currentColor" stroke-width="2"><path d="M13 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V9z"></path><polyline points="13 2 13 9 20 9"></polyline></svg>',
    usb: '<svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2"><rect x="7" y="2" width="10" height="7" rx="1"></rect><rect x="5" y="9" width="14" height="13" rx="2"></rect><line x1="10" y1="5" x2="10" y2="5.01"></line><line x1="14" y1="5" x2="14" y2="5.01"></line></svg>',
    shieldLock: '<svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="11" width="18" height="11" rx="2"></rect><path d="M7 11V7a5 5 0 0 1 10 0v4"></path></svg>',
    folderShared: '<svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2"><path d="M4 20h16a2 2 0 0 0 2-2V8a2 2 0 0 0-2-2h-7.93a2 2 0 0 1-1.66-.9l-.82-1.2A2 2 0 0 0 7.93 3H4a2 2 0 0 0-2 2v13c0 1.1.9 2 2 2Z"></path></svg>',
    download: '<svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path><polyline points="7 10 12 15 17 10"></polyline><line x1="12" y1="15" x2="12" y2="3"></line></svg>',
    eye: '<svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"></path><circle cx="12" cy="12" r="3"></circle></svg>',
    shareDrive: '<svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2"><path d="M4 12v8a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-8"></path><polyline points="16 6 12 2 8 6"></polyline><line x1="12" y1="2" x2="12" y2="15"></line></svg>',
    trash: '<svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2"><polyline points="3 6 5 6 21 6"></polyline><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path></svg>',
  };

  // Toast Notification Helper
  function showToast(message, duration = 3000) {
    const toast = document.createElement('div');
    toast.className = 'toast';
    toast.textContent = message;
    el.toastContainer.appendChild(toast);
    setTimeout(() => {
      toast.style.opacity = '0';
      toast.style.transition = 'opacity 0.3s';
      setTimeout(() => toast.remove(), 300);
    }, duration);
  }

  // Escape untrusted text before injecting into innerHTML
  function escapeHtml(value) {
    const div = document.createElement('div');
    div.textContent = value == null ? '' : String(value);
    return div.innerHTML;
  }

  // Theme Initializer
  function applyTheme() {
    if (state.isDark) {
      el.body.classList.remove('light-theme');
      el.body.classList.add('dark-theme');
      el.themeIconSun.classList.remove('hidden');
      el.themeIconMoon.classList.add('hidden');
    } else {
      el.body.classList.remove('dark-theme');
      el.body.classList.add('light-theme');
      el.themeIconSun.classList.add('hidden');
      el.themeIconMoon.classList.remove('hidden');
    }
  }

  // Fetch Server Status
  async function loadServerStatus() {
    try {
      const res = await fetch('/api/status');
      if (!res.ok) throw new Error();
      const data = await res.json();
      state.serverInfo = data;
      el.serverNameTitle.textContent = data.server_name;
      el.serverIpBadge.textContent = `${data.best_ip}:${data.port}`;
      el.qrCodeModalImg.src = data.qr_code;
      el.serverUrlInput.value = `http://${data.best_ip}:${data.port}`;
    } catch (e) {
      el.serverIpBadge.textContent = 'Offline / Error';
    }
  }

  // Fetch Storage Roots (Public, Vault, USB)
  async function loadStorageRoots() {
    try {
      const headers = {};
      if (state.vaultToken) headers['X-Vault-Token'] = state.vaultToken;
      const res = await fetch('/api/drives', { headers });
      if (!res.ok) throw new Error();
      const data = await res.json();
      state.roots = data.roots || [];
      renderStorageTabs();
    } catch (e) {
      console.error('Failed to load storage drives', e);
    }
  }

  // Render Storage Tabs
  function renderStorageTabs() {
    el.storageTabsList.innerHTML = '';
    state.roots.forEach((root) => {
      const tab = document.createElement('button');
      tab.className = `storage-tab ${root.id === state.currentRoot ? 'active' : ''}`;
      
      let icon = ICONS.folderShared;
      if (root.type === 'vault') icon = ICONS.shieldLock;
      if (root.type === 'usb') icon = ICONS.usb;

      let lockBadge = '';
      if (root.type === 'vault') {
        lockBadge = root.is_unlocked
          ? '<span class="badge-tag" style="background: rgba(16,185,129,0.3); color: #10b981;">Unlocked</span>'
          : '<span class="badge-tag" style="background: rgba(239,68,68,0.3); color: #ef4444;">Locked</span>';
      }

      tab.innerHTML = `
        <span class="tab-icon">${icon}</span>
        <span>${root.name}</span>
        ${lockBadge}
      `;

      tab.addEventListener('click', () => {
        if (state.currentRoot !== root.id) {
          // If leaving the Private Vault, immediately lock it so re-entering requires password!
          if (state.currentRoot === 'vault') {
            lockVault(true);
          }
          state.currentRoot = root.id;
          state.currentPath = '';
          state.searchQuery = '';
          el.searchInput.value = '';
          el.clearSearchBtn.classList.add('hidden');
          renderStorageTabs();
          loadFiles();
        }
      });

      el.storageTabsList.appendChild(tab);
    });
  }

  // Load Files & Folders
  async function loadFiles() {
    el.filesContainer.innerHTML = '';
    el.emptyState.classList.add('hidden');
    el.vaultLockedState.classList.add('hidden');

    const headers = {};
    if (state.vaultToken) headers['X-Vault-Token'] = state.vaultToken;

    const url = `/api/files?root=${encodeURIComponent(state.currentRoot)}&path=${encodeURIComponent(state.currentPath)}`;

    try {
      const res = await fetch(url, { headers });

      if (res.status === 401) {
        // Vault is locked
        el.vaultLockedState.classList.remove('hidden');
        el.vaultErrorMsg.classList.add('hidden');
        el.vaultPasswordInput.value = '';
        el.vaultPasswordInput.focus();
        el.lockVaultBtn.classList.add('hidden');
        renderBreadcrumbs([{ name: 'Private Vault (Locked)', path: '' }]);
        return;
      }

      if (!res.ok) {
        throw new Error('Failed to load files');
      }

      const data = await res.json();
      state.items = data.items || [];
      state.isReadOnly = !!data.read_only;

      // Show or hide Lock Vault button based on current location
      if (state.currentRoot === 'vault') {
        el.lockVaultBtn.classList.remove('hidden');
      } else {
        el.lockVaultBtn.classList.add('hidden');
      }

      // Update upload / new folder buttons based on read_only state
      el.uploadFilesBtn.disabled = state.isReadOnly;
      if (el.uploadFolderBtn) el.uploadFolderBtn.disabled = state.isReadOnly;
      el.newFolderBtn.disabled = state.isReadOnly;
      if (el.floatingUploadBtn) el.floatingUploadBtn.disabled = state.isReadOnly;
      if (state.isReadOnly) {
        el.uploadFilesBtn.title = 'Storage location is Read-Only';
        if (el.uploadFolderBtn) el.uploadFolderBtn.title = 'Storage location is Read-Only';
        el.newFolderBtn.title = 'Storage location is Read-Only';
        el.dropzone.style.opacity = '0.5';
        el.dropzone.style.pointerEvents = 'none';
      } else {
        el.uploadFilesBtn.title = 'Upload files';
        if (el.uploadFolderBtn) el.uploadFolderBtn.title = 'Upload a whole folder including subfolders';
        el.newFolderBtn.title = 'Create new folder';
        el.dropzone.style.opacity = '1';
        el.dropzone.style.pointerEvents = 'auto';
      }

      renderBreadcrumbs(data.breadcrumbs || []);
      renderFilteredItems();
    } catch (e) {
      showToast('Error loading directory');
    }
  }

  // Render Breadcrumbs
  function renderBreadcrumbs(crumbs) {
    el.breadcrumbsNav.innerHTML = '';
    const currentRootObj = state.roots.find((r) => r.id === state.currentRoot);
    const rootDisplayName = currentRootObj ? currentRootObj.name : 'Root';

    crumbs.forEach((crumb, idx) => {
      const isLast = idx === crumbs.length - 1;
      const span = document.createElement('span');
      span.className = `breadcrumb-item ${isLast ? 'current' : ''}`;
      span.textContent = idx === 0 ? rootDisplayName : crumb.name;

      if (!isLast) {
        span.addEventListener('click', () => {
          state.currentPath = crumb.path;
          loadFiles();
        });
      }
      el.breadcrumbsNav.appendChild(span);

      if (!isLast) {
        const sep = document.createElement('span');
        sep.className = 'breadcrumb-separator';
        sep.textContent = '/';
        el.breadcrumbsNav.appendChild(sep);
      }
    });
  }

  // Active item for Share to Drive modal
  let itemToShare = null;

  function openShareDriveModal(item) {
    itemToShare = item;
    el.shareDriveFilename.textContent = item.name;
    el.shareDriveSelect.innerHTML = '';

    // Find all target storage locations that are not the current root and not read-only
    const availableTargets = state.roots.filter((r) => r.id !== state.currentRoot && !r.read_only);

    if (availableTargets.length === 0) {
      showToast('No other writable drives currently shared.');
      return;
    }

    availableTargets.forEach((target) => {
      const opt = document.createElement('option');
      opt.value = target.id;
      opt.textContent = target.name;
      el.shareDriveSelect.appendChild(opt);
    });

    el.shareDriveModal.classList.remove('hidden');
  }

  // Filter & Render Items
  function renderFilteredItems() {
    el.filesContainer.innerHTML = '';
    const query = state.searchQuery.toLowerCase().trim();

    const filtered = state.items.filter((item) => {
      // Search filter
      const matchesSearch = !query || item.name.toLowerCase().includes(query);
      // Category filter
      const matchesCategory =
        state.currentFilter === 'all' ||
        (item.is_dir && state.currentFilter === 'all') ||
        (!item.is_dir && item.category === state.currentFilter);

      return matchesSearch && matchesCategory;
    });

    if (filtered.length === 0) {
      el.emptyState.classList.remove('hidden');
      return;
    }

    el.emptyState.classList.add('hidden');

    // Check if other writable drives exist to show Share to Drive button
    const hasOtherDrives = state.roots.some((r) => r.id !== state.currentRoot && !r.read_only);

    filtered.forEach((item) => {
      const card = document.createElement('div');
      card.className = `file-card cat-${item.category}`;

      const iconSvg = ICONS[item.category] || (item.is_dir ? ICONS.folder : ICONS.other);

      let iconBoxHtml = iconSvg;
      if (!item.is_dir && item.has_thumbnail) {
        const tokenParam = state.vaultToken ? `&token=${encodeURIComponent(state.vaultToken)}` : '';
        const thumbUrl = `/api/thumbnail?root=${encodeURIComponent(state.currentRoot)}&path=${encodeURIComponent(item.path)}${tokenParam}`;
        const extLabel = (item.ext.replace('.', '') || item.category).toUpperCase();
        iconBoxHtml = `
          <div class="thumb-container">
            <img src="${thumbUrl}" alt="${item.name}" loading="lazy" class="file-thumb-img" onerror="this.onerror=null; this.parentElement.innerHTML='${iconSvg.replace(/'/g, "\\'")}';">
            <span class="file-ext-pill">${extLabel}</span>
          </div>
        `;
      }

      card.innerHTML = `
        <div class="file-icon-box ${item.has_thumbnail ? 'has-preview' : ''}">
          ${iconBoxHtml}
        </div>
        <div class="file-details">
          <span class="file-name" title="${item.name}">${item.name}</span>
          <div class="file-meta">
            <span>${item.size_str}</span>
            <span>${item.modified}</span>
          </div>
        </div>
        <div class="file-actions">
          ${
            item.previewable
              ? `<button class="btn-icon-sm btn-preview" title="Preview">${ICONS.eye}</button>`
              : ''
          }
          <button class="btn-icon-sm btn-download" title="Download">${ICONS.download}</button>
          ${
            hasOtherDrives
              ? `<button class="btn-icon-sm btn-share-drive" title="Share / Copy to Drive">${ICONS.shareDrive}</button>`
              : ''
          }
          ${
            !state.isReadOnly
              ? `<button class="btn-icon-sm btn-delete" title="Delete">${ICONS.trash}</button>`
              : ''
          }
        </div>
      `;

      // Click card to open folder or preview file
      card.addEventListener('click', (e) => {
        if (e.target.closest('.file-actions')) return;
        if (item.is_dir) {
          state.currentPath = item.path;
          loadFiles();
        } else if (item.previewable) {
          openPreview(item);
        } else {
          downloadItem(item);
        }
      });

      // Preview button click
      const previewBtn = card.querySelector('.btn-preview');
      if (previewBtn) {
        previewBtn.addEventListener('click', (e) => {
          e.stopPropagation();
          openPreview(item);
        });
      }

      // Download button click
      const downloadBtn = card.querySelector('.btn-download');
      if (downloadBtn) {
        downloadBtn.addEventListener('click', (e) => {
          e.stopPropagation();
          downloadItem(item);
        });
      }

      // Share to Drive button click
      const shareDriveBtn = card.querySelector('.btn-share-drive');
      if (shareDriveBtn) {
        shareDriveBtn.addEventListener('click', (e) => {
          e.stopPropagation();
          openShareDriveModal(item);
        });
      }

      // Delete button click
      const deleteBtn = card.querySelector('.btn-delete');
      if (deleteBtn) {
        deleteBtn.addEventListener('click', (e) => {
          e.stopPropagation();
          deleteItem(item);
        });
      }

      el.filesContainer.appendChild(card);
    });
  }

  // Download File or Folder
  function downloadItem(item) {
    const tokenParam = state.vaultToken ? `&token=${encodeURIComponent(state.vaultToken)}` : '';
    const zipParam = item.is_dir ? '&zip=true' : '';
    const downloadUrl = `/api/download?root=${encodeURIComponent(state.currentRoot)}&path=${encodeURIComponent(item.path)}${zipParam}${tokenParam}`;
    
    // Create invisible anchor to trigger direct download
    const a = document.createElement('a');
    a.href = downloadUrl;
    a.download = item.is_dir ? `${item.name}.zip` : item.name;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    showToast(`Starting download: ${item.name}`);
  }

  // Delete File or Folder
  async function deleteItem(item) {
    if (!confirm(`Are you sure you want to delete "${item.name}"?`)) return;

    try {
      const headers = { 'Content-Type': 'application/json' };
      if (state.vaultToken) headers['X-Vault-Token'] = state.vaultToken;

      const res = await fetch('/api/delete', {
        method: 'POST',
        headers,
        body: JSON.stringify({
          root: state.currentRoot,
          path: item.path,
        }),
      });

      const data = await res.json();
      if (res.ok) {
        showToast(`Deleted ${item.name}`);
        loadFiles();
      } else {
        showToast(data.error || 'Delete failed');
      }
    } catch (e) {
      showToast('Error deleting item');
    }
  }

  // Open In-Browser Media Preview
  function openPreview(item) {
    el.previewFilename.textContent = item.name;
    el.previewFilesize.textContent = item.size_str;
    el.previewBody.innerHTML = '';

    const tokenParam = state.vaultToken ? `&token=${encodeURIComponent(state.vaultToken)}` : '';
    const previewUrl = `/api/preview?root=${encodeURIComponent(state.currentRoot)}&path=${encodeURIComponent(item.path)}${tokenParam}`;
    const downloadUrl = `/api/download?root=${encodeURIComponent(state.currentRoot)}&path=${encodeURIComponent(item.path)}${tokenParam}`;

    el.previewDownloadDirectBtn.href = downloadUrl;

    if (item.category === 'video') {
      const video = document.createElement('video');
      video.className = 'preview-media-element';
      video.src = previewUrl;
      video.controls = true;
      video.autoplay = true;
      el.previewBody.appendChild(video);
    } else if (item.category === 'audio') {
      const audioContainer = document.createElement('div');
      audioContainer.style.textAlign = 'center';
      audioContainer.style.padding = '40px';

      const audio = document.createElement('audio');
      audio.className = 'preview-media-element';
      audio.src = previewUrl;
      audio.controls = true;
      audio.autoplay = true;
      audio.style.width = '300px';

      audioContainer.innerHTML = `<div style="color: #38bdf8; margin-bottom: 20px;">${ICONS.audio}</div>`;
      audioContainer.appendChild(audio);
      el.previewBody.appendChild(audioContainer);
    } else if (item.category === 'image') {
      const img = document.createElement('img');
      img.className = 'preview-media-element';
      img.src = previewUrl;
      img.alt = item.name;
      // Some image formats (TIFF, HEIC, etc.) cannot be rendered by the browser.
      // Fall back to the server-generated JPEG thumbnail for those cases.
      const thumbToken = state.vaultToken ? `&token=${encodeURIComponent(state.vaultToken)}` : '';
      const thumbUrl = `/api/thumbnail?root=${encodeURIComponent(state.currentRoot)}&path=${encodeURIComponent(item.path)}${thumbToken}`;
      img.onerror = () => {
        img.onerror = null;
        img.src = thumbUrl;
      };
      el.previewBody.appendChild(img);
    } else if (item.category === 'code' || item.ext === '.txt' || item.ext === '.csv' || item.ext === '.md') {
      const pre = document.createElement('pre');
      pre.className = 'text-code-preview';
      pre.textContent = 'Loading content...';
      el.previewBody.appendChild(pre);

      fetch(previewUrl)
        .then((r) => r.text())
        .then((txt) => {
          pre.textContent = txt;
        })
        .catch(() => {
          pre.textContent = 'Error loading preview text.';
        });
    } else if (item.ext === '.pdf') {
      const iframe = document.createElement('iframe');
      iframe.style.width = '100%';
      iframe.style.height = '100%';
      iframe.style.border = 'none';
      iframe.src = previewUrl;
      el.previewBody.appendChild(iframe);
    } else {
      el.previewBody.innerHTML = `<p style="color: #94a3b8; padding: 20px;">No inline preview available for this format.</p>`;
    }

    el.previewModal.classList.remove('hidden');
  }

  function closePreview() {
    el.previewBody.innerHTML = '';
    el.previewModal.classList.add('hidden');
  }

  // Build upload entries from a classic FileList (paths = plain filenames,
  // or webkitRelativePath when a folder picker / folder drop provided it).
  function buildUploadsFromFileList(fileList) {
    const uploads = [];
    for (let i = 0; i < fileList.length; i++) {
      const f = fileList[i];
      uploads.push({ file: f, relPath: f.webkitRelativePath || f.name });
    }
    return uploads;
  }

  // Recursively walk a dropped directory entry so whole-folder drag-and-drop
  // preserves the folder tree, including deeply nested subfolders.
  function traverseDirEntry(entry, basePath, onBatch) {
    if (entry.isFile) {
      entry.file(
        (file) => {
          onBatch([{ file, relPath: (basePath ? basePath + '/' : '') + entry.name }]);
        },
        () => onBatch([])
      );
    } else if (entry.isDirectory) {
      const allCollected = [];
      const reader = entry.createReader();
      const childBase = (basePath ? basePath + '/' : '') + entry.name;

      const readBatch = () => {
        reader.readEntries(
          (entries) => {
            if (entries.length === 0) {
              onBatch(allCollected);
              return;
            }
            let pending = entries.length;
            entries.forEach((child) => {
              traverseDirEntry(child, childBase, (batch) => {
                allCollected.push(...batch);
                pending -= 1;
                if (pending === 0) readBatch();
              });
            });
          },
          () => onBatch(allCollected)
        );
      };
      readBatch();
    } else {
      onBatch([]);
    }
  }

  // Extract files (and folder structure) from a drag-and-drop event.
  function collectDroppedFiles(dataTransfer) {
    return new Promise((resolve) => {
      const items = dataTransfer && dataTransfer.items;
      const collected = [];

      if (items && items.length && typeof items[0].webkitGetAsEntry === 'function') {
        const entries = [];
        for (let i = 0; i < items.length; i++) {
          const entry = items[i].webkitGetAsEntry();
          if (entry) entries.push(entry);
        }
        if (entries.length === 0) {
          resolve(buildUploadsFromFileList(dataTransfer.files));
          return;
        }
        let pending = entries.length;
        entries.forEach((entry) => {
          traverseDirEntry(entry, '', (batch) => {
            collected.push(...batch);
            pending -= 1;
            if (pending === 0) resolve(collected);
          });
        });
      } else {
        resolve(buildUploadsFromFileList(dataTransfer.files));
      }
    });
  }

  // Upload a single file via XHR, reporting per-file progress to the row.
  function uploadSingleFile(file, relPath, destPath, rowEl) {
    return new Promise((resolve, reject) => {
      const formData = new FormData();
      formData.append('root', state.currentRoot);
      formData.append('path', destPath);
      formData.append('file', file);
      formData.append('rel_path', relPath);

      const xhr = new XMLHttpRequest();
      xhr.open('POST', '/api/upload', true);
      if (state.vaultToken) {
        xhr.setRequestHeader('X-Vault-Token', state.vaultToken);
      }

      xhr.upload.onprogress = (e) => {
        if (e.lengthComputable) {
          const percent = Math.round((e.loaded / e.total) * 100);
          updateUploadRow(rowEl, percent, 'Uploading');
        }
      };

      xhr.onload = () => {
        if (xhr.status === 200) {
          resolve();
        } else {
          let message = 'Upload failed';
          try {
            const resp = JSON.parse(xhr.responseText);
            message = resp.error || message;
          } catch (e) { /* ignore */ }
          reject(new Error(message));
        }
      };

      xhr.onerror = () => reject(new Error('Network error'));
      xhr.send(formData);
    });
  }

  // Update a single upload row's progress bar and status text.
  function updateUploadRow(rowEl, percent, status) {
    if (!rowEl) return;
    const bar = rowEl.querySelector('.upload-item-bar-fill');
    const statusEl = rowEl.querySelector('.upload-item-status');
    if (bar) bar.style.width = `${Math.max(0, Math.min(100, percent))}%`;
    if (statusEl) {
      statusEl.textContent = status;
      statusEl.className = 'upload-item-status';
      if (status === 'Uploading') statusEl.classList.add('uploading');
      else if (status === 'Done') statusEl.classList.add('done');
      else if (status === 'Error') statusEl.classList.add('failed');
    }
  }

  // Main upload entry point. Accepts an array of {file, relPath} objects
  // OR a FileList/File[] (paths inferred from file names / webkitRelativePath).
  // Files are streamed sequentially so each one reports its own progress and
  // nested folder paths are preserved on the server.
  async function uploadFiles(fileList, destPath) {
    let uploads = fileList;
    if (!uploads || uploads.length === 0) return;

    // Normalize FileList / File[] to {file, relPath} entries
    if (!Array.isArray(uploads) || (uploads.length && uploads[0] instanceof File)) {
      uploads = buildUploadsFromFileList(uploads);
    }
    if (uploads.length === 0) return;

    if (state.isReadOnly) {
      showToast('Cannot upload: Storage location is Read-Only');
      return;
    }

    const uploadDir = destPath || state.currentPath;
    const total = uploads.length;

    el.uploadProgressContainer.classList.remove('hidden');
    el.uploadStatusText.textContent = `Uploading ${total} file(s)...`;
    el.uploadProgressBarFill.style.width = '0%';
    el.uploadList.innerHTML = '';

    const rows = [];
    uploads.forEach((u) => {
      const div = document.createElement('div');
      div.className = 'upload-item';
      const sizeText = u.file.size > 0 ? `${(u.file.size / (1024 * 1024)).toFixed(2)} MB` : '0 B';
      const displayPath = u.relPath && u.relPath.indexOf('/') !== -1
        ? u.relPath
        : u.file.name;
      div.innerHTML = `
        <div class="upload-item-header">
          <span class="upload-item-name" title="${escapeHtml(displayPath)}">${escapeHtml(displayPath)}</span>
          <span class="upload-item-status">Waiting</span>
        </div>
        <div class="upload-item-meta"><span>${escapeHtml(sizeText)}</span></div>
        <div class="upload-item-bar-bg"><div class="upload-item-bar-fill" style="width:0%"></div></div>
      `;
      el.uploadList.appendChild(div);
      rows.push(div);
    });

    let completed = 0;
    let failed = 0;

    for (let i = 0; i < total; i++) {
      const { file, relPath } = uploads[i];
      const rowEl = rows[i];
      updateUploadRow(rowEl, 0, 'Uploading');
      try {
        await uploadSingleFile(file, relPath, uploadDir, rowEl);
        updateUploadRow(rowEl, 100, 'Done');
        completed += 1;
      } catch (err) {
        updateUploadRow(rowEl, 0, 'Error');
        rowEl.querySelector('.upload-item-name').title = err && err.message ? err.message : 'Upload failed';
        failed += 1;
      }
      const overall = total > 0 ? Math.round((completed / total) * 100) : 100;
      el.uploadProgressBarFill.style.width = `${overall}%`;
      el.uploadStatusText.textContent = `Uploaded ${completed}/${total}`;
    }

    if (failed === 0) {
      el.uploadProgressBarFill.style.width = '100%';
      el.uploadStatusText.textContent = `Upload complete! (${total} file(s))`;
      showToast(`Successfully uploaded ${completed} file(s)`);
    } else if (completed > 0) {
      el.uploadStatusText.textContent = `Finished: ${completed} uploaded, ${failed} failed`;
      showToast(`${completed} uploaded, ${failed} failed`);
    } else {
      el.uploadStatusText.textContent = 'Upload failed';
      showToast('All uploads failed');
    }

    loadFiles();

    setTimeout(() => {
      el.uploadProgressContainer.classList.add('hidden');
      el.uploadList.innerHTML = '';
    }, 4000);
  }

  // Lock Private Vault
  async function lockVault(silent = false) {
    const token = state.vaultToken;
    state.vaultToken = '';
    localStorage.removeItem('agy_vault_token');
    sessionStorage.removeItem('agy_vault_token');
    document.cookie = "vault_token=; expires=Thu, 01 Jan 1970 00:00:00 UTC; path=/;";

    if (token) {
      try {
        fetch('/api/auth/lock', {
          method: 'POST',
          headers: { 'X-Vault-Token': token }
        });
      } catch (e) {}
    }

    el.lockVaultBtn.classList.add('hidden');
    if (!silent) {
      showToast('Private Vault locked');
    }
    await loadStorageRoots();
    if (state.currentRoot === 'vault') {
      loadFiles();
    }
  }

  // Vault Unlock Handling
  el.vaultUnlockForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    const password = el.vaultPasswordInput.value;
    el.vaultErrorMsg.classList.add('hidden');

    try {
      const res = await fetch('/api/auth/vault', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ password }),
      });

      const data = await res.json();
      if (res.ok && data.success) {
        state.vaultToken = data.token;
        // Do NOT store in localStorage so leaving/reloading will strictly ask for password again!
        showToast('Private Vault unlocked!');
        el.lockVaultBtn.classList.remove('hidden');
        await loadStorageRoots();
        await loadFiles();
      } else {
        el.vaultErrorMsg.textContent = data.error || 'Incorrect password';
        el.vaultErrorMsg.classList.remove('hidden');
      }
    } catch {
      el.vaultErrorMsg.textContent = 'Connection error';
      el.vaultErrorMsg.classList.remove('hidden');
    }
  });

  // Password Visibility Toggle
  el.togglePasswordVisibility.addEventListener('click', () => {
    const isPassword = el.vaultPasswordInput.type === 'password';
    el.vaultPasswordInput.type = isPassword ? 'text' : 'password';
  });

  // Event Listeners Setup
  function setupEventListeners() {
    // Lock Vault Button
    el.lockVaultBtn.addEventListener('click', () => lockVault(false));

    // Theme Switch
    el.themeToggleBtn.addEventListener('click', () => {
      state.isDark = !state.isDark;
      localStorage.setItem('agy_theme', state.isDark ? 'dark' : 'light');
      applyTheme();
    });

    // View Mode (Grid vs List)
    el.viewGridBtn.addEventListener('click', () => {
      state.viewMode = 'grid';
      localStorage.setItem('agy_view_mode', 'grid');
      el.filesContainer.className = 'files-container grid-view';
      el.viewGridBtn.classList.add('active');
      el.viewListBtn.classList.remove('active');
    });

    el.viewListBtn.addEventListener('click', () => {
      state.viewMode = 'list';
      localStorage.setItem('agy_view_mode', 'list');
      el.filesContainer.className = 'files-container list-view';
      el.viewListBtn.classList.add('active');
      el.viewGridBtn.classList.remove('active');
    });

    if (state.viewMode === 'list') {
      el.filesContainer.className = 'files-container list-view';
      el.viewListBtn.classList.add('active');
      el.viewGridBtn.classList.remove('active');
    }

    // Search Input
    el.searchInput.addEventListener('input', (e) => {
      state.searchQuery = e.target.value;
      if (state.searchQuery) {
        el.clearSearchBtn.classList.remove('hidden');
      } else {
        el.clearSearchBtn.classList.add('hidden');
      }
      renderFilteredItems();
    });

    el.clearSearchBtn.addEventListener('click', () => {
      el.searchInput.value = '';
      state.searchQuery = '';
      el.clearSearchBtn.classList.add('hidden');
      renderFilteredItems();
    });

    // Filter Chips
    el.filterChips.querySelectorAll('.chip').forEach((chip) => {
      chip.addEventListener('click', () => {
        el.filterChips.querySelectorAll('.chip').forEach((c) => c.classList.remove('active'));
        chip.classList.add('active');
        state.currentFilter = chip.dataset.filter;
        renderFilteredItems();
      });
    });

    // Upload Buttons (Mobile & Desktop)
    el.uploadFilesBtn.addEventListener('click', () => el.filePickerInput.click());
    if (el.uploadFolderBtn) {
      el.uploadFolderBtn.addEventListener('click', () => openFolderPicker());
    }
    if (el.quickPickAnyBtn) {
      el.quickPickAnyBtn.addEventListener('click', (e) => {
        e.stopPropagation();
        el.filePickerInput.click();
      });
    }
    if (el.quickPickFolderBtn) {
      el.quickPickFolderBtn.addEventListener('click', (e) => {
        e.stopPropagation();
        openFolderPicker();
      });
    }
    if (el.quickPickMediaBtn) {
      el.quickPickMediaBtn.addEventListener('click', (e) => {
        e.stopPropagation();
        el.photoPickerInput.click();
      });
    }
    if (el.floatingUploadBtn) {
      el.floatingUploadBtn.addEventListener('click', () => el.filePickerInput.click());
    }

    el.dropzone.addEventListener('click', (e) => {
      if (e.target.closest('button')) return;
      el.filePickerInput.click();
    });

    el.filePickerInput.addEventListener('change', (e) => {
      uploadFiles(e.target.files);
      el.filePickerInput.value = '';
    });

    el.photoPickerInput.addEventListener('change', (e) => {
      uploadFiles(e.target.files);
      el.photoPickerInput.value = '';
    });

    el.folderPickerInput.addEventListener('change', (e) => {
      const files = e.target.files;
      if (files && files.length && !files[0].webkitRelativePath) {
        // Browser opened a plain file dialog (webkitdirectory unsupported):
        // the picked items carry no folder structure.
        showToast('This browser can\u2019t select whole folders. Files were uploaded without folder structure.');
      }
      uploadFiles(files);
      el.folderPickerInput.value = '';
    });

    // Drag & Drop
    ['dragenter', 'dragover'].forEach((eventName) => {
      el.dropzone.addEventListener(eventName, (e) => {
        e.preventDefault();
        e.stopPropagation();
        el.dropzone.classList.add('dragover');
      });
    });

    ['dragleave', 'drop'].forEach((eventName) => {
      el.dropzone.addEventListener(eventName, (e) => {
        e.preventDefault();
        e.stopPropagation();
        el.dropzone.classList.remove('dragover');
      });
    });

    el.dropzone.addEventListener('drop', async (e) => {
      const dt = e.dataTransfer;
      // Folder-aware drag & drop: preserves nested folder structure
      const uploads = await collectDroppedFiles(dt);
      uploadFiles(uploads);
    });

    // Refresh Button
    el.refreshBtn.addEventListener('click', () => {
      loadStorageRoots();
      loadFiles();
      showToast('Refreshed directory');
    });

    // Download Whole Folder as Zip
    el.downloadZipBtn.addEventListener('click', () => {
      const tokenParam = state.vaultToken ? `&token=${encodeURIComponent(state.vaultToken)}` : '';
      const downloadUrl = `/api/download?root=${encodeURIComponent(state.currentRoot)}&path=${encodeURIComponent(state.currentPath)}&zip=true${tokenParam}`;
      const a = document.createElement('a');
      a.href = downloadUrl;
      a.download = `${state.currentRoot}_folder.zip`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      showToast('Packaging and downloading folder ZIP...');
    });

    // New Folder Modal
    el.newFolderBtn.addEventListener('click', () => {
      el.folderNameInput.value = '';
      el.newFolderModal.classList.remove('hidden');
      el.folderNameInput.focus();
    });

    el.closeFolderModalBtn.addEventListener('click', () => el.newFolderModal.classList.add('hidden'));
    el.cancelFolderBtn.addEventListener('click', () => el.newFolderModal.classList.add('hidden'));

    el.newFolderForm.addEventListener('submit', async (e) => {
      e.preventDefault();
      const folderName = el.folderNameInput.value.trim();
      if (!folderName) return;

      try {
        const headers = { 'Content-Type': 'application/json' };
        if (state.vaultToken) headers['X-Vault-Token'] = state.vaultToken;

        const res = await fetch('/api/mkdir', {
          method: 'POST',
          headers,
          body: JSON.stringify({
            root: state.currentRoot,
            path: state.currentPath,
            name: folderName,
          }),
        });

        const data = await res.json();
        if (res.ok) {
          showToast(`Folder "${folderName}" created`);
          el.newFolderModal.classList.add('hidden');
          loadFiles();
        } else {
          showToast(data.error || 'Failed to create folder');
        }
      } catch {
        showToast('Error creating folder');
      }
    });

    // QR Code Share Modal
    el.showQrBtn.addEventListener('click', () => el.qrModal.classList.remove('hidden'));
    el.closeQrBtn.addEventListener('click', () => el.qrModal.classList.add('hidden'));
    el.copyUrlBtn.addEventListener('click', () => {
      navigator.clipboard.writeText(el.serverUrlInput.value);
      showToast('Link copied to clipboard!');
    });

    // Upload progress: allow user to dismiss the completed status card
    if (el.dismissUploadsBtn) {
      el.dismissUploadsBtn.addEventListener('click', () => {
        el.uploadProgressContainer.classList.add('hidden');
        el.uploadList.innerHTML = '';
      });
    }

    // Preview Modal Close
    el.closePreviewBtn.addEventListener('click', closePreview);
    el.previewModal.addEventListener('click', (e) => {
      if (e.target === el.previewModal) closePreview();
    });

    // Share to Drive Modal
    el.closeShareDriveModalBtn.addEventListener('click', () => el.shareDriveModal.classList.add('hidden'));
    el.cancelShareDriveBtn.addEventListener('click', () => el.shareDriveModal.classList.add('hidden'));
    el.shareDriveModal.addEventListener('click', (e) => {
      if (e.target === el.shareDriveModal) el.shareDriveModal.classList.add('hidden');
    });

    el.confirmShareDriveBtn.addEventListener('click', async () => {
      if (!itemToShare) return;
      const targetRoot = el.shareDriveSelect.value;
      if (!targetRoot) return;

      try {
        const headers = { 'Content-Type': 'application/json' };
        if (state.vaultToken) headers['X-Vault-Token'] = state.vaultToken;

        const res = await fetch('/api/copy', {
          method: 'POST',
          headers,
          body: JSON.stringify({
            src_root: state.currentRoot,
            src_path: itemToShare.path,
            dest_root: targetRoot,
            dest_path: '',
          }),
        });

        const data = await res.json();
        if (res.ok && data.success) {
          showToast(`Copied "${itemToShare.name}" to Drive!`);
          el.shareDriveModal.classList.add('hidden');
        } else {
          showToast(data.error || 'Failed to copy to drive');
        }
      } catch {
        showToast('Error sharing to drive');
      }
    });

    // Auto-lock vault on back button navigation or leaving page
    window.addEventListener('popstate', () => {
      if (state.currentRoot === 'vault') {
        lockVault(true);
      }
    });

    window.addEventListener('beforeunload', () => {
      if (state.vaultToken) {
        state.vaultToken = '';
        localStorage.removeItem('agy_vault_token');
        sessionStorage.removeItem('agy_vault_token');
      }
    });
  }

  // Initialize
  async function init() {
    console.info('Chautara Share Hub UI v3', folderPickSupported ? '(folder upload supported)' : '(folder upload unsupported)');
    applyTheme();
    setupEventListeners();
    await loadServerStatus();
    await loadStorageRoots();
    await loadFiles();
  }

  window.addEventListener('DOMContentLoaded', init);
})();
