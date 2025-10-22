// static/js/clinics.js
class ClinicManager {
    constructor() {
        this.clinicData = null;
    }
    
    async loadClinicData() {
        try {
            const response = await fetch(apiUrl(API_CONFIG.ENDPOINTS.clinics, `my-clinic`));
            if (!response.ok) throw new Error('Failed to load clinic data');
            
            this.clinicData = await response.json();
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