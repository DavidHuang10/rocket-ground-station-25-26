// Configuration management

export class ConfigManager {
    constructor() {
        this.config = null;
    }

    async load() {
        try {
            const response = await fetch('/config.json');
            this.config = await response.json();
            console.log('Configuration loaded:', this.config);
            return this.config;
        } catch (e) {
            console.error('Failed to load configuration:', e);
            this.config = { panels: [], field_metadata: {} };
            return this.config;
        }
    }

    get panels() {
        return this.config?.panels || [];
    }

    get sortedPanels() {
        return [...this.panels].sort((a, b) => a.order - b.order);
    }

    get fieldMetadata() {
        return this.config?.field_metadata || {};
    }

    getAllFields() {
        const fields = new Set();
        this.panels.forEach(panel => {
            if (panel.fields) {
                panel.fields.forEach(f => fields.add(f));
            }
            if (panel.items) {
                panel.items.forEach(item => {
                    if (item.field) fields.add(item.field);
                });
            }
        });
        return fields;
    }
}
