// static/js/consultations.js
// ConsultationManager - v1: navigation inside, automatic transcription upload, autosave, visual indicator,
// error handling, auto-retry, debounced saves.
// Dependencies expected from the app: apiUrl, API_CONFIG, and showToast (imported from ./ui.js)

import { showToast } from './ui.js';

/**
 * ConsultationManager
 * Handles consultation lifecycle, audio recording + transcription upload, autosave, and navigation.
 *
 * Design notes:
 * - Navigation is implemented inside (consistent with other modules).
 * - Backend operations use async/await and expect apiUrl & API_CONFIG to exist globally.
 * - Logic is DOM-agnostic where possible; bind/unbind methods are provided for cleanup.
 */
class ConsultationManager {
  /**
   * Create a ConsultationManager.
   * @param {Object} options
   * @param {boolean} options.autoBindDom - If true, manager will immediately attach DOM handlers.
   * @param {number} options.autosaveIntervalMs - Periodic autosave interval in ms (default 60000).
   */
  constructor({ autoBindDom = true, autosaveIntervalMs = 60000 } = {}) {
    // core state
    this.currentConsultationId = null;
    this.currentTemplate = null;
    this.currentPatientId = null;
    this.currentNotes = '';
    this.isRecording = false;
    this.mediaRecorder = null;
    this.audioChunks = [];
    this.audioStream = null;

    // UI / timers
    this._domHandlers = [];
    this._autosaveIntervalMs = autosaveIntervalMs;
    this._autosaveTimer = null; // periodic
    this._debounceSaveTimer = null; // debounced
    this._debounceDelay = 1500; // save after pause
    this._maxTranscriptionRetries = 3;

    // visual recording indicator element (created if missing)
    this._recordingIndicator = null;
    this._recordingTimer = null;
    this._recordingSeconds = 0;

    if (autoBindDom && typeof document !== 'undefined') {
      // safe to call on construction in v1
      this.bindUIEvents();
      this.startPeriodicAutosave();
    }
  }

  /* ============================ Initialization & DOM binding ============================ */

  /**
   * Initialize manager; optionally bind DOM handlers.
   * @param {boolean} bindDom
   */
  init(bindDom = true) {
    if (bindDom) {
      this.bindUIEvents();
      this.startPeriodicAutosave();
    }
  }

