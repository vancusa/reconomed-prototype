// documents.js
// Main orchestrator for Documents module: combines navigation + actions.

import { DocumentActions } from './documents/documents.actions.js';
import { DocumentNavigation } from './documents/documents.navigation.js';

export class DocumentManager {
  constructor() {
    this.actions = DocumentActions;
    this.nav = DocumentNavigation;
  }

  async init() {
    console.log('DocumentManager init called');
    this.nav.bindUIEvents();
    await this.nav.refreshUnprocessedList();
  }
}