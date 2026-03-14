// static/js/clinics.js
import { apiFetch, apiUrl, API_CONFIG } from './app.js';

class ClinicManager {
    constructor() {
        this.clinicData = null;
    }

    async init() {
        if (!this.clinicData) {
            await this.loadClinicData();
        }
    }

    async loadClinicData() {
        try {
            const response = await apiFetch(apiUrl(API_CONFIG.ENDPOINTS.clinics, `my-clinic`));
            //console.log(response);
            if (!response.ok) throw new Error('Failed to load clinic data');
            
            this.clinicData = await response.json();
            //console.log(this.clinicData);
            return this.clinicData;
        } catch (error) {
            console.error('Error loading clinic data:', error);
            return null;
        }
    }
    
    getClinicId() {
        return this.clinicData?.id || null;
    }
    
    getClinicName() {
        return this.clinicData?.name || 'Unknown Clinic';
    }
}

export { ClinicManager };