  /**
   * Attach DOM event listeners (idempotent: avoids double-binding).
   * Binds: tab buttons, new-consultation form submit, start-audio-recording,
   * consultation-notes input (debounced save), discharge patient select change,
   * review patient search input (debounced).
   */
  bindUIEvents() {
    if (this._domHandlers.length > 0) return; // already bound

    // --- Tabs ---
    const tabButtons = Array.from(document.querySelectorAll('.consultation-tabs__header .tab-button'));
    const tabHandler = (e) => {
      const tab = e.currentTarget.dataset.tab;
      if (tab) this.switchConsultationTab(tab);
    };
    tabButtons.forEach(btn => {
      btn.addEventListener('click', tabHandler);
      this._domHandlers.push({ el: btn, type: 'click', handler: tabHandler });
    });

    // ensure initial visibility matches HTML active button if present
    const activeBtn = document.querySelector('.consultation-tabs__header .tab-button.active');
    const initialTab = activeBtn?.dataset?.tab ?? 'new-consultation';
    this.switchConsultationTab(initialTab);

    // Handle "Add New Patient" button
    const newPatientBtn = document.getElementById('new-patient-btn');
    if (newPatientBtn) {
      const openAddPatientModal = (e) => {
        e.preventDefault();
        if (typeof window.showAddPatientModal === 'function') {
          window.showAddPatientModal(); // reuse existing modal from patients.js
        } else {
          showToast('Add Patient modal not found', 'warning');
        }
      };
      newPatientBtn.addEventListener('click', openAddPatientModal);
      this._domHandlers.push({ el: newPatientBtn, type: 'click', handler: openAddPatientModal });
    }

    // Patient search in Consultation tab
    const consultSearchInput = document.getElementById('consult-patient-search');
    if (consultSearchInput) {
      const onSearch = this._debounce(async (ev) => {
        const q = ev.target.value.trim();

        console.log('Consultations search fired with:', q);

        const resultsContainer = document.getElementById('consult-patient-search-results');

        if (!q) {
          resultsContainer.innerHTML = `
            <div class="empty-state">
              <div class="empty-icon">🔍</div>
              <h4>Search for a patient to begin</h4>
              <p>Results will appear here</p>
            </div>`;
          return;
        }

        try {
          const results = await app.patientManager.searchPatients(q); // ✅ reuse existing logic
          this._renderPatientResultsForConsult(results);
        } catch (err) {
          console.error('Patient search error', err);
          showToast('Error searching patients', 'error');
        }
      }, 400);

      consultSearchInput.addEventListener('input', onSearch);
      this._domHandlers.push({ el: consultSearchInput, type: 'input', handler: onSearch });
    }

    // --- Ensure tab switching once you have a selected patient
    const changePatientBtn = document.getElementById('change-patient');
    if (changePatientBtn) {
      changePatientBtn.addEventListener('click', () => {
        this.selectedPatient = null;
        document.getElementById('patient-header').classList.add('hidden');
        this.switchConsultationTab('patient-selection'); // 👈 Go back to first tab
      });
    }

    // --- New consultation form submit ---
    const newForm = document.getElementById('new-consultation-form');
    if (newForm) {
      const submitHandler = async (e) => {
        e.preventDefault();
        const form = e.currentTarget;
        const formData = new FormData(form);
        const payload = {
          patient_id: formData.get('patient_id') || this.currentPatientId,
          specialty: formData.get('specialty') || formData.get('consultation_type'),
        };
        await this.startNewConsultation(payload);
      };
      newForm.addEventListener('submit', submitHandler);
      this._domHandlers.push({ el: newForm, type: 'submit', handler: submitHandler });
    }

    // --- Start audio recording button ---
    const startAudioBtn = document.getElementById('start-audio-recording');
    if (startAudioBtn) {
      const startHandler = (e) => {
        e.preventDefault();
        this.switchConsultationTab('patient-review'); // optional UX: move to review/record section if desired
        this.startAudioRecording();
      };
      startAudioBtn.addEventListener('click', startHandler);
      this._domHandlers.push({ el: startAudioBtn, type: 'click', handler: startHandler });
    }

    // --- Consultation notes input (debounced autosave) ---
    const notesEl = document.getElementById('consultation-notes');
    if (notesEl) {
      const inputHandler = (e) => {
        this.currentNotes = e.target.value;
        this._debouncedSaveDraft();
      };
      notesEl.addEventListener('input', inputHandler);
      this._domHandlers.push({ el: notesEl, type: 'input', handler: inputHandler });
    }

    // --- Discharge patient select: load consultations for patient when changed ---
    const dischargeSelect = document.getElementById('discharge-patient');
    if (dischargeSelect) {
      const changeHandler = async (e) => {
        const pid = e.target.value;
        if (pid) {
          await this.loadConsultationsForPatient(pid);
        } else {
          this._clearElementById('patient-consultations');
        }
      };
      dischargeSelect.addEventListener('change', changeHandler);
      this._domHandlers.push({ el: dischargeSelect, type: 'change', handler: changeHandler });
    }

    // --- Review patient search (debounced) ---
    const reviewSearch = document.getElementById('review-patient-search');
    if (reviewSearch) {
      const debouncedSearch = this._debounce(async (ev) => {
        const q = ev.target.value.trim();
        if (!q) return;
        const results = await app.patientManager.searchPatients(q);
        // transitional behavior: render results to #review-results (lightweight)
        this._renderReviewResults(results);
      }, 400);
      reviewSearch.addEventListener('input', debouncedSearch);
      this._domHandlers.push({ el: reviewSearch, type: 'input', handler: debouncedSearch });
    }

    // --- Page unload cleanup (autosave, streams) ---
    const beforeUnloadHandler = async () => {
      try {
        // synchronous: best-effort draft save (navigator.sendBeacon alternative could be used)
        if (this.currentConsultationId || this.currentNotes) {
          await this.saveConsultationDraftImmediately();
        }
      } catch (e) {
        // swallow; this is best-effort
      }
      this.cleanup();
    };
    window.addEventListener('beforeunload', beforeUnloadHandler);
    this._domHandlers.push({ el: window, type: 'beforeunload', handler: beforeUnloadHandler });
  }

  /**
   * Remove attached DOM handlers and stop periodic tasks.
   */
  unbindUIEvents() {
    for (const { el, type, handler } of this._domHandlers) {
      try {
        el.removeEventListener(type, handler);
      } catch (err) {
        // ignore removal errors
      }
    }
    this._domHandlers = [];
    this.clearPeriodicAutosave();
  }

  /* ============================ Navigation inside manager ============================ */

