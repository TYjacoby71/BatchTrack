
/**
 * Conversion Error Drawer Handler
 * Handles all conversion-related drawer errors
 */
export class ConversionDrawerHandler {
    constructor(drawerProtocol) {
        this.drawerProtocol = drawerProtocol;
    }

    async handleError(errorCode, errorData) {
        try {
            if (!errorData || typeof errorData !== 'object') {
                console.error('🚨 CONVERSION DRAWER: Invalid error data:', errorData);
                return false;
            }

            switch (errorCode) {
                case 'MISSING_DENSITY':
                    return this.handleMissingDensity(errorData);
                
                case 'MISSING_CUSTOM_MAPPING':
                case 'UNSUPPORTED_CONVERSION':
                    return this.handleMissingMapping(errorData);
                
                case 'UNKNOWN_SOURCE_UNIT':
                case 'UNKNOWN_TARGET_UNIT':
                    return this.handleUnknownUnit(errorData);
                
                default:
                    console.warn(`🔧 CONVERSION DRAWER: Unhandled error code: ${errorCode}`);
                    return false;
            }
        } catch (error) {
            console.error('🚨 CONVERSION DRAWER: Error handling conversion error:', error);
            return false;
        }
    }

    async handleMissingDensity(errorData) {
        if (!errorData.ingredient_id) {
            console.error('🚨 CONVERSION DRAWER: Missing ingredient_id for density error');
            return false;
        }
        
        console.log('🔧 CONVERSION DRAWER: Opening density modal for ingredient', errorData.ingredient_id);
        return this.drawerProtocol.openModal(
            '/api/drawer-actions/conversion/density-modal/' + errorData.ingredient_id,
            'densityUpdated'
        );
    }

    async handleMissingMapping(errorData) {
        if (!errorData.from_unit || !errorData.to_unit) {
            console.error('🚨 CONVERSION DRAWER: Missing unit data for mapping error:', errorData);
            return false;
        }
        
        const params = new URLSearchParams({
            from_unit: errorData.from_unit,
            to_unit: errorData.to_unit
        });
        
        return this.drawerProtocol.openModal(
            '/api/drawer-actions/conversion/unit-mapping-modal?' + params,
            'unitMappingCreated'
        );
    }

    async handleUnknownUnit(errorData) {
        if (!errorData.unit) {
            console.error('🚨 CONVERSION DRAWER: Missing unit for unit creation error:', errorData);
            return false;
        }
        
        window.open('/conversion/units', '_blank');
        return true;
    }
}
