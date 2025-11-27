// documents.js
// Main orchestrator for Documents module: combines navigation + actions.

import { DocumentActions } from './documents/documents.actions.js';
import { DocumentNavigation } from './documents/documents.navigation.js';

export class DocumentManager {
  constructor() {
    this.currentUploadPatientId = null;

    this.actions = DocumentActions;
    this.nav = DocumentNavigation;
  }

  async init() {
    console.log('DocumentManager init called');
    this.nav.bindUIEvents();
    await this.nav.refreshUnprocessedList();
  }

  setUploadContext(patientId){
    // null = secretary/doc-centric; ID = patient-centric
    this.currentUploadPatientId=patientId||null;
  }

  clearUploadContext() {
    this.currentUploadPatientId = null;
  }
}