  /**
   * Switch consultation tab. Buttons with data-tab="name" map to content with id="name-tab".
   * Sets button.active and content.active & inline display.
   * @param {string} tabName
   */
  switchConsultationTab(tabName) {
    if (!tabName) return;
    const headerButtons = document.querySelectorAll('.consultation-tabs__header .tab-button');
    headerButtons.forEach(btn => btn.classList.toggle('active', btn.dataset.tab === tabName));

    const contents = document.querySelectorAll('.consultation-tabs__content .tab-content');
    contents.forEach(content => {
      const expectedId = `${tabName}-tab`;
      const isTarget = content.id === expectedId;
      content.classList.toggle('active', isTarget);
      content.style.display = isTarget ? 'block' : 'none';
    });

    //showToast(`Switched to "${tabName}"`, 'info');
    // If switching to certain tabs requires loading data, do it here:
    if (tabName === 'discharge') {
      // populate discharge patient select if empty
      const dischargeSelect = document.getElementById('discharge-patient');
      if (dischargeSelect && dischargeSelect.options.length <= 1) {
        this.loadPatientsList().catch(() => { /* ignore */ });
      }
    }
  }

  /* ============================ Patient & consultation lists ============================ */

  /**
   * Fetch patients and populate the two selects: consultation-patient and discharge-patient.
   * @returns {Promise<Array>} list of patients
   */
  async loadPatientsList() {
    try {
        const res = await fetch(apiUrl(API_CONFIG.ENDPOINTS.patients) + '?page=1&per_page=100');
        if (!res.ok) throw new Error(`Failed to fetch patients (${res.status})`);
        const data = await res.json();
        const patients = data.patients || [];
        

        // populate selects
        this._populateSelect('consultation-patient', patients);
        this._populateSelect('discharge-patient', patients);

        showToast('Patients loaded', 'success');
        return patients;
    } catch (err) {
      console.error('loadPatientsList error', err);
      showToast('Could not load patients', 'error');
      return [];
    }
  }

/**
     * Initiates a new consultation directly from a patient card.
     * Fetches full patient details, sets the selected patient,
     * updates the consultation header, and switches to the
     * consultation form tab for immediate use.
     */
    async startFromPatient(patientId) {
      try {
        // 1. Fetch full patient details (using your patientManager)
        const patient = await app.patientManager.getPatientById(patientId);
        if (!patient) {
          showToast('Patient not found', 'error');
          return;
        }

        // 2. Set as current patient
        this.selectedPatient = patient;

        // 3. Show the patient header in consultations
        this.selectPatient(patient.id, {
          name: `${patient.family_name} ${patient.given_name}`,
          details: `Age ${patient.age ? patient.age + 'y' : '—'} / ID ${patient.id.slice(0, 8)} / Gender ${patient.gender ? (patient.gender.toLowerCase().startsWith('f') ? '♀' : '♂') : '—'}`
        });

        // 4. Jump straight to the consultation tab
        if (app.navigation) {
          app.navigation.navigateTo('consultations');
        } else {
          console.warn('Navigation manager not available');
        }
        this.switchConsultationTab('patient-review');

        showToast(`Starting consultation for ${patient.given_name} ${patient.family_name}`, 'info');
      } catch (err) {
        console.error('Error starting consultation from patient:', err);
        showToast('Could not start consultation', 'error');
      }
    }


  /**
   * Populate a select element by id with patient options.
   * @param {string} selectId
   * @param {Array} patients - objects: { id, name, cnp? }
   * @private
   */
  _populateSelect(selectId, patients = []) {
    const sel = document.getElementById(selectId);
    if (!sel) return;
    // keep the placeholder option and clear the rest
    const placeholder = sel.querySelector('option[value=""]') ?? sel.options[0];
    sel.innerHTML = '';
    if (placeholder) sel.appendChild(placeholder.cloneNode(true));
    patients.forEach(p => {
      const opt = document.createElement('option');
      opt.value = p.id;
      opt.textContent = p.name || `${p.id}`;
      sel.appendChild(opt);
    });
  }

  /**
   * Load consultations for a given patient and render them in #patient-consultations.
   * @param {string} patientId
   */
  async loadConsultationsForPatient(patientId) {
    if (!patientId) return;
    try {
      const res = await fetch(apiUrl(API_CONFIG.ENDPOINTS.consultations, `?patient_id=${encodeURIComponent(patientId)}`));
      if (!res.ok) throw new Error('Failed to load consultations');
      const consultations = await res.json();

      const container = document.getElementById('patient-consultations');
      if (!container) return;
      container.innerHTML = '';
      if (!consultations.length) {
        container.innerHTML = '<div class="empty-state">No completed consultations for this patient.</div>';
        return;
      }
      consultations.forEach(c => {
        const card = document.createElement('div');
        card.className = 'consultation-item';
        const specialtyLabel = c.specialty || c.consultation_type || 'Consultation';
        const consultationDate = c.consultation_date || c.timestamp;
        card.innerHTML = `
          <div class="consultation-meta">
            <strong>${specialtyLabel}</strong>
            <div class="muted">${consultationDate ? new Date(consultationDate).toLocaleString() : ''}</div>
          </div>
          <div class="consultation-notes-snippet">${(c.notes || '').slice(0, 200)}</div>
          <div class="consultation-actions">
            <button data-id="${c.id}" class="btn-secondary btn-generate-discharge">Generate Discharge</button>
          </div>
        `;
        container.appendChild(card);
      });

      // attach handlers for "Generate Discharge" buttons
      container.querySelectorAll('.btn-generate-discharge').forEach(btn => {
        btn.addEventListener('click', async (e) => {
          const cid = e.currentTarget.dataset.id;
          await this.generateDischargeSummaryByConsultation(cid);
        });
      });

      showToast('Consultations loaded', 'success');
    } catch (err) {
      console.error('loadConsultationsForPatient', err);
      showToast('Failed to load consultations', 'error');
    }
  }

  /**
   * Render search results in Consultation → Patient Selection tab
   */
  _renderPatientResultsForConsult(results = []) {
    const container = document.getElementById('consult-patient-results') 
      || document.getElementById('patient-search-results');
    if (!container) return;

    if (!results.length) {
      container.innerHTML = `
        <div class="empty-state">
          <div class="empty-icon">🔍</div>
          <h4>No patients found</h4>
          <p>Try another name, CNP, or phone</p>
        </div>`;
      return;
    }

    container.innerHTML = results.map(p => {
      const name = this._escapeHtml(`${p.given_name || ''} ${p.family_name || ''}`.trim());
      const age = p.age ? `${p.age}y` : '';
      const gender = p.gender ? (p.gender.toLowerCase().startsWith('f') ? '♀' : '♂') : '';
      const cnp = p.cnp ? `CNP ${p.cnp}` : '';
      const phone = p.phone ? `📞 ${p.phone}` : '';

      return `
        <div class="patient-result-row" data-id="${p.id}" data-tooltip="Click to select">
          <span class="name">${name}</span>
          <span class="demographics">${gender} ${age}</span>
          <span class="cnp">${cnp}</span>
          <span class="phone">${phone}</span>
        </div>`;
    }).join('');

    container.querySelectorAll('.patient-result-row').forEach(row => {
      row.addEventListener('click', () => {
        const id = row.dataset.id;
        const name = row.querySelector('.name').innerText;
        this.selectPatient(id, { name });
        this.switchConsultationTab('patient-review');
      });
    });
  }

  /**
   * Select a patient, update header, and set context
   */
  selectPatient(id, data = {}) {
    this.currentPatientId = id;
    const header = document.getElementById('patient-header');
    const nameEl = document.getElementById('patient-name');
    const detailsEl = document.getElementById('patient-details');

    if (header) header.classList.remove('hidden');
    if (nameEl) nameEl.textContent = data.name || 'Selected Patient';
    if (detailsEl) detailsEl.textContent = data.details || '';

    showToast(`Patient selected: ${data.name}`, 'success');
  }


  
  /* ============================ Consultation lifecycle: create/save/finalize ============================ */

  /**
   * Start a new consultation (creates it in backend and sets currentConsultationId).
   * @param {Object} payload - { patient_id, specialty }
   */
  async startNewConsultation(payload = {}) {
    try {
      if (!payload.patient_id) {
        showToast('Please select a patient', 'warning');
        return null;
      }
      const body = {
        patient_id: payload.patient_id,
        specialty: payload.specialty || 'internal_medicine',
        consultation_date: new Date().toISOString(),
      };
      const res = await fetch(apiUrl(API_CONFIG.ENDPOINTS.consultations), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      });
      if (!res.ok) throw new Error(`Failed to create consultation (${res.status})`);
      const created = await res.json();
      this.currentConsultationId = created.id;
      this.currentPatientId = payload.patient_id;
      this.currentNotes = '';
      showToast('New consultation started', 'success');

      // start autosave only after a consultation exists
      this.startPeriodicAutosave();
      return created;
    } catch (err) {
      console.error('startNewConsultation', err);
      showToast('Failed to start consultation', 'error');
      return null;
    }
  }

  /**
   * Debounced draft save: called on input events. Waits for user to pause to avoid hammering backend.
   * Uses this._debounceDelay.
   * @private
   */
  _debouncedSaveDraft() {
    if (this._debounceSaveTimer) clearTimeout(this._debounceSaveTimer);
    this._debounceSaveTimer = setTimeout(() => {
      this.saveConsultationDraft().catch(() => { /* ignore */ });
    }, this._debounceDelay);
  }

  /**
   * Save current consultation as draft (non-blocking; awaited where necessary).
   * If no consultation exists yet (no id), creates one in draft mode.
   */
  async saveConsultationDraft() {
    try {
      const payload = {
        patient_id: this.currentPatientId,
        notes: this.currentNotes,
        status: 'draft',
        timestamp: new Date().toISOString(),
      };
      let res;
      if (this.currentConsultationId) {
        res = await fetch(apiUrl(API_CONFIG.ENDPOINTS.consultations, this.currentConsultationId), {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload),
        });
      } else {
        res = await fetch(apiUrl(API_CONFIG.ENDPOINTS.consultations), {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload),
        });
      }
      if (!res.ok) throw new Error('Draft save failed');
      const saved = await res.json();
      this.currentConsultationId = saved.id || this.currentConsultationId;
      showToast('Draft saved', 'success');
      return saved;
    } catch (err) {
      console.error('saveConsultationDraft', err);
      showToast('Failed to save draft', 'error');
      return null;
    }
  }

  /**
   * Synchronous attempt to save draft immediately (for beforeunload best-effort).
   * Uses fetch but does not block page unload reliably; it's best-effort.
   */
  async saveConsultationDraftImmediately() {
    try {
      // minimal payload to avoid long operations
      const payload = {
        patient_id: this.currentPatientId,
        notes: this.currentNotes,
        status: 'draft',
        timestamp: new Date().toISOString(),
      };
      await fetch(apiUrl(API_CONFIG.ENDPOINTS.consultations), {
        method: this.currentConsultationId ? 'PUT' : 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
    } catch (err) {
      // ignore errors here
    }
  }

  /**
   * Update consultation status via /status endpoint.
   * @param {string} consultationId - consultation UUID or numeric ID
   * @param {string} newStatus - e.g. "in_progress", "paused", "completed", "cancelled"
   * @returns {Promise<Object|null>} updated consultation or null on failure
   */
  async updateConsultationStatus(consultationId, newStatus) {
    if (!consultationId || !newStatus) {
      showToast('Missing consultation id or status', 'warning');
      return null;
    }

    try {
      const endpoint = apiUrl(API_CONFIG.ENDPOINTS.consultationStatus);
      const res = await fetch(`${endpoint}?id=${encodeURIComponent(consultationId)}&status=${encodeURIComponent(newStatus)}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
      });
      if (!res.ok) throw new Error(`Status update failed (${res.status})`);
      const updated = await res.json();
      showToast(`Status changed to "${newStatus}"`, 'success');
      await this.updateCounters();
      return updated;
    } catch (err) {
      console.error('updateConsultationStatus', err);
      showToast('Failed to update consultation status', 'error');
      return null;
    }
  }

  /**
   * Finalize consultation: mark 'completed' and optionally generate discharge.
   * @param {string} [consultationId] - defaults to currentConsultationId
   */
  async finalizeConsultation(consultationId = null) {
    const id = consultationId || this.currentConsultationId;
    if (!id) {
        showToast('No consultation to finalize', 'warning');
        return null;
    }
    return await this.updateConsultationStatus(id, 'completed');
    }


  /* ============================ Audio recording & transcription ============================ */

  /**
   * Start audio recording. Requests microphone permissions and creates MediaRecorder.
   * Creates a visual recording indicator.
   */
  async startAudioRecording() {
    if (this.isRecording) {
      showToast('Already recording', 'warning');
      return;
    }
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      this.audioStream = stream;
      this.mediaRecorder = new MediaRecorder(stream);
      this.audioChunks = [];

      this.mediaRecorder.ondataavailable = (ev) => {
        if (ev.data && ev.data.size > 0) this.audioChunks.push(ev.data);
      };

      this.mediaRecorder.onstop = async () => {
        // create blob and upload automatically with retry
        const blob = new Blob(this.audioChunks, { type: 'audio/webm' });
        await this._uploadTranscriptionWithRetry(blob);
        // cleanup stream tracks after stop
        this._stopAudioStream();
      };

      this.mediaRecorder.onerror = (e) => {
        console.error('MediaRecorder error', e);
        showToast('Recording error', 'error');
        this.stopAudioRecording();
      };

      this.mediaRecorder.start();
      this.isRecording = true;
      this._showRecordingIndicator();
      showToast('Recording started', 'info');
    } catch (err) {
      console.error('startAudioRecording', err);
      showToast('Microphone access denied or unavailable', 'error');
    }
  }

  /**
   * Stop audio recording if active.
   */
  stopAudioRecording() {
    if (!this.isRecording || !this.mediaRecorder) return;
    try {
      this.mediaRecorder.stop();
    } catch (err) {
      console.error('stopAudioRecording', err);
    }
    this.isRecording = false;
    this._hideRecordingIndicator();
    showToast('Recording stopped', 'info');
  }

  /**
   * Internal: stop all tracks on the audio stream.
   * @private
   */
  _stopAudioStream() {
    if (!this.audioStream) return;
    try {
      this.audioStream.getTracks().forEach(track => track.stop());
    } catch (e) { /* ignore */ }
    this.audioStream = null;
  }

  /**
   * Upload the audio blob to backend for transcription, with auto-retry and exponential backoff.
   * On success, appends transcription to notes and saves draft.
   * @param {Blob} blob
   * @private
   */
  async _uploadTranscriptionWithRetry(blob) {
    let attempt = 0;
    let lastErr = null;
    while (attempt < this._maxTranscriptionRetries) {
      try {
        const res = await this._uploadTranscription(blob);
        if (!res) throw new Error('Empty transcription response');
        // append transcription text to notes and save draft
        if (res.transcript && res.transcript.trim()) {
          this.appendTranscriptionToNotes(res.transcript);
        }
        showToast('Audio transcribed successfully', 'success');
        return res;
      } catch (err) {
        lastErr = err;
        attempt += 1;
        const waitMs = 500 * Math.pow(2, attempt); // exponential backoff: 1000ms, 2000ms, etc.
        console.warn(`Transcription attempt ${attempt} failed, retrying in ${waitMs}ms`, err);
        await this._sleep(waitMs);
      }
    }
    console.error('Transcription failed after retries', lastErr);
    showToast('Audio transcription failed after multiple attempts', 'error');
    return null;
  }

  /**
   * Performs the actual upload of audio blob to transcription endpoint.
   * Returns parsed JSON with at least { transcript: '...' }.
   * @param {Blob} blob
   * @returns {Promise<Object>}
   * @private
   */
  async _uploadTranscription(blob) {
    if (!blob) throw new Error('No audio blob provided');
    try {
      const fd = new FormData();
      fd.append('file', blob, 'consultation_audio.webm');
      fd.append('consultation_id', this.currentConsultationId || '');

      const res = await fetch(apiUrl(API_CONFIG.ENDPOINTS.audioUpload), {
        method: 'POST',
        body: fd,
      });
      if (!res.ok) {
        const text = await res.text().catch(() => '');
        throw new Error(`Upload failed (${res.status}): ${text}`);
      }
      const data = await res.json();
      return data;
    } catch (err) {
      console.error('_uploadTranscription', err);
      throw err;
    }
  }

  /**
   * Append transcribed text to notes and trigger a draft save.
   * @param {string} text
   */
  appendTranscriptionToNotes(text = '') {
    if (!text) return;
    const notesEl = document.getElementById('consultation-notes');
    if (notesEl) {
      // insert at cursor if possible, else append
      try {
        const start = notesEl.selectionStart ?? notesEl.value.length;
        const before = notesEl.value.slice(0, start);
        const after = notesEl.value.slice(start);
        notesEl.value = `${before}${text}\n${after}`;
        notesEl.focus();
        notesEl.selectionStart = notesEl.selectionEnd = before.length + text.length + 1;
        this.currentNotes = notesEl.value;
      } catch (err) {
        // fallback: append
        notesEl.value = `${notesEl.value}\n${text}`;
        this.currentNotes = notesEl.value;
      }
    } else {
      // no textarea in DOM; append to internal state
      this.currentNotes = `${this.currentNotes}\n${text}`;
    }
    // immediately save draft
    this.saveConsultationDraft().catch(() => { /* ignore */ });
  }

  /* ============================ Discharge & summaries ============================ */

  /**
   * Generate discharge summary by consultation id (fetches consultation details and calls backend summary endpoint).
   * @param {string} consultationId
   */
  async generateDischargeSummaryByConsultation(consultationId) {
    if (!consultationId) {
      showToast('No consultation specified', 'warning');
      return;
    }
    try {
      const res = await fetch(apiUrl(API_CONFIG.ENDPOINTS.consultations, consultationId));
      if (!res.ok) throw new Error('Failed to fetch consultation for discharge');
      const consultation = await res.json();

      // Optionally, call an endpoint that generates a discharge summary (if available)
      const summaryRes = await fetch(apiUrl(API_CONFIG.ENDPOINTS.generateDischarge), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ consultation }),
      });
      if (!summaryRes.ok) throw new Error('Generate discharge failed');
      const summaryData = await summaryRes.json();
      this.displayDischargeSummary(summaryData.summary || 'No summary returned');
    } catch (err) {
      console.error('generateDischargeSummaryByConsultation', err);
      showToast('Failed to generate discharge summary', 'error');
    }
  }

  /**
   * Render the discharge summary in the discharge tab (simple render).
   * @param {string} summaryHtmlOrText
   */
  displayDischargeSummary(summaryHtmlOrText) {
    const container = document.getElementById('patient-consultations');
    if (!container) {
      showToast('Discharge container missing', 'warning');
      return;
    }
    container.innerHTML = `
      <div class="discharge-summary">
        <h4>Discharge Summary</h4>
        <div class="discharge-body">${this._escapeHtml(summaryHtmlOrText)}</div>
        <div class="discharge-actions">
          <button class="btn-primary btn-download-discharge">Download</button>
        </div>
      </div>
    `;
    // download handler (simple text file)
    const dlBtn = container.querySelector('.btn-download-discharge');
    if (dlBtn) {
      dlBtn.addEventListener('click', () => {
        const blob = new Blob([summaryHtmlOrText], { type: 'text/plain' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `discharge_${Date.now()}.txt`;
        a.click();
        URL.revokeObjectURL(url);
      });
    }
  }

  /**
   * Search patients by query (used in review tab).
   * @param {string} query
   * @returns {Promise<Array>}
   */
  async searchPatient(query) {
    if (!query || !query.trim()) return [];
    try {
        const url = apiUrl(API_CONFIG.ENDPOINTS.patients) + `?search=${encodeURIComponent(query)}&per_page=10&page=1`;
        const res = await fetch(url);
        if (!res.ok) throw new Error('Patient search failed');
        const results = await res.json();
        return results;
    } catch (err) {
        console.error('searchPatient', err);
        showToast('Patient search error', 'error');
        return [];
    }
  }

  /* ============================ UI helpers & indicators ============================ */

  /**
   * Create and show a recording indicator if not present. Starts a simple seconds timer.
   * @private
   */
  _showRecordingIndicator() {
    // create element inside new-consultation-tab if available
    const parent = document.getElementById('new-consultation-tab') ?? document.body;
    if (!this._recordingIndicator) {
      const el = document.createElement('div');
      el.id = 'recording-indicator';
      el.className = 'recording-indicator';
      el.innerHTML = `<span class="dot"></span> Recording <span class="time">00:00</span>`;
      // minimal inline styles to ensure visible in most themes
      el.style.position = 'fixed';
      el.style.right = '20px';
      el.style.bottom = '20px';
      el.style.padding = '8px 12px';
      el.style.background = '#b71c1c';
      el.style.color = '#fff';
      el.style.borderRadius = '8px';
      el.style.boxShadow = '0 4px 12px rgba(0,0,0,0.15)';
      el.style.zIndex = 9999;
      el.style.display = 'flex';
      el.style.alignItems = 'center';
      el.style.gap = '8px';
      parent.appendChild(el);
      this._recordingIndicator = el;
    }
    this._recordingSeconds = 0;
    this._updateRecordingTime();
    this._recordingTimer = setInterval(() => {
      this._recordingSeconds += 1;
      this._updateRecordingTime();
    }, 1000);
    this._recordingIndicator.style.display = 'flex';
  }

  /**
   * Hide and remove the recording indicator.
   * @private
   */
  _hideRecordingIndicator() {
    if (this._recordingTimer) clearInterval(this._recordingTimer);
    this._recordingTimer = null;
    if (this._recordingIndicator) {
      this._recordingIndicator.style.display = 'none';
      // keep element in DOM for re-use rather than removing to avoid layout shifts
    }
  }

  /**
   * Update the time label inside the recording indicator.
   * @private
   */
  _updateRecordingTime() {
    if (!this._recordingIndicator) return;
    const timeEl = this._recordingIndicator.querySelector('.time');
    if (!timeEl) return;
    const mm = String(Math.floor(this._recordingSeconds / 60)).padStart(2, '0');
    const ss = String(this._recordingSeconds % 60).padStart(2, '0');
    timeEl.textContent = `${mm}:${ss}`;
  }

  /**
   * Simple utility to sleep.
   * @param {number} ms
   * @returns {Promise<void>}
   * @private
   */
  _sleep(ms) {
    return new Promise(resolve => setTimeout(resolve, ms));
  }

  /**
   * Escape HTML for insert into text containers (very small helper).
   * @param {string} s
   * @private
   */
  _escapeHtml(s = '') {
    return String(s)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#39;')
      .replace(/\n/g, '<br/>');
  }

  /* ============================ Autosave: periodic + debounced ============================ */

  /**
   * Start periodic autosave (every this._autosaveIntervalMs).
   */
  startPeriodicAutosave() {
    this.clearPeriodicAutosave();
    this._autosaveTimer = setInterval(() => {
      if (this.currentConsultationId || this.currentNotes) {
        this.saveConsultationDraft().catch(() => { /* ignore */ });
      }
    }, this._autosaveIntervalMs);
  }

  /**
   * Stop periodic autosave.
   */
  clearPeriodicAutosave() {
    if (this._autosaveTimer) {
      clearInterval(this._autosaveTimer);
      this._autosaveTimer = null;
    }
  }

  /* ============================ Counters & simple UI updates ============================ */

/**
   * Update tab counters using backend /counts endpoint (MVP-optimized).
   * Falls back to zero if unavailable.
   */
  async updateCounters() {
    try {
      const res = await fetch(apiUrl(API_CONFIG.ENDPOINTS.consultationCounts));
      if (!res.ok) throw new Error('Failed to fetch counts');
      const counts = await res.json();

      this._setCount('active-consultations', counts.active_consultations ?? 0);
      this._setCount('review-pending', counts.review_pending ?? 0);
      this._setCount('discharge-ready', counts.discharge_ready ?? 0);
    } catch (err) {
      console.warn('updateCounters error', err);
      // gracefully fallback to zero
      this._setCount('active-consultations', 0);
      this._setCount('review-pending', 0);
      this._setCount('discharge-ready', 0);
    }
  }

  /**
   * Helper to set the small count by element id.
   * @param {string} id
   * @param {number} value
   * @private
   */
  _setCount(id, value) {
    const el = document.getElementById(id);
    if (el) el.textContent = String(value);
  }

  /* ============================ Utility helpers ============================ */

  /**
   * Forget current consultation state and reset UI.
   */
  resetConsultationState() {
    this.currentConsultationId = null;
    this.currentTemplate = null;
    this.currentPatientId = null;
    this.currentNotes = '';
    // clear notes textarea if present
    const notesEl = document.getElementById('consultation-notes');
    if (notesEl) notesEl.value = '';
    this.clearPeriodicAutosave();
    this._hideRecordingIndicator();
    showToast('Consultation state reset', 'info');
  }

  /**
   * Simple element clearing helper.
   * @param {string} id
   * @private
   */
  _clearElementById(id) {
    const el = document.getElementById(id);
    if (el) el.innerHTML = '';
  }

  /**
   * Debounce helper.
   * @param {Function} fn
   * @param {number} wait
   * @returns {Function}
   * @private
   */
  _debounce(fn, wait = 250) {
    let timer = null;
    return function debounced(...args) {
      if (timer) clearTimeout(timer);
      timer = setTimeout(() => fn.apply(this, args), wait);
    }.bind(this);
  }

  /**
   * Render review results in the review-results container (simple transitional renderer).
   * @param {Array} results
   * @private
   */
  _renderReviewResults(results = []) {
    const container = document.getElementById('review-results');
    if (!container) return;
    if (!results.length) {
      container.innerHTML = `
        <div class="empty-state">
          <div class="empty-icon">🔍</div>
          <h4>No results</h4>
          <p>Try a different search</p>
        </div>
      `;
      return;
    }
    container.innerHTML = '';
    results.forEach(p => {
      const row = document.createElement('div');
      row.className = 'review-row';
      row.innerHTML = `<strong>${p.name}</strong> <div class="muted">${p.cnp ?? ''} ${p.phone ?? ''}</div>`;
      container.appendChild(row);
    });
  }

  /* ============================ Cleanup ============================ */

  /**
   * Clean up timers, streams and UI handlers.
   */
  cleanup() {
    this.clearPeriodicAutosave();
    this.unbindUIEvents();
    if (this.isRecording) {
      try { this.stopAudioRecording(); } catch (e) { /* ignore */ }
    }
    this._hideRecordingIndicator();
    // stop any leftover stream tracks
    this._stopAudioStream();
  }
}

/* ============================ Export ============================ */
export { ConsultationManager };